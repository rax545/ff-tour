"""Champions, knockout brackets, clash graphics, predictions and private radar UI."""

import asyncio
import json

import discord
from discord import app_commands

from services.arena_common import page_slice
from services.brackets import bind_match, bracket_tree, create_bracket, resolve_node
from services.clash import clash_poster_data
from services.hall_of_fame import hall_of_fame, induct_tournament, revoke_induction
from services.predictions import (
    cancel_predictions,
    list_predictions,
    lock_predictions,
    open_predictions,
    pick_team,
    prediction_leaderboard,
    prediction_pool,
    settle_predictions,
)
from services.radar import radar_findings, review_finding, scan_rosters
from services.reminders import parse_schedule_time
from services.stream_delivery import update_stopped_announcement
from services.streams import get_stream, list_streams
from utils.arena_cards import bracket_card, clash_card, hall_of_fame_card, prediction_card
from utils.embeds import base, ok
from utils.interactions import TournamentCog, display
from utils.permissions import require_staff
from utils.validation import validate_stream_url
from views.arena import PredictionSelect, prediction_view

NO_PINGS = discord.AllowedMentions.none()


class Competition(TournamentCog):
    live = app_commands.Group(
        name="live", description="Current tournament broadcasts", guild_only=True
    )
    hall = app_commands.Group(
        name="halloffame", description="Archived tournament champions and MVPs", guild_only=True
    )
    bracket = app_commands.Group(
        name="bracket", description="Seeded single-elimination bracket trees", guild_only=True
    )
    clash = app_commands.Group(
        name="clash", description="Public squad-versus-squad match posters", guild_only=True
    )
    prediction = app_commands.Group(
        name="prediction", description="Free predictions, no money or betting", guild_only=True
    )
    radar = app_commands.Group(
        name="radar", description="Staff-only, human-reviewed anti-smurf signals", guild_only=True
    )

    def __init__(self, bot):
        self.bot = bot
        bot.add_dynamic_items(PredictionSelect)

    def cog_unload(self):
        self.bot.remove_dynamic_items(PredictionSelect)

    @live.command(name="list", description="List matches currently marked live by staff")
    async def live_list(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 0] = 0,
        page: app_commands.Range[int, 1] = 1,
    ):
        await interaction.response.defer()
        rows, total = page_slice(await list_streams(tournament_id), page, 6)
        embed = base(
            f"Live Broadcasts • Page {page}/{total}",
            "Staff-controlled LIVE status; the bot does not check provider uptime.",
        )
        if not rows:
            embed.description += "\nNo broadcasts are currently live."
        for row in rows:
            try:
                url = validate_stream_url(row["stream_url"])
                link = f"<{url}>"
            except ValueError:
                link = "Saved link is invalid; ask staff to update it."
            embed.add_field(
                name=f"Match #{row['match_no']} • {display(row['tournament_name'], 120)}",
                value=f"{display(row['stream_platform'], 40)} • {display(row['map'] or 'TBA', 50)}\n{link}",
                inline=False,
            )
        await interaction.followup.send(embed=embed, allowed_mentions=NO_PINGS)

    @hall.command(
        name="induct",
        description="Staff: finalize and archive verified champions and individual MVP",
    )
    async def induct(
        self, interaction: discord.Interaction, tournament_id: app_commands.Range[int, 1]
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        record = await induct_tournament(interaction.guild.id, tournament_id, interaction.user.id)
        image = await asyncio.to_thread(hall_of_fame_card, [record])
        await interaction.followup.send(
            content=f"Champion archive **#{record['id']}** saved. Tournament finalized; publish with `/halloffame show`.",
            file=discord.File(image, filename="hall-of-fame.png"),
            ephemeral=True,
            allowed_mentions=NO_PINGS,
        )

    @hall.command(
        name="show", description="Show the champions gallery, with historical scores and MVPs"
    )
    @app_commands.checks.cooldown(1, 5.0)
    async def hall_show(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 0] = 0,
        page: app_commands.Range[int, 1] = 1,
    ):
        await interaction.response.defer()
        rows, total = page_slice(await hall_of_fame(interaction.guild.id, tournament_id), page, 4)
        if not rows:
            return await interaction.followup.send(
                "No finalized championships yet. Staff can use `/halloffame induct`.",
                allowed_mentions=NO_PINGS,
            )
        image = await asyncio.to_thread(hall_of_fame_card, rows, page, total)
        await interaction.followup.send(
            file=discord.File(image, filename="hall-of-fame.png"), allowed_mentions=NO_PINGS
        )

    @hall.command(
        name="revoke",
        description="Staff: hide an incorrect archive, retaining its history and reason",
    )
    async def hall_revoke(
        self,
        interaction: discord.Interaction,
        archive_id: app_commands.Range[int, 1],
        reason: app_commands.Range[str, 1, 300],
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await revoke_induction(interaction.guild.id, archive_id, interaction.user.id, reason)
        await interaction.followup.send(
            embed=ok("Archive revoked; original snapshot and audit history retained."),
            ephemeral=True,
        )

    async def _send_bracket(self, interaction, snapshot, page=1):
        nodes, total = page_slice(snapshot["nodes"], page, 8)
        names = {e["team_id"]: display(e["name"], 45) for e in snapshot["entries"]}
        lines = []
        for node in nodes:
            a, b = node["team_a"], node["team_b"]
            lines.append(
                f"**Node #{node['id']}** • Round {node['round_no']} • {node['status'].upper()}\n"
                f"A: {names.get(a, 'TBD/BYE')} (`{a or '—'}`) vs B: {names.get(b, 'TBD/BYE')} (`{b or '—'}`)"
                + (f" • Fixture `{node['match_id']}`" if node["match_id"] else "")
            )
        embed = base(
            f"Bracket • {display(snapshot['tournament_name'], 100)} • Page {page}/{total}",
            "\n\n".join(lines)
            + "\n\nStaff: `/bracket resolve` confirms scores in A/B order. `/bracket bind` connects a READY node to a match fixture.",
        )
        image = await asyncio.to_thread(bracket_card, snapshot)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(image, filename="bracket-tree.png"),
            allowed_mentions=NO_PINGS,
        )

    @bracket.command(
        name="create",
        description="Staff: freeze registration and seed a 2–32 squad knockout bracket",
    )
    @app_commands.describe(
        seeds="Optional comma-separated team IDs, all squads exactly once, best seed first"
    )
    async def bracket_create(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 1],
        seeds: app_commands.Range[str, 0, 500] = "",
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer()
        ordered = None
        if seeds.strip():
            parts = [part.strip() for part in seeds.split(",")]
            if not all(p.isdigit() for p in parts):
                raise ValueError("Seeds must be comma-separated team IDs.")
            ordered = [int(p) for p in parts]
        snapshot = await create_bracket(
            interaction.guild.id, tournament_id, interaction.user.id, ordered
        )
        await self._send_bracket(interaction, snapshot)

    @bracket.command(
        name="tree", description="Show the graphical bracket and paginated node/team IDs"
    )
    @app_commands.checks.cooldown(1, 5.0)
    async def tree(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 1],
        page: app_commands.Range[int, 1] = 1,
    ):
        await interaction.response.defer()
        await self._send_bracket(
            interaction, await bracket_tree(interaction.guild.id, tournament_id), page
        )

    @bracket.command(
        name="resolve",
        description="Staff: confirm a node winner and advance them to the next round",
    )
    async def resolve(
        self,
        interaction: discord.Interaction,
        node_id: app_commands.Range[int, 1],
        winner_team_id: app_commands.Range[int, 1],
        score_a: app_commands.Range[int, 0, 99],
        score_b: app_commands.Range[int, 0, 99],
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer()
        snapshot = await resolve_node(
            interaction.guild.id, node_id, winner_team_id, score_a, score_b, interaction.user.id
        )
        resolved = next(n for n in snapshot["nodes"] if n["id"] == node_id)
        if resolved["match_id"]:
            await update_stopped_announcement(
                interaction.guild, await get_stream(resolved["match_id"])
            )
        await self._send_bracket(interaction, snapshot)

    @bracket.command(
        name="bind",
        description="Staff: bind a READY bracket node to an unused match in the same tournament",
    )
    async def bind(
        self,
        interaction: discord.Interaction,
        node_id: app_commands.Range[int, 1],
        match_id: app_commands.Range[int, 1],
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await bind_match(interaction.guild.id, node_id, match_id, interaction.user.id)
        await interaction.followup.send(
            embed=ok(
                "Fixture bound. Streams, clash posters and predictions use only these two opponents."
            ),
            ephemeral=True,
        )

    @clash.command(
        name="poster",
        description="Render a 1600×900 versus poster without exposing private player IDs",
    )
    @app_commands.checks.cooldown(1, 5.0)
    async def poster(
        self,
        interaction: discord.Interaction,
        match_id: app_commands.Range[int, 1],
        team_a_id: app_commands.Range[int, 1],
        team_b_id: app_commands.Range[int, 1],
    ):
        await interaction.response.defer()
        data = await clash_poster_data(interaction.guild.id, match_id, team_a_id, team_b_id)
        image = await asyncio.to_thread(clash_card, data)
        await interaction.followup.send(
            file=discord.File(image, filename="squad-clash.png"), allowed_mentions=NO_PINGS
        )

    async def _send_arena(self, interaction, pool, page=1):
        entries, total = page_slice(pool["entries"], page, 12)
        embed = base(
            f"Prediction Arena #{pool['id']} • {pool['status'].upper()}",
            f"{display(pool['tournament_name'], 120)} • Match #{pool['match_no']}\n"
            f"Cutoff <t:{pool['effective_closes_at']}:F> (<t:{pool['effective_closes_at']}:R>).\n"
            "One editable pick per Discord account. Correct pick = **10 points**. No gambling or payouts.\n"
            f"Page **{page}/{total}**. Use `/prediction arena page:…` for other opponents.",
        )
        image = await asyncio.to_thread(prediction_card, pool, entries, page, total)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(image, filename="prediction-arena.png"),
            view=prediction_view(pool, entries, page),
            allowed_mentions=NO_PINGS,
        )

    @prediction.command(
        name="open",
        description="Staff: open free predictions before the match with a future cutoff",
    )
    @app_commands.describe(
        closes_at="Local time, e.g. 2026-10-07 21:00 or tomorrow 9:00 PM; no later than match start"
    )
    async def prediction_open(
        self, interaction: discord.Interaction, match_id: app_commands.Range[int, 1], closes_at: str
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer()
        deadline = int(parse_schedule_time(closes_at).timestamp())
        pool = await open_predictions(interaction.guild.id, match_id, deadline, interaction.user.id)
        await self._send_arena(interaction, pool)

    @prediction.command(
        name="arena",
        description="Show an arena with live vote totals and a persistent squad selector",
    )
    @app_commands.checks.cooldown(1, 5.0)
    async def arena(
        self,
        interaction: discord.Interaction,
        pool_id: app_commands.Range[int, 1],
        page: app_commands.Range[int, 1] = 1,
    ):
        await interaction.response.defer()
        await self._send_arena(
            interaction, await prediction_pool(interaction.guild.id, pool_id), page
        )

    @prediction.command(name="list", description="List prediction arenas in this server")
    async def prediction_list(
        self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1
    ):
        await interaction.response.defer()
        rows, total = page_slice(await list_predictions(interaction.guild.id), page, 10)
        lines = [
            f"**Arena #{r['id']}** • Match #{r['match_no']} • {r['status'].upper()} • {display(r['tournament_name'], 100)}"
            for r in rows
        ]
        await interaction.followup.send(
            embed=base(
                f"Prediction Arenas • Page {page}/{total}", "\n".join(lines) or "No arenas yet."
            ),
            allowed_mentions=NO_PINGS,
        )

    @prediction.command(
        name="pick", description="Privately submit or change your winning-squad prediction"
    )
    async def pick(
        self,
        interaction: discord.Interaction,
        pool_id: app_commands.Range[int, 1],
        team_id: app_commands.Range[int, 1],
    ):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.bot:
            raise ValueError("Bot accounts cannot make predictions.")
        entry = await pick_team(interaction.guild.id, pool_id, interaction.user.id, team_id)
        await interaction.followup.send(
            embed=ok(f"Your pick: **{display(entry['name'])}**. Change it any time before lock."),
            ephemeral=True,
            allowed_mentions=NO_PINGS,
        )

    @prediction.command(
        name="mypick", description="Show your private current prediction and awarded points"
    )
    async def mypick(self, interaction: discord.Interaction, pool_id: app_commands.Range[int, 1]):
        await interaction.response.defer(ephemeral=True)
        pool = await prediction_pool(interaction.guild.id, pool_id, interaction.user.id)
        pick = pool["my_pick"]
        entry = next((e for e in pool["entries"] if pick and e["team_id"] == pick["team_id"]), None)
        text = (
            f"{display(entry['name'])} • {pick['awarded_points']} points • {pool['status'].upper()}"
            if entry
            else "You have not made a prediction in this arena."
        )
        await interaction.followup.send(
            embed=base("Your Prediction", text), ephemeral=True, allowed_mentions=NO_PINGS
        )

    @prediction.command(
        name="lock", description="Staff: close voting immediately, without awarding points"
    )
    async def lock(self, interaction: discord.Interaction, pool_id: app_commands.Range[int, 1]):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await lock_predictions(interaction.guild.id, pool_id, interaction.user.id)
        await interaction.followup.send(
            embed=ok("Voting locked. Use /prediction settle after results are confirmed."),
            ephemeral=True,
        )

    @prediction.command(
        name="settle",
        description="Staff: award points once using verified BR results or a resolved bracket node",
    )
    async def settle(self, interaction: discord.Interaction, pool_id: app_commands.Range[int, 1]):
        if not await require_staff(interaction):
            return
        await interaction.response.defer()
        await self._send_arena(
            interaction,
            await settle_predictions(interaction.guild.id, pool_id, interaction.user.id),
        )

    @prediction.command(
        name="cancel", description="Staff: cancel an un-settled arena without awarding any points"
    )
    async def cancel(self, interaction: discord.Interaction, pool_id: app_commands.Range[int, 1]):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await cancel_predictions(interaction.guild.id, pool_id, interaction.user.id)
        await interaction.followup.send(
            embed=ok("Arena cancelled. No points awarded and it cannot be reopened."),
            ephemeral=True,
        )

    @prediction.command(
        name="leaderboard", description="Show server prediction points and correct-pick counts"
    )
    async def prediction_ranks(
        self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1
    ):
        await interaction.response.defer()
        rows, total = page_slice(await prediction_leaderboard(interaction.guild.id), page, 10)
        lines = [
            f"**#{(page - 1) * 10 + i}** <@{r['user_id']}> • **{r['points']} pts** • {r['correct']}/{r['predictions']} correct"
            for i, r in enumerate(rows, 1)
        ]
        await interaction.followup.send(
            embed=base(
                f"Prediction Rankings • Page {page}/{total}",
                "\n".join(lines) or "No settled predictions yet.",
            ),
            allowed_mentions=NO_PINGS,
        )

    async def _send_radar(
        self, interaction, tournament_id, page, include_inactive=False, summary=""
    ):
        rows, total = page_slice(
            await radar_findings(
                interaction.guild.id, tournament_id, include_inactive=include_inactive
            ),
            page,
            5,
        )
        embed = base(
            f"Private Anti-Smurf Radar • Page {page}/{total}",
            summary
            + "\nSignals are review leads, not proof of cheating. No automatic bans or public accusations.",
        )
        if not rows:
            embed.description += "\nNo current signals. This is not identity clearance."
        for row in rows:
            evidence = display(json.dumps(row["evidence"], ensure_ascii=False), 480)
            value = (
                f"{display(row['summary'], 180)}\nEvidence: {evidence}\n"
                f"Review: **{row['status'].upper()}** • {'ACTIVE' if row['active'] else 'INACTIVE'}"
                + (f"\nNote: {display(row['review_note'], 220)}" if row["review_note"] else "")
            )
            embed.add_field(
                name=f"Finding #{row['id']} • {row['severity'].upper()} • {row['kind']}",
                value=value[:1024],
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=NO_PINGS)

    @radar.command(
        name="scan",
        description="Staff: scan roster UID reuse, account links and verified scoring anomalies",
    )
    @app_commands.checks.cooldown(1, 5.0)
    async def scan(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 1],
        page: app_commands.Range[int, 1] = 1,
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        result = await scan_rosters(interaction.guild.id, tournament_id, interaction.user.id)
        await self._send_radar(
            interaction,
            tournament_id,
            page,
            summary=f"Scanned {result['teams']} squads / {result['roster_slots']} slots. {result['signals']} signals.",
        )

    @radar.command(
        name="list", description="Staff: view saved findings and review history privately"
    )
    async def findings(
        self,
        interaction: discord.Interaction,
        tournament_id: app_commands.Range[int, 1],
        page: app_commands.Range[int, 1] = 1,
        include_inactive: bool = False,
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self._send_radar(interaction, tournament_id, page, include_inactive)

    @radar.command(
        name="review",
        description="Staff: confirm a review concern or clear it; never bans a player",
    )
    @app_commands.choices(
        decision=[
            app_commands.Choice(name="Clear signal", value="cleared"),
            app_commands.Choice(name="Confirm review concern", value="confirmed"),
        ]
    )
    async def review(
        self,
        interaction: discord.Interaction,
        finding_id: app_commands.Range[int, 1],
        decision: app_commands.Choice[str],
        note: app_commands.Range[str, 1, 300],
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await review_finding(
            interaction.guild.id, finding_id, interaction.user.id, decision.value, note
        )
        await interaction.followup.send(
            embed=ok("Review saved privately. No player was banned or removed."), ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Competition(bot))
