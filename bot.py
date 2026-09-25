import asyncio,logging,discord
from discord.ext import commands
from database.db import init_db
from config import TOKEN,GUILD_ID
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
class EsportsBot(commands.Bot):
    def __init__(self):
        intents=discord.Intents.default(); intents.members=True
        super().__init__(command_prefix='!',intents=intents)
    async def setup_hook(self):
        await init_db()
        for ext in ('cogs.esports','cogs.admin','cogs.support'):
            await self.load_extension(ext)
        if GUILD_ID:
            g=discord.Object(id=GUILD_ID); self.tree.copy_global_to(guild=g); await self.tree.sync(guild=g)
        else: await self.tree.sync()
    async def on_ready(self): logging.info('ONLINE: %s (%s)',self.user,self.user.id)
async def main():
    if not TOKEN: raise RuntimeError('DISCORD_TOKEN missing in .env')
    async with EsportsBot() as bot: await bot.start(TOKEN)
if __name__=='__main__': asyncio.run(main())
