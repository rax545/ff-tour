"""Player passport, digital certificates and squad war room slash commands."""

import asyncio

import discord
from discord import app_commands

from services.arena import (
    issue_certificate,
    player_passport,
    revoke_certificate,
    verify_certificate,
)
from services.squad_ops import (
    MAPS,
    close_ready_check,
    open_ready_check,
    ready_status,
    save_plan,
    set_ready,
    squad_briefing,
)
from services.war_rooms import WarRoomService
from utils.arena_cards import passport_card as passport
from utils.cards import certificate
from utils.embeds import base, err, ok
from utils.interactions import TournamentCog, display
from utils.permissions import require_staff, staff
from views.arena import ReadyButton, ready_embed, ready_view


@app_commands.guild_only()
class Arena(TournamentCog):
    certificate_group = app_commands.Group(
        name="certificate", description="Issue and verify digital certificates", guild_only=True
    )
    squad = app_commands.Group(name="squad", description="Private squad war rooms", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        self.rooms = WarRoomService()
        bot.add_dynamic_items(ReadyButton)

    def cog_unload(self):
        self.bot.remove_dynamic_items(ReadyButton)

    @app_commands.command(
        name="passport",
        description="View your private player passport and verified individual stats",
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0)
    async def player_passport_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        rosters, stats, student = await player_passport(interaction.user.id)
        if not rosters:
            return await interaction.followup.send(
                embed=err(
                    "No linked player roster. Ask your captain to link your Discord account via /team addplayer."
                ),
                ephemeral=True,
            )
        image = await asyncio.to_thread(
            passport, interaction.user.display_name, rosters, stats, student
        )
        await interaction.followup.send(
            file=discord.File(image, filename="player-passport.png"),
            content="Private roster-linked passport • Not official Garena identity verification. Only verified, non-conflicting individual results count; student ID is never included.",
            ephemeral=True,
        )

    @certificate_group.command(
        name="issue", description="Staff: issue a registered player achievement certificate"
    )
    async def issue(
        self,
        interaction: discord.Interaction,
        tournament_id: int,
        team_id: int,
        recipient: discord.Member,
        award: app_commands.Range[str, 1, 80],
    ):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            record = await issue_certificate(
                interaction.guild.id,
                tournament_id,
                team_id,
                recipient.id,
                award,
                interaction.user.id,
            )
        except ValueError as exc:
            return await interaction.followup.send(embed=err(str(exc)), ephemeral=True)
        image = await asyncio.to_thread(certificate, record)
        await interaction.followup.send(
            file=discord.File(image, filename=f"{record['code']}.png"),
            content=f"Certificate `{record['code']}` • Share this image with the recipient. Verify using `/certificate verify`.",
            ephemeral=True,
        )

    @certificate_group.command(
        name="verify", description="Check an issued certificate in this server registry"
    )
    async def verify(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)
        record = await verify_certificate(interaction.guild.id, code)
        if not record:
            return await interaction.followup.send(
                embed=err("Certificate not found in this server."), ephemeral=True
            )
        embed = base("Digital Certificate • " + ("REVOKED" if record["revoked_at"] else "VALID"))
        for label, key in [
            ("Registry code", "code"),
            ("Recipient", "recipient_name"),
            ("Tournament", "tournament_name"),
            ("Squad", "team_name"),
            ("Award", "award"),
            ("Issued at (UTC)", "issued_at"),
        ]:
            embed.add_field(
                name=label,
                value=discord.utils.escape_markdown(str(record[key]))[:1024],
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @certificate_group.command(
        name="revoke", description="Staff: permanently revoke an issued certificate"
    )
    async def revoke(self, interaction: discord.Interaction, code: str):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        changed = await revoke_certificate(interaction.guild.id, code, interaction.user.id)
        await interaction.followup.send(
            embed=ok("Certificate revoked.") if changed else err("Not found or already revoked."),
            ephemeral=True,
        )

    async def room_action(self, interaction, team_id, close=False):
        await interaction.response.defer(ephemeral=True)
        try:
            rooms = await self.rooms.manage(
                interaction.guild, interaction.user, team_id, close=close
            )
        except ValueError as exc:
            return await interaction.followup.send(embed=err(str(exc)), ephemeral=True)
        except discord.HTTPException:
            return await interaction.followup.send(
                embed=err(
                    "Discord could not update the room. Check Manage Channels / View Channel permissions, then retry."
                ),
                ephemeral=True,
            )
        text = (
            "Squad war room closed."
            if close
            else f"Private rooms ready: {rooms[0].mention} • {rooms[1].mention}\nRoster access synchronized. Server administrators can always access channels."
        )
        await interaction.followup.send(embed=ok(text), ephemeral=True)

    @squad.command(
        name="warroom",
        description="Captain/staff: create or synchronize private text and voice rooms",
    )
    async def warroom(self, interaction: discord.Interaction, team_id: int):
        await self.room_action(interaction, team_id)

    @squad.command(
        name="close", description="Captain/staff: delete the squad text and voice war rooms"
    )
    async def close(self, interaction: discord.Interaction, team_id: int):
        await self.room_action(interaction, team_id, close=True)

    @squad.command(
        name="plan", description="Captain/staff: save a private drop zone and tactical strategy"
    )
    @app_commands.choices(map_name=[app_commands.Choice(name=name, value=name) for name in MAPS])
    async def plan(
        self,
        interaction: discord.Interaction,
        team_id: app_commands.Range[int, 1],
        map_name: app_commands.Choice[str],
        drop_zone: app_commands.Range[str, 1, 80],
        strategy: app_commands.Range[str, 1, 1500],
    ):
        await interaction.response.defer(ephemeral=True)
        await save_plan(
            interaction.guild.id,
            team_id,
            interaction.user.id,
            map_name.value,
            drop_zone,
            strategy,
            is_staff=staff(interaction.user),
        )
        await interaction.followup.send(
            embed=ok(
                "Private strategy saved. Current squad members can read it with /squad briefing."
            ),
            ephemeral=True,
        )

    @squad.command(
        name="briefing",
        description="Current roster/staff: view private strategy, lineup and recent ready checks",
    )
    async def briefing(self, interaction: discord.Interaction, team_id: app_commands.Range[int, 1]):
        await interaction.response.defer(ephemeral=True)
        data = await squad_briefing(
            interaction.guild.id, team_id, interaction.user.id, is_staff=staff(interaction.user)
        )
        plan = data["plan"]
        strategy = (
            discord.utils.escape_mentions(discord.utils.escape_markdown(plan["strategy"]))
            if plan
            else "No strategy saved. Captain/staff can use /squad plan."
        )
        embed = base(f"Private War Room • {display(data['team']['name'], 120)}", strategy[:3500])
        if plan:
            embed.add_field(
                name="Map / drop zone",
                value=f"{plan['map_name']} • {display(plan['drop_zone'], 160)}",
                inline=False,
            )
        lines = [
            f"{display(m['ign'], 60)} • {display(m['role'], 30)}"
            + (" [SUB]" if m["is_sub"] else "")
            for m in data["members"]
        ]
        embed.add_field(
            name="Roster", value="\n".join(lines)[:1024] or "No roster entries yet.", inline=False
        )
        checks = [
            f"Check #{c['id']} • Match #{c['match_no']} • expires <t:{c['expires_at']}:R>"
            for c in data["checks"]
        ]
        embed.add_field(
            name="Recent ready checks", value="\n".join(checks) or "No checks yet.", inline=False
        )
        embed.set_footer(
            text="Private squad notes • Access is checked against the current roster on each request."
        )
        await interaction.followup.send(
            embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @squad.command(
        name="readycheck",
        description="Captain/staff: post an expiring ready check in the private war room",
    )
    async def readycheck(
        self,
        interaction: discord.Interaction,
        team_id: app_commands.Range[int, 1],
        match_id: app_commands.Range[int, 1],
    ):
        await interaction.response.defer(ephemeral=True)
        check, created = await open_ready_check(
            interaction.guild.id,
            team_id,
            match_id,
            interaction.user.id,
            is_staff=staff(interaction.user),
        )
        text_channel, voice = await self.rooms.manage(interaction.guild, interaction.user, team_id)
        row = await ready_status(
            interaction.guild.id, check["id"], interaction.user.id, is_staff=staff(interaction.user)
        )
        message = await text_channel.send(
            embed=ready_embed(row),
            view=ready_view(row),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await interaction.followup.send(
            embed=ok(
                f"{'New' if created else 'Existing'} ready check **#{check['id']}** posted privately: {message.jump_url}"
            ),
            ephemeral=True,
        )

    @squad.command(
        name="ready",
        description="Current roster: mark yourself ready or not ready for an active check",
    )
    async def ready(
        self,
        interaction: discord.Interaction,
        check_id: app_commands.Range[int, 1],
        ready: bool = True,
    ):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.bot:
            raise ValueError("Bot accounts cannot mark player readiness.")
        row = await set_ready(interaction.guild.id, check_id, interaction.user.id, ready)
        await interaction.followup.send(
            embed=ready_embed(row), ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @squad.command(
        name="readiness", description="Current roster/staff: view up-to-date private readiness"
    )
    async def readiness(
        self, interaction: discord.Interaction, check_id: app_commands.Range[int, 1]
    ):
        await interaction.response.defer(ephemeral=True)
        row = await ready_status(
            interaction.guild.id, check_id, interaction.user.id, is_staff=staff(interaction.user)
        )
        await interaction.followup.send(
            embed=ready_embed(row), ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @squad.command(name="readyclose", description="Captain/staff: close a ready check early")
    async def readyclose(
        self, interaction: discord.Interaction, check_id: app_commands.Range[int, 1]
    ):
        await interaction.response.defer(ephemeral=True)
        await close_ready_check(
            interaction.guild.id, check_id, interaction.user.id, is_staff=staff(interaction.user)
        )
        await interaction.followup.send(
            embed=ok("Ready check closed. Old buttons can no longer change responses."),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Arena(bot))
