"""Shared guild-only staff authorization."""
import discord
from config import STAFF_ROLE_IDS


def staff(member):
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator or any(
        role.id in STAFF_ROLE_IDS for role in member.roles
    )


async def require_staff(interaction):
    if not interaction.guild or not staff(interaction.user):
        await interaction.response.send_message('❌ Staff permission required in a server.', ephemeral=True)
        return False
    return True
