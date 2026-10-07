"""Shared isolated fixtures and Discord interaction doubles."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord

import database.db as db_module
from services.arena_common import database

NOW = int(datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc).timestamp())
GUILD = 100


class IsolatedArenaTest(unittest.IsolatedAsyncioTestCase):
    team_count = 3

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(
            db_module, "DATABASE_PATH", str(Path(self.temp.name) / "test.sqlite3")
        )
        self.path_patch.start()
        await db_module.init_db()
        async with database(write=True) as db:
            await db.execute(
                "INSERT INTO tournaments(id,name,max_teams) VALUES(1,'Arena Cup',32),(2,'Other Cup',12)"
            )
            for i in range(1, self.team_count + 1):
                await db.execute(
                    "INSERT INTO teams(id,tournament_id,name,tag,captain_id) VALUES(?,1,?,?,?)",
                    (i, f"Squad {i}", f"S{i}", 100 + i),
                )
                await db.execute(
                    "INSERT INTO team_members(id,team_id,user_id,ign,uid,role) VALUES(?,?,?,?,?,'Rusher')",
                    (i, i, 10 + i, f"Player {i}", f"10000{i}"),
                )
            await db.execute(
                "INSERT INTO teams(id,tournament_id,name,tag,captain_id) VALUES(99,2,'Other','O',999)"
            )
            await db.execute(
                "INSERT INTO team_members(id,team_id,user_id,ign,uid) VALUES(99,99,99,'Other','999999')"
            )
            await db.execute(
                "INSERT INTO matches(id,tournament_id,match_no,map) VALUES(1,1,1,'Bermuda'),(2,1,2,'Purgatory'),(99,2,1,'Alpine')"
            )

    async def asyncTearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()

    async def sql(self, sql, params=()):
        async with database(write=True) as db:
            await db.execute(sql, params)

    async def fetch(self, sql, params=()):
        async with database() as db:
            rows = await (await db.execute(sql, params)).fetchall()
            return [dict(r) for r in rows]

    async def squad_scores(self, match_id=1, *, verified=True):
        for i in range(1, self.team_count + 1):
            await self.sql(
                """INSERT INTO results(match_id,team_id,placement,kills,total_points,verified)
                VALUES(?,?,?,?,?,?)""",
                (match_id, i, i, 10 - i, 30 - i * 5, int(verified)),
            )


def interaction(*, guild_id=GUILD, user_id=11, administrator=False):
    value = MagicMock(spec=discord.Interaction)
    value.guild = MagicMock(spec=discord.Guild)
    value.guild.id = guild_id
    value.user = MagicMock(spec=discord.Member)
    value.user.id = user_id
    value.user.bot = False
    value.user.display_name = "Player"
    value.user.roles = []
    value.user.guild_permissions.administrator = administrator
    value.response = MagicMock()
    value.response.defer = AsyncMock()
    value.response.send_message = AsyncMock()
    value.response.is_done.return_value = False
    value.followup = MagicMock()
    value.followup.send = AsyncMock()
    value.message = MagicMock()
    value.message.edit = AsyncMock()
    value.data = {}
    return value
