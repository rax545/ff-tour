"""Shared safe display, guild guard and slash-command error handling."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import require_tournament_guild

logger = logging.getLogger(__name__)


def display(value, limit=300):
    value = " ".join(str(value).split())
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value))[:limit]


async def command_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure) and interaction.response.is_done():
        return  # The guild guard already explained the denial privately.
    original = getattr(error, "original", error)
    if isinstance(original, app_commands.CommandOnCooldown):
        message = f"Please try again in {original.retry_after:.1f} seconds."
    elif isinstance(original, ValueError):
        message = display(original, 1800)
    elif isinstance(original, discord.HTTPException):
        message = "Discord could not deliver/update this item. Check channel and bot permissions, then retry."
    else:
        logger.error(
            "Arena command failed", exc_info=(type(original), original, original.__traceback__)
        )
        message = (
            "The operation could not be completed. Please retry or ask staff to check the bot logs."
        )
    if interaction.response.is_done():
        await interaction.followup.send(
            f"❌ {message}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )
    else:
        await interaction.response.send_message(
            f"❌ {message}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )


class TournamentCog(commands.Cog):
    async def interaction_check(self, interaction):
        return await require_tournament_guild(interaction)

    async def cog_app_command_error(self, interaction, error):
        await command_error(interaction, error)
