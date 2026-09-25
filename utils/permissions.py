import discord
from config import ADMIN_ROLE_ID,MANAGER_ROLE_ID

def staff(member):
    if member.guild_permissions.administrator:return True
    return any(r.id in set(ADMIN_ROLE_ID) | {MANAGER_ROLE_ID} for r in member.roles)
async def require_staff(interaction):
    if not staff(interaction.user):
        await interaction.response.send_message('❌ Staff permission required.',ephemeral=True); return False
    return True
