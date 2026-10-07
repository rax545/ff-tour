"""Player passport, digital certificates and squad war room slash commands."""
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from services.arena import player_passport, issue_certificate, verify_certificate, revoke_certificate
from services.war_rooms import WarRoomService
from utils.cards import passport, certificate
from utils.embeds import base, err, ok
from utils.permissions import require_staff


@app_commands.guild_only()
class Arena(commands.Cog):
    certificate_group = app_commands.Group(name='certificate', description='Issue and verify digital certificates', guild_only=True)
    squad = app_commands.Group(name='squad', description='Private squad war rooms', guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        self.rooms = WarRoomService()

    @app_commands.command(name='passport', description='View your private player passport and verified individual stats')
    @app_commands.guild_only()
    async def player_passport_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        rosters, stats, student = await player_passport(interaction.user.id)
        if not rosters:
            return await interaction.followup.send(embed=err('No linked player roster. Ask your captain to link your Discord account via /team addplayer.'), ephemeral=True)
        image = await asyncio.to_thread(passport, interaction.user.display_name, rosters, stats, student)
        await interaction.followup.send(file=discord.File(image, filename='player-passport.png'),
            content='Private passport • Only verified individual results are counted. Student ID is never included.', ephemeral=True)

    @certificate_group.command(name='issue', description='Staff: issue a registered player achievement certificate')
    async def issue(self, interaction: discord.Interaction, tournament_id: int, team_id: int,
                    recipient: discord.Member, award: app_commands.Range[str, 1, 80]):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            record = await issue_certificate(interaction.guild.id, tournament_id,team_id,recipient.id,award,interaction.user.id)
        except ValueError as exc:
            return await interaction.followup.send(embed=err(str(exc)), ephemeral=True)
        image = await asyncio.to_thread(certificate,record)
        await interaction.followup.send(file=discord.File(image,filename=f'{record["code"]}.png'),
            content=f'Certificate `{record["code"]}` • Share this image with the recipient. Verify using `/certificate verify`.', ephemeral=True)

    @certificate_group.command(name='verify', description='Check an issued certificate in this server registry')
    async def verify(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)
        record = await verify_certificate(interaction.guild.id,code)
        if not record:
            return await interaction.followup.send(embed=err('Certificate not found in this server.'), ephemeral=True)
        embed = base('Digital Certificate • ' + ('REVOKED' if record['revoked_at'] else 'VALID'))
        for label,key in [('Registry code','code'),('Recipient','recipient_name'),('Tournament','tournament_name'),
                          ('Squad','team_name'),('Award','award'),('Issued at (UTC)','issued_at')]:
            embed.add_field(name=label,value=discord.utils.escape_markdown(str(record[key]))[:1024],inline=False)
        await interaction.followup.send(embed=embed,ephemeral=True)

    @certificate_group.command(name='revoke', description='Staff: permanently revoke an issued certificate')
    async def revoke(self, interaction: discord.Interaction, code: str):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        changed = await revoke_certificate(interaction.guild.id,code,interaction.user.id)
        await interaction.followup.send(embed=ok('Certificate revoked.') if changed else err('Not found or already revoked.'),ephemeral=True)

    async def room_action(self, interaction, team_id, close=False):
        await interaction.response.defer(ephemeral=True)
        try:
            rooms = await self.rooms.manage(interaction.guild,interaction.user,team_id,close=close)
        except ValueError as exc:
            return await interaction.followup.send(embed=err(str(exc)),ephemeral=True)
        except discord.HTTPException:
            return await interaction.followup.send(embed=err('Discord could not update the room. Check Manage Channels / View Channel permissions, then retry.'),ephemeral=True)
        text = 'Squad war room closed.' if close else f'Private rooms ready: {rooms[0].mention} • {rooms[1].mention}\nRoster access synchronized. Server administrators can always access channels.'
        await interaction.followup.send(embed=ok(text),ephemeral=True)

    @squad.command(name='warroom', description='Captain/staff: create or synchronize private text and voice rooms')
    async def warroom(self, interaction: discord.Interaction, team_id: int):
        await self.room_action(interaction,team_id)

    @squad.command(name='close', description='Captain/staff: delete the squad text and voice war rooms')
    async def close(self, interaction: discord.Interaction, team_id: int):
        await self.room_action(interaction,team_id,close=True)


async def setup(bot):
    await bot.add_cog(Arena(bot))
