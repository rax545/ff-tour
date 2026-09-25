import discord
from discord.ext import commands
from discord import app_commands
from database.db import connect,audit
from utils.embeds import base,ok,err
from utils.permissions import require_staff
class Admin(commands.Cog):
    def __init__(self,bot):self.bot=bot
    admin=app_commands.Group(name='admin',description='Esports administration')
    @admin.command(name='dashboard',description='Show live admin dashboard')
    async def dashboard(self,interaction):
        if not await require_staff(interaction):return
        db=await connect(); stats={}
        for table in ('tournaments','teams','matches','results','payments','reports','tickets'):
            cur=await db.execute(f'SELECT COUNT(*) c FROM {table}'); stats[table]=(await cur.fetchone())['c']
        await db.close(); e=base('🛡️ ADMIN COMMAND CENTER','Live database overview.');
        for k,v in stats.items():e.add_field(name=k.title(),value=str(v),inline=True)
        e.add_field(name='Quick Actions',value='`/admin payment` • `/admin result` • `/admin close`\n`/match room` • `/result verify`',inline=False); await interaction.response.send_message(embed=e,ephemeral=True)
    @admin.command(name='payment',description='Approve/reject payment')
    async def payment(self,interaction,payment_id:int,decision:str):
        if not await require_staff(interaction):return
        decision=decision.lower();
        if decision not in ('approve','reject'):return await interaction.response.send_message(embed=err('Decision must be approve or reject.'),ephemeral=True)
        db=await connect(); cur=await db.execute('UPDATE payments SET status=? WHERE id=?',('approved' if decision=='approve' else 'rejected',payment_id)); await db.commit(); await db.close()
        if not cur.rowcount:return await interaction.response.send_message(embed=err('Payment not found.'),ephemeral=True)
        await audit(interaction.user.id,'payment_review',f'{payment_id}:{decision}'); await interaction.response.send_message(embed=ok(f'Payment **#{payment_id}** → **{decision.upper()}**'))
    @admin.command(name='close',description='Close tournament')
    async def close(self,interaction,tournament_id:int):
        if not await require_staff(interaction):return
        db=await connect(); cur=await db.execute("UPDATE tournaments SET status='closed' WHERE id=?",(tournament_id,)); await db.commit(); await db.close();
        if not cur.rowcount:return await interaction.response.send_message(embed=err('Tournament not found.'),ephemeral=True)
        await interaction.response.send_message(embed=ok(f'Tournament **#{tournament_id}** closed.'))
async def setup(bot):await bot.add_cog(Admin(bot))
