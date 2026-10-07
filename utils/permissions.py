"""Shared guild-only staff authorization."""

import discord

from config import GUILD_ID, STAFF_ROLE_IDS


def staff(member):
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator or any(
        role.id in STAFF_ROLE_IDS for role in member.roles
    )


async def require_tournament_guild(interaction):
    if not interaction.guild or (GUILD_ID and interaction.guild.id != GUILD_ID):
        await interaction.response.send_message(
            "❌ Use this command in the configured tournament server.", ephemeral=True
        )
        return False
    return True


async def require_staff(interaction):
    if not await require_tournament_guild(interaction):
        return False
    if not staff(interaction.user):
        await interaction.response.send_message(
            "❌ Staff permission required in a server.", ephemeral=True
        )
        return False
    return True
