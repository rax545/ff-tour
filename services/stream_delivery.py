"""Discord broadcast delivery, separated from SQLite state transitions for testing."""

import asyncio
import io
import logging

import discord

from config import SERVER_NAME
from database.db import get_setting
from services.streams import is_current_stream, save_announcement
from utils.embeds import base
from utils.interactions import display
from utils.validation import validate_stream_url

logger = logging.getLogger(__name__)
NO_PINGS = discord.AllowedMentions.none()


def stream_link_view(row):
    view = discord.ui.View(timeout=None)
    try:
        url = validate_stream_url(row["stream_url"])
    except ValueError:
        return view
    view.add_item(
        discord.ui.Button(label="Watch Live" if row["stream_live"] else "Watch Replay", url=url)
    )
    return view


def stream_embed(row):
    live = bool(row["stream_live"])
    embed = base(
        f"{'🔴 LIVE NOW' if live else '⚪ STREAM ENDED'} • Match #{row['match_no']}",
        f"**{display(row['tournament_name'], 180)}**\n"
        f"{display(SERVER_NAME, 100)} • {display(row['stream_platform'], 40)}\n"
        "Use the button below to watch the broadcast."
        if live
        else f"**{display(row['tournament_name'], 180)}**\nStaff marked this stream offline. The replay link is retained.",
        color=discord.Color.red() if live else discord.Color.dark_grey(),
    )
    embed.add_field(name="Map", value=display(row["map"] or "TBA", 100))
    if live:
        embed.set_image(url="attachment://live-broadcast.png")
    embed.set_footer(
        text="Staff-controlled status • The bot does not host or stop provider streams."
    )
    return embed


async def _channel(guild, channel_id):
    if not channel_id:
        return None
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        channel = await guild.fetch_channel(int(channel_id))
    if channel.guild.id != guild.id or not hasattr(channel, "send"):
        return None
    return channel


async def update_stopped_announcement(guild, row):
    """Best-effort remote cleanup; deleted messages/permissions never undo saved state."""
    if not row or not row["stream_message_id"]:
        return
    try:
        channel = await _channel(guild, row["stream_channel_id"])
        if channel:
            message = await channel.fetch_message(row["stream_message_id"])
            offline = {**row, "stream_live": 0}
            await message.edit(
                embed=stream_embed(offline), view=stream_link_view(offline), attachments=[]
            )
    except (discord.HTTPException, ValueError):
        logger.info("Could not refresh offline broadcast message for match %s", row["id"])


async def post_announcement(interaction, row, image_bytes):
    target = None
    try:
        target = await _channel(interaction.guild, await get_setting("notification_channel_id"))
    except (discord.HTTPException, ValueError):
        pass
    candidates = [target] if target else []
    if not target or target.id != interaction.channel_id:
        candidates.append(interaction.channel)
    for channel in candidates:
        if channel is None:
            continue
        try:
            # Fresh files for retries: discord.py closes a File after sending it.
            message = await channel.send(
                embed=stream_embed(row),
                file=discord.File(io.BytesIO(image_bytes), filename="live-broadcast.png"),
                view=stream_link_view(row),
                allowed_mentions=NO_PINGS,
            )
            current = await save_announcement(
                row["id"], row["stream_revision"], channel.id, message.id
            )
            if not current:
                try:
                    offline = {**row, "stream_live": 0}
                    await message.edit(
                        embed=stream_embed(offline), view=stream_link_view(offline), attachments=[]
                    )
                except discord.HTTPException:
                    pass
            return message, current
        except discord.HTTPException:
            logger.info(
                "Live announcement delivery failed in channel %s; trying fallback", channel.id
            )
    raise ValueError(
        "Stream status was saved, but no announcement could be posted. Fix Send Messages / Attach Files / Embed Links permissions, then retry /match stream with rebroadcast:true."
    )


async def notify_players(guild, row, recipients, image_bytes):
    """Bounded fan-out. Failed/blocked DMs are counted, not treated as delivery success."""
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    semaphore = asyncio.Semaphore(4)

    async def deliver(user_id, team):
        async with semaphore:
            if not await is_current_stream(row["id"], row["stream_revision"]):
                counts["skipped"] += 1
                return
            try:
                async with asyncio.timeout(45):
                    user = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    if user.bot:
                        counts["skipped"] += 1
                        return
                    if not await is_current_stream(row["id"], row["stream_revision"]):
                        counts["skipped"] += 1
                        return
                    await user.send(
                        content=f"🔴 {display(team['name'], 120)} — Match #{row['match_no']} is streaming now!",
                        embed=stream_embed(row),
                        file=discord.File(io.BytesIO(image_bytes), filename="live-broadcast.png"),
                        view=stream_link_view(row),
                        allowed_mentions=NO_PINGS,
                    )
                counts["sent"] += 1
            except (discord.HTTPException, TimeoutError):
                counts["failed"] += 1

    await asyncio.gather(*(deliver(user_id, team) for user_id, team in recipients.items()))
    return counts
