import asyncio
import logging
import discord
from discord.ext import commands

from config import TOKEN, GUILD_ID, SERVER_NAME
from database.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("esports_bot")


class EsportsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        await init_db()
        for ext in ("cogs.esports", "cogs.admin", "cogs.support"):
            await self.load_extension(ext)
            logger.info("Loaded extension: %s", ext)

        if GUILD_ID:
            g = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=g)
            await self.tree.sync(guild=g)
            logger.info("Synced slash commands to guild: %s", GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Synced slash commands globally.")

    async def on_ready(self):
        logger.info("ONLINE: %s (ID: %s)", self.user, self.user.id)
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="Developed by Joy"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


async def main():
    if not TOKEN:
        raise RuntimeError("Bot token missing (DISCORD_TOKEN, BOT_TOKEN or TOKEN)")
    async with EsportsBot() as bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
