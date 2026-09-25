import discord
from database.db import connect
from utils.embeds import base,ok,err

class RegistrationModal(discord.ui.Modal,title='Team Registration'):
    team_id=discord.ui.TextInput(label='Team ID',placeholder='Example: 12')
    async def on_submit(self,interaction):
        view=self.view_ref
        await view.register(interaction,int(self.team_id.value))

class TournamentPanel(discord.ui.View):
    def __init__(self,tournament_id):
        super().__init__(timeout=None); self.tournament_id=tournament_id
    @discord.ui.button(label='🏆 Register Team',style=discord.ButtonStyle.success,custom_id='ff:register')
    async def register_btn(self,interaction,button):
        modal=RegistrationModal(); modal.view_ref=self; await interaction.response.send_modal(modal)
    @discord.ui.button(label='📋 Tournament Info',style=discord.ButtonStyle.primary,custom_id='ff:info')
    async def info_btn(self,interaction,button):
        db=await connect(); cur=await db.execute('SELECT * FROM tournaments WHERE id=?',(self.tournament_id,)); t=await cur.fetchone(); cur=await db.execute("SELECT COUNT(*) c FROM teams WHERE tournament_id=?",(self.tournament_id,)); c=await cur.fetchone(); await db.close()
        if not t:return await interaction.response.send_message(embed=err('Tournament not found.'),ephemeral=True)
        e=base('🏆 '+t['name'],t['description'] or 'Official tournament information.'); e.add_field(name='Mode',value='Squad'); e.add_field(name='Slots',value=f"{c['c']}/{t['max_teams']}"); e.add_field(name='Entry',value=f"৳{t['entry_fee']:g}"); e.add_field(name='Prize Pool',value=f"৳{t['prize_pool']:g}"); e.add_field(name='Status',value=t['status'].upper()); await interaction.response.send_message(embed=e,ephemeral=True)
    async def register(self,interaction,team_id):
        db=await connect(); cur=await db.execute('SELECT * FROM tournaments WHERE id=?',(self.tournament_id,)); t=await cur.fetchone(); cur=await db.execute('SELECT * FROM teams WHERE id=? AND captain_id=?',(team_id,interaction.user.id)); team=await cur.fetchone()
        if not t or not team: await db.close(); return await interaction.response.send_message(embed=err('Tournament/team not found or you are not captain.'),ephemeral=True)
        if t['status']!='open': await db.close(); return await interaction.response.send_message(embed=err('Registration is closed.'),ephemeral=True)
        cur=await db.execute("SELECT COUNT(*) c FROM registrations WHERE tournament_id=? AND status='registered'",(self.tournament_id,)); count=(await cur.fetchone())['c']
        if count>=t['max_teams']: await db.close(); return await interaction.response.send_message(embed=err('Tournament is full.'),ephemeral=True)
        try: await db.execute("INSERT INTO registrations(tournament_id,team_id) VALUES(?,?)",(self.tournament_id,team_id)); await db.commit()
        except Exception: await db.close(); return await interaction.response.send_message(embed=err('This team is already registered.'),ephemeral=True)
        await db.close(); await interaction.response.send_message(embed=ok(f'**{team["name"]} [{team["tag"]}]** registered for **{t["name"]}**.'),ephemeral=True)
