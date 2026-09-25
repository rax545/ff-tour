import discord
from discord.ext import commands
from discord import app_commands
from database.db import connect
from utils.embeds import base,ok
class Support(commands.Cog):
    def __init__(self,bot):self.bot=bot
    @app_commands.command(name='ticket',description='Create private esports support ticket')
    @app_commands.describe(ticket_type='registration/payment/match/report/general')
    async def ticket(self,interaction,ticket_type:str):
        g=interaction.guild; overwrites={g.default_role:discord.PermissionOverwrite(view_channel=False),interaction.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),g.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True)}
        cat=discord.utils.get(g.categories,name='ESPORTS TICKETS') or await g.create_category('ESPORTS TICKETS')
        ch=await g.create_text_channel(f'ticket-{interaction.user.name[:18]}',category=cat,overwrites=overwrites)
        db=await connect(); cur=await db.execute('INSERT INTO tickets(channel_id,opener_id,type) VALUES(?,?,?)',(ch.id,interaction.user.id,ticket_type)); tid=cur.lastrowid; await db.commit(); await db.close()
        await ch.send(embed=base(f'🎫 Ticket #{tid}',f'Category: **{ticket_type}**\nPlease provide your tournament/team details and explain the issue.'))
        await interaction.response.send_message(embed=ok(f'Ticket created: {ch.mention}'),ephemeral=True)
async def setup(bot):await bot.add_cog(Support(bot))
