"""Startup wiring regression tests for ``bot.py``.

The manual merge of the god-tier upgrade duplicated the ``load_extension`` call
inside ``EsportsBot.setup_hook``; because ``commands.Bot.load_extension`` raises
``ExtensionAlreadyLoaded`` for an already-loaded cog, the bot crashed on startup
while every offline test still passed (none of them executed ``setup_hook``).
These tests execute the real startup path with a disposable database so a
duplicate or missing cog registration fails CI.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db_module  # noqa: E402
import bot as bot_module  # noqa: E402

EXPECTED_EXTENSIONS = {
    "cogs.esports",
    "cogs.admin",
    "cogs.support",
    "cogs.reminders",
    "cogs.arena",
    "cogs.competition",
    "cogs.economy",
    "cogs.players",
    "cogs.security",
}


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_loads_every_extension_exactly_once(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(
                db_module, "DATABASE_PATH", str(Path(folder) / "startup.sqlite3")
            ):
                bot = bot_module.EsportsBot()
                # Keep startup fully offline: no Discord HTTP calls.
                bot.tree.sync = AsyncMock()
                bot.tree.copy_global_to = MagicMock()
                async with bot:
                    await bot.setup_hook()  # login()/start() would run this in prod
                    loaded = set(bot.extensions)
                self.assertEqual(loaded, EXPECTED_EXTENSIONS)
                bot.tree.sync.assert_awaited()

    async def test_setup_hook_is_idempotent_per_extension(self):
        # Loading any registered cog twice must raise, which is exactly what a
        # duplicated load_extension line in setup_hook would do.
        from discord.ext import commands
        import discord

        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        async with bot:
            await bot.load_extension("cogs.support")
            with self.assertRaises(commands.ExtensionAlreadyLoaded):
                await bot.load_extension("cogs.support")


if __name__ == "__main__":
    unittest.main()
