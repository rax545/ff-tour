import asyncio
import logging
import os
import discord
from aiohttp import web
from discord.ext import commands

from config import TOKEN, GUILD_ID, SERVER_NAME, DEVELOPER
from database.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("esports_bot")


# 🔥 Render-এর জন্য Keep-Alive Web Port
async def start_web_server():
    port = int(os.getenv("PORT", "10000") or 10000)
    app = web.Application()

    async def handle_ping(request):
        return web.Response(
            text=f"🐺 {SERVER_NAME} Esports Bot\nDeveloped by {DEVELOPER}\nStatus: ONLINE 🟢\n",
            content_type="text/plain"
        )

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Keep-alive Web Server listening on port %s for Render hosting", port)
    return runner


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
        self.presence_task = None

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

    async def presence_loop(self):
        await self.wait_until_ready()
        activities = [
            discord.Activity(
                type=discord.ActivityType.competing,
                name=f"Free Fire • {SERVER_NAME}"
            ),
            discord.Activity(
                type=discord.ActivityType.watching,
                name=f"Esports Arena | Developed by {DEVELOPER}"
            ),
            discord.Activity(
                type=discord.ActivityType.playing,
                name=f"/tournament list | Dev: {DEVELOPER}"
            ),
        ]
        while not self.is_closed():
            for act in activities:
                try:
                    await self.change_presence(status=discord.Status.online, activity=act)
                except Exception:
                    pass
                await asyncio.sleep(25)

    async def on_ready(self):
        logger.info("ONLINE: %s (ID: %s)", self.user, self.user.id)
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name=f"Free Fire • {SERVER_NAME} | Developed by {DEVELOPER}"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)
        if not self.presence_task or self.presence_task.done():
            self.presence_task = asyncio.create_task(self.presence_loop())


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing in .env")

    # Start health-check web server for Render
    web_runner = await start_web_server()

    try:
        async with EsportsBot() as bot:
            await bot.start(TOKEN)
    finally:
        if web_runner:
            await web_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
