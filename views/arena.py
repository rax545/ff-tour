"""Stateless dynamic components: old messages keep working after bot restarts."""

import discord

from services.predictions import pick_team
from services.squad_ops import set_ready
from utils.embeds import base
from utils.interactions import command_error, display
from utils.permissions import require_tournament_guild


class PredictionSelect(
    discord.ui.DynamicItem[discord.ui.Select],
    template=r"ff:prediction:(?P<pool_id>[0-9]+):(?P<page>[0-9]+)",
):
    def __init__(self, pool_id, page=1, entries=None, *, item=None, disabled=False):
        self.pool_id = pool_id
        self.page = page
        if item is None:
            item = discord.ui.Select(
                custom_id=f"ff:prediction:{pool_id}:{page}",
                placeholder="Pick your winning squad (editable until lock)",
                min_values=1,
                max_values=1,
                disabled=disabled,
                options=[
                    discord.SelectOption(
                        label=f"[{e['tag']}] {e['name']}"[:100],
                        value=str(e["team_id"]),
                        description=f"Team #{e['team_id']} • {e['picks']} picks"[:100],
                    )
                    for e in entries
                ],
            )
        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pool_id"]), int(match["page"]), item=item)

    async def callback(self, interaction):
        if not await require_tournament_guild(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.bot:
                raise ValueError("Bot accounts cannot make predictions.")
            values = interaction.data.get("values", [])
            if len(values) != 1 or not values[0].isdigit():
                raise ValueError("Select a valid squad.")
            entry = await pick_team(
                interaction.guild.id, self.pool_id, interaction.user.id, int(values[0])
            )
            await interaction.followup.send(
                f"✅ Your pick: **{display(entry['name'])}**. You can change it before the arena locks.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as exc:
            await command_error(interaction, exc)


def prediction_view(pool, entries, page):
    view = discord.ui.View(timeout=None)
    if entries:
        view.add_item(
            PredictionSelect(pool["id"], page, entries, disabled=pool["status"] != "open")
        )
    return view


def ready_embed(row):
    embed = base(
        f"Squad Ready Check #{row['id']} • {row['status'].upper()}",
        f"{display(row['team_name'])} • Match #{row['match_no']}\nExpires <t:{row['expires_at']}:R>.",
    )
    embed.add_field(
        name=f"Ready ({len(row['ready_ids'])})",
        value=" ".join(f"<@{user_id}>" for user_id in row["ready_ids"])[:1024] or "Nobody yet.",
        inline=False,
    )
    embed.add_field(
        name=f"Pending ({len(row['pending_ids'])})",
        value=" ".join(f"<@{user_id}>" for user_id in row["pending_ids"])[:1024]
        or "All linked players ready.",
        inline=False,
    )
    if row["unlinked_slots"]:
        embed.add_field(
            name="Unlinked roster slots",
            value=f"{row['unlinked_slots']} player(s) cannot respond until linked to Discord.",
            inline=False,
        )
    embed.set_footer(
        text="Private squad readiness • Current roster access is checked on every click."
    )
    return embed


class ReadyButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"ff:ready:(?P<check_id>[0-9]+):(?P<ready>[01])",
):
    def __init__(self, check_id, ready=True, *, item=None, disabled=False):
        self.check_id = check_id
        self.ready = ready
        super().__init__(
            item
            or discord.ui.Button(
                label="I'm ready" if ready else "Not ready",
                style=discord.ButtonStyle.success if ready else discord.ButtonStyle.secondary,
                custom_id=f"ff:ready:{check_id}:{int(ready)}",
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["check_id"]), match["ready"] == "1", item=item)

    async def callback(self, interaction):
        if not await require_tournament_guild(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.bot:
                raise ValueError("Bot accounts cannot mark player readiness.")
            row = await set_ready(
                interaction.guild.id, self.check_id, interaction.user.id, self.ready
            )
            # A failed refresh never undoes a successful, persisted response.
            try:
                await interaction.message.edit(embed=ready_embed(row), view=ready_view(row))
            except discord.HTTPException:
                pass
            await interaction.followup.send(
                "✅ Ready." if self.ready else "⏳ Marked not ready.", ephemeral=True
            )
        except Exception as exc:
            await command_error(interaction, exc)


def ready_view(row):
    view = discord.ui.View(timeout=None)
    for ready in (True, False):
        view.add_item(ReadyButton(row["id"], ready, disabled=row["status"] != "open"))
    return view
