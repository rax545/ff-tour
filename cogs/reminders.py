"""
Match Reminder & Schedule Notification cog.

Staff schedule a match time with /reminder set, and the bot
automatically announces countdown reminders in the channel and
DMs every registered squad member before the match starts.
"""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from discord import app_commands

from config import SERVER_NAME
from database.db import connect, audit
from services.reminders import (
    parse_schedule_time,
    parse_offsets,
    schedule_match_reminders,
    due_reminders,
    pending_reminders,
    mark_reminder,
    cancel_match_reminders,
)
from utils.embeds import base, ok, err, match_reminder_embed
from utils.permissions import require_staff

logger = logging.getLogger("esports_bot.reminders")

CHECK_INTERVAL_SECONDS = 30


class Reminders(commands.Cog):
    """Automated match reminder & schedule notification system."""

    def __init__(self, bot):
        self.bot = bot

    reminder = app_commands.Group(
        name="reminder",
        description="Match reminder & schedule notification commands"
    )

    async def cog_load(self):
        self.reminder_dispatcher.start()

    async def cog_unload(self):
        self.reminder_dispatcher.cancel()

    # =========================================================
    # /reminder set
    # =========================================================

    @reminder.command(
        name="set",
        description="Schedule a match time and auto reminders (channel + squad DMs)"
    )
    @app_commands.describe(
        match_id="Match ID",
        when="Match time, e.g. '2026-10-07 21:00', 'today 9:00 PM', 'tomorrow 20:30'",
        offsets="Reminder times in minutes before match, e.g. '60,15,5' (default)",
        channel="Channel for public reminder announcements (default: current channel)"
    )
    async def reminder_set(
        self,
        interaction: discord.Interaction,
        match_id: int,
        when: str,
        offsets: str = "",
        channel: discord.TextChannel = None
    ):
        if not await require_staff(interaction):
            return

        if match_id < 1:
            return await interaction.response.send_message(
                embed=err("Match ID must be a positive integer."),
                ephemeral=True
            )

        # Parse schedule time & offsets
        try:
            match_time_utc = parse_schedule_time(when)
            offset_list = parse_offsets(offsets)
        except ValueError as e:
            return await interaction.response.send_message(
                embed=err(str(e)),
                ephemeral=True
            )

        await interaction.response.defer()

        target_channel = channel or interaction.channel
        db = await connect()

        try:
            cur = await db.execute(
                """
                SELECT m.id, m.tournament_id, m.match_no, m.map,
                       t.name AS tournament_name
                FROM matches m
                JOIN tournaments t ON t.id = m.tournament_id
                WHERE m.id=?
                """,
                (match_id,)
            )
            match = await cur.fetchone()

            if not match:
                return await interaction.followup.send(
                    embed=err(f"Match `#{match_id}` not found."),
                    ephemeral=True
                )

            match_unix = int(match_time_utc.timestamp())

            # Keep the match row's human-readable schedule in sync
            await db.execute(
                "UPDATE matches SET scheduled_at=? WHERE id=?",
                (f"<t:{match_unix}:F>", match_id)
            )

            await db.execute("UPDATE prediction_pools SET closes_at=MIN(closes_at,?) WHERE match_id=? AND status='open'",
                             (match_unix, match_id))
            await db.execute("UPDATE squad_ready_checks SET expires_at=MIN(expires_at,?) WHERE match_id=? AND status='open'",
                             (match_unix, match_id))

            scheduled = await schedule_match_reminders(
                db,
                match_id=match_id,
                tournament_id=match["tournament_id"],
                channel_id=target_channel.id if target_channel else 0,
                created_by=interaction.user.id,
                match_time_utc=match_time_utc,
                offsets=offset_list
            )

        except Exception as e:
            await db.rollback()
            return await interaction.followup.send(
                embed=err(f"Failed to schedule reminders.\n```{e}```"),
                ephemeral=True
            )
        finally:
            await db.close()

        if not scheduled:
            return await interaction.followup.send(
                embed=err(
                    "All requested reminder times are already in the past.\n"
                    "Pick a later match time or smaller offsets."
                ),
                ephemeral=True
            )

        await audit(
            interaction.user.id,
            "reminder_set",
            f"match #{match_id} at {match_time_utc.isoformat()} "
            f"offsets={[o for o, _ in scheduled]}"
        )

        timeline = "\n".join(
            f"▸ ⏰ **{off} min before** — <t:{int(remind_at.timestamp())}:t> "
            f"(<t:{int(remind_at.timestamp())}:R>)"
            for off, remind_at in scheduled
        )

        embed = base(
            title="⏰ MATCH REMINDERS SCHEDULED!",
            description=(
                f"```fix\n"
                f"🐺 {SERVER_NAME} • SCHEDULE LOCKED 🐺\n"
                f"```\n"
                f"Automated reminders are armed for **Match #{match['match_no']}** "
                f"of **{match['tournament_name']}**."
            ),
            color=discord.Color.from_rgb(16, 185, 129)
        )
        embed.add_field(
            name="🏆 Tournament",
            value=f"**{match['tournament_name']}** (`#{match['tournament_id']}`)",
            inline=True
        )
        embed.add_field(
            name="🎮 Match",
            value=f"**Match #{match['match_no']}** (ID: `#{match_id}`)",
            inline=True
        )
        embed.add_field(
            name="🗺️ Map",
            value=f"**{match['map'] or 'TBA'}**",
            inline=True
        )
        embed.add_field(
            name="🕒 Match Time",
            value=f"<t:{match_unix}:F> (<t:{match_unix}:R>)",
            inline=False
        )
        embed.add_field(
            name="📢 Reminder Timeline",
            value=timeline,
            inline=False
        )
        embed.add_field(
            name="📍 Announcement Channel",
            value=target_channel.mention if target_channel else "`N/A`",
            inline=True
        )
        embed.add_field(
            name="📨 Squad DMs",
            value="**Enabled** — captains & members",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    # =========================================================
    # /reminder list
    # =========================================================

    @reminder.command(
        name="list",
        description="View all upcoming scheduled match reminders"
    )
    @app_commands.describe(
        tournament_id="Filter by tournament ID (optional)"
    )
    async def reminder_list(
        self,
        interaction: discord.Interaction,
        tournament_id: int = 0
    ):
        await interaction.response.defer()

        db = await connect()
        try:
            rows = await pending_reminders(
                db, tournament_id if tournament_id > 0 else None
            )
        finally:
            await db.close()

        if not rows:
            return await interaction.followup.send(
                embed=base(
                    "📭 No Upcoming Reminders",
                    "No pending match reminders found."
                    + (f" (Tournament `#{tournament_id}`)" if tournament_id else "")
                    + "\nStaff can schedule one with `/reminder set`."
                )
            )

        lines = []
        for r in rows:
            remind_unix = int(
                datetime.fromisoformat(r["remind_at"]).timestamp()
            )
            lines.append(
                f"▸ `#{r['id']}` — **{r['tournament_name']}** • "
                f"Match #{r['match_no']} ({r['map'] or 'TBA'}) • "
                f"**{r['offset_minutes']}m before** • <t:{remind_unix}:R>"
            )

        embed = base(
            title="⏰ UPCOMING MATCH REMINDERS",
            description=(
                f"```fix\n"
                f"🐺 {SERVER_NAME} • REMINDER SCHEDULE 🐺\n"
                f"```\n"
                + "\n".join(lines)
            ),
            color=discord.Color.from_rgb(59, 130, 246)
        )
        await interaction.followup.send(embed=embed)

    # =========================================================
    # /reminder cancel
    # =========================================================

    @reminder.command(
        name="cancel",
        description="Cancel all pending reminders for a match"
    )
    @app_commands.describe(
        match_id="Match ID whose reminders should be cancelled"
    )
    async def reminder_cancel(
        self,
        interaction: discord.Interaction,
        match_id: int
    ):
        if not await require_staff(interaction):
            return

        db = await connect()
        try:
            count = await cancel_match_reminders(db, match_id)
        finally:
            await db.close()

        if count < 1:
            return await interaction.response.send_message(
                embed=err(f"No pending reminders found for match `#{match_id}`."),
                ephemeral=True
            )

        await audit(
            interaction.user.id,
            "reminder_cancel",
            f"match #{match_id} ({count} reminders)"
        )

        await interaction.response.send_message(
            embed=ok(
                f"Cancelled **{count}** pending reminder(s) for match `#{match_id}`."
            )
        )

    # =========================================================
    # Background dispatcher
    # =========================================================

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def reminder_dispatcher(self):
        """Check for due reminders and dispatch channel + DM notifications."""
        try:
            db = await connect()
            try:
                rows = await due_reminders(db)
            finally:
                await db.close()

            for row in rows:
                try:
                    await self._dispatch_reminder(row)
                    status = "sent"
                except Exception:
                    logger.exception(
                        "Failed to dispatch reminder #%s", row["id"]
                    )
                    status = "failed"

                db = await connect()
                try:
                    await mark_reminder(db, row["id"], status)
                finally:
                    await db.close()

        except Exception:
            logger.exception("Reminder dispatcher tick failed")

    @reminder_dispatcher.before_loop
    async def before_dispatcher(self):
        await self.bot.wait_until_ready()

    async def _dispatch_reminder(self, row):
        """Send one reminder to its announcement channel and squad DMs."""
        match_time = datetime.fromisoformat(row["match_time"])
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=timezone.utc)
        match_unix = int(match_time.timestamp())

        embed = match_reminder_embed(
            tournament_name=row["tournament_name"],
            tournament_id=row["tournament_id"],
            match_no=row["match_no"],
            match_id=row["match_id"],
            map_name=row["map"],
            match_time_unix=match_unix,
            offset_minutes=row["offset_minutes"],
            server_name=SERVER_NAME
        )

        # 1) Channel announcement
        if row["channel_id"]:
            channel = self.bot.get_channel(row["channel_id"])
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(row["channel_id"])
                except Exception:
                    channel = None
            if channel is not None:
                try:
                    await channel.send(
                        content=(
                            f"⏰ **[ {SERVER_NAME} • MATCH REMINDER ]** ⏰ "
                            f"@here Match #{row['match_no']} starts "
                            f"<t:{match_unix}:R>!"
                        ),
                        embed=embed
                    )
                except Exception:
                    logger.warning(
                        "Could not announce reminder #%s in channel %s",
                        row["id"], row["channel_id"]
                    )

        # 2) Squad member DMs
        recipients = await self._collect_recipients(row["tournament_id"])
        for uid in recipients:
            user = self.bot.get_user(uid)
            if user is None:
                try:
                    user = await self.bot.fetch_user(uid)
                except Exception:
                    continue
            try:
                await user.send(
                    content=(
                        f"⏰ **[ {SERVER_NAME} • MATCH REMINDER ]** ⏰ "
                        f"Match #{row['match_no']} of "
                        f"**{row['tournament_name']}** starts <t:{match_unix}:R>!"
                    ),
                    embed=embed
                )
            except (discord.Forbidden, discord.HTTPException):
                continue

        logger.info(
            "Dispatched reminder #%s (match #%s, %s min before) to %s member(s)",
            row["id"], row["match_id"], row["offset_minutes"], len(recipients)
        )

    async def _collect_recipients(self, tournament_id: int) -> set:
        """All captain + member user IDs across the tournament's squads."""
        uids = set()
        db = await connect()
        try:
            cur = await db.execute(
                """
                SELECT DISTINCT t.id, t.captain_id
                FROM teams t
                WHERE t.tournament_id=?
                UNION
                SELECT DISTINCT t.id, t.captain_id
                FROM teams t
                JOIN registrations r ON t.id = r.team_id
                WHERE r.tournament_id=?
                """,
                (tournament_id, tournament_id)
            )
            teams = await cur.fetchall()

            for tm in teams:
                if tm["captain_id"]:
                    uids.add(tm["captain_id"])
                cur = await db.execute(
                    "SELECT user_id FROM team_members "
                    "WHERE team_id=? AND user_id > 0",
                    (tm["id"],)
                )
                for mr in await cur.fetchall():
                    uids.add(mr["user_id"])
        finally:
            await db.close()
        return uids


async def setup(bot):
    await bot.add_cog(Reminders(bot))
