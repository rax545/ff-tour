import io
import re
import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands
from PIL import Image

from cogs.competition import Competition
from services.brackets import create_bracket
from services.clash import clash_poster_data
from services.predictions import open_predictions, prediction_pool
from services.squad_ops import open_ready_check, ready_status
from tests.helpers import GUILD, NOW, IsolatedArenaTest, interaction
from utils.arena_cards import (
    bracket_card,
    clash_card,
    hall_of_fame_card,
    passport_card,
    prediction_card,
)
from utils.permissions import require_tournament_guild
from views.arena import PredictionSelect, ReadyButton, prediction_view, ready_view


class GraphicsTests(IsolatedArenaTest):
    async def test_all_new_cards_are_valid_pngs_with_expected_dimensions(self):
        bracket = await create_bracket(GUILD, 1, 101)
        clash = await clash_poster_data(GUILD, 1, 1, 2)
        # The HOF graphic accepts an immutable snapshot independent of current bracket progress.
        record = {
            "id": 1,
            "tournament_name": "Arena Cup",
            "format": "battle_royale",
            "inducted_at": "2026-10-07",
            "podium": [{"id": 1, "name": "Squad", "tag": "SQ", "points": 100, "kills": 20}],
            "mvp": {},
        }
        pool = await open_predictions(GUILD, 2, NOW + 60, 101, now=NOW)
        roster = [{"ign": "Player", "uid": "100001", "role": "Rusher", "team_name": "Squad"}]
        cards = [
            (bracket_card(bracket), (1100, 720)),
            (clash_card(clash), (1600, 900)),
            (hall_of_fame_card([record]), (1600, 1000)),
            (prediction_card(pool, pool["entries"]), (1440, 1000)),
            (
                passport_card("Player", roster, {"kills": 7, "damage": 400, "matches": 1}),
                (1200, 720),
            ),
        ]
        for buffer, dimensions in cards:
            with self.subTest(dimensions=dimensions):
                image = Image.open(io.BytesIO(buffer.getvalue()))
                self.assertEqual(image.size, dimensions)
                self.assertEqual(image.format, "PNG")
                image.verify()
                self.assertLess(len(buffer.getvalue()), 8 * 1024 * 1024)

    async def test_clash_data_and_drawn_text_never_include_private_fields(self):
        await self.sql(
            "UPDATE matches SET room_id='PRIVATE-ROOM',room_password='PRIVATE-PASSWORD' WHERE id=1"
        )
        await self.sql("UPDATE team_members SET uid='PRIVATE-UID' WHERE id=1")
        data = await clash_poster_data(GUILD, 1, 1, 2)
        self.assertNotIn("PRIVATE-", str(data))
        with patch("utils.arena_cards._text") as text:
            clash_card(data)
            self.assertNotIn("PRIVATE-", str(text.call_args_list))
        with self.assertRaises(ValueError):
            await clash_poster_data(GUILD, 1, 1, 1)
        with self.assertRaises(ValueError):
            await clash_poster_data(GUILD, 1, 1, 99)

    async def test_extreme_text_does_not_crash_graphics_and_student_id_is_never_drawn(self):
        record = {
            "id": 1,
            "tournament_name": "Long " * 1000,
            "format": "knockout",
            "inducted_at": "2026-10-07",
            "podium": [
                {"id": 1, "name": "বাংলা Squad " * 300, "tag": "TEST", "points": 0, "kills": 0}
            ],
            "mvp": {},
        }
        self.assertGreater(len(hall_of_fame_card([record]).getvalue()), 1000)
        student = {
            "department": "CSE",
            "batch": "60",
            "section": "A",
            "student_id": "PRIVATE-STUDENT-ID",
        }
        with patch("utils.arena_cards._text") as text:
            passport_card("Player", [], {"kills": 0, "damage": 0, "matches": 0}, student)
            self.assertNotIn("PRIVATE-STUDENT-ID", str(text.call_args_list))


class DynamicComponentTests(IsolatedArenaTest):
    async def test_prediction_selector_reconstructs_without_an_in_memory_pool(self):
        now = int(time.time())
        pool = await open_predictions(GUILD, 1, now + 600, 101, now=now)
        view = prediction_view(pool, pool["entries"], 1)
        self.assertTrue(view.is_persistent())
        item = view.children[0].item
        value = interaction()
        value.data = {"values": ["2"]}
        custom = re.fullmatch(r"ff:prediction:(?P<pool_id>[0-9]+):(?P<page>[0-9]+)", item.custom_id)
        reconstructed = await PredictionSelect.from_custom_id(value, item, custom)
        with patch("utils.permissions.GUILD_ID", GUILD):
            await reconstructed.callback(value)
        value.response.defer.assert_awaited_once_with(ephemeral=True)
        self.assertEqual(
            (await prediction_pool(GUILD, pool["id"], 11, now=now))["my_pick"]["team_id"], 2
        )

    async def test_stale_selector_cannot_bypass_the_database_cutoff(self):
        now = int(time.time())
        pool = await open_predictions(GUILD, 1, now + 600, 101, now=now)
        selector = prediction_view(pool, pool["entries"], 1).children[0]
        await self.sql("UPDATE prediction_pools SET closes_at=? WHERE id=?", (now - 1, pool["id"]))
        value = interaction()
        value.response.is_done.return_value = True
        value.data = {"values": ["1"]}
        with patch("utils.permissions.GUILD_ID", GUILD):
            await selector.callback(value)
        self.assertIn("locked", value.followup.send.call_args.args[0])
        self.assertEqual(await self.fetch("SELECT * FROM prediction_picks"), [])

    async def test_ready_buttons_reconstruct_and_recheck_current_membership(self):
        now = int(time.time())
        check, created = await open_ready_check(GUILD, 1, 1, 101, now=now)
        row = await ready_status(GUILD, check["id"], 11, now=now)
        view = ready_view(row)
        self.assertTrue(view.is_persistent())
        item = view.children[0].item
        value = interaction()
        custom = re.fullmatch(r"ff:ready:(?P<check_id>[0-9]+):(?P<ready>[01])", item.custom_id)
        reconstructed = await ReadyButton.from_custom_id(value, item, custom)
        with patch("utils.permissions.GUILD_ID", GUILD):
            await reconstructed.callback(value)
        self.assertEqual((await ready_status(GUILD, check["id"], 101, now=now))["ready_ids"], [11])
        value.response.is_done.return_value = True
        await self.sql("DELETE FROM team_members WHERE id=1")
        with patch("utils.permissions.GUILD_ID", GUILD):
            await reconstructed.callback(value)
        self.assertIn("current squad members", value.followup.send.call_args.args[0])


class CommandSafetyTests(IsolatedArenaTest):
    async def test_all_extensions_register_and_serialize_with_discord_limits(self):
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        async with bot:
            for extension in (
                "cogs.esports",
                "cogs.admin",
                "cogs.support",
                "cogs.reminders",
                "cogs.arena",
                "cogs.competition",
            ):
                await bot.load_extension(extension)
            for group, command in [
                ("live", "list"),
                ("halloffame", "induct"),
                ("bracket", "resolve"),
                ("clash", "poster"),
                ("prediction", "settle"),
                ("radar", "scan"),
                ("squad", "readycheck"),
                ("result", "player"),
            ]:
                self.assertIsNotNone(bot.tree.get_command(group).get_command(command))
            for command in bot.tree.get_commands():
                payload = command.to_dict(bot.tree)
                self.assertLessEqual(len(payload.get("options", [])), 25)
                self.assertLessEqual(len(payload.get("description", "")), 100)
            await bot.unload_extension("cogs.competition")
            await bot.load_extension(
                "cogs.competition"
            )  # Persistent registration survives reloads too.

    async def test_wrong_guild_or_dm_is_rejected_before_private_data_is_queried(self):
        value = interaction(guild_id=200)
        with patch("utils.permissions.GUILD_ID", GUILD):
            self.assertFalse(await require_tournament_guild(value))
        self.assertTrue(value.response.send_message.call_args.kwargs["ephemeral"])
        value.guild = None
        with patch("utils.permissions.GUILD_ID", 0):
            self.assertFalse(await require_tournament_guild(value))

    async def test_radar_is_staff_only_and_every_delivery_is_ephemeral(self):
        bot = MagicMock()
        cog = Competition(bot)
        denied = interaction()
        with (
            patch("utils.permissions.GUILD_ID", GUILD),
            patch("cogs.competition.scan_rosters", AsyncMock()) as scan,
        ):
            await Competition.scan.callback(cog, denied, 1)
            scan.assert_not_awaited()
        self.assertTrue(denied.response.send_message.call_args.kwargs["ephemeral"])
        staff = interaction(administrator=True)
        with patch("utils.permissions.GUILD_ID", GUILD):
            await Competition.scan.callback(cog, staff, 1)
        staff.response.defer.assert_awaited_once_with(ephemeral=True)
        self.assertTrue(staff.followup.send.call_args.kwargs["ephemeral"])

    async def test_earlier_reminder_reschedule_clamps_deadlines_and_later_time_never_extends_them(
        self,
    ):
        from datetime import datetime, timezone

        from cogs.reminders import Reminders

        now = int(time.time())
        pool = await open_predictions(GUILD, 1, now + 3600, 101, now=now)
        check, _created = await open_ready_check(GUILD, 1, 1, 101, now=now)
        cog = Reminders(MagicMock())
        for cutoff in (now + 600, now + 5000):
            value = interaction(user_id=101, administrator=True)
            value.channel = MagicMock(spec=discord.TextChannel)
            value.channel.id = 201
            scheduled = datetime.fromtimestamp(cutoff, timezone.utc)
            with (
                patch("utils.permissions.GUILD_ID", GUILD),
                patch("cogs.reminders.parse_schedule_time", return_value=scheduled),
            ):
                await Reminders.reminder_set.callback(cog, value, 1, "test schedule", "5")
            self.assertEqual(
                (await prediction_pool(GUILD, pool["id"], now=now))["closes_at"], now + 600
            )
            self.assertEqual(
                (await ready_status(GUILD, check["id"], 101, now=now))["expires_at"], now + 600
            )

    async def test_bound_room_credentials_are_delivered_only_to_opponent_captains(self):
        from cogs.esports import Esports
        from services.brackets import bind_match

        node = (await create_bracket(GUILD, 1, 101))["nodes"][1]
        await bind_match(GUILD, node["id"], 1, 101)
        members = {}
        for captain in (101, 102, 103):
            member = MagicMock(spec=discord.Member)
            member.bot = False
            member.send = AsyncMock()
            members[captain] = member
        value = interaction(user_id=101, administrator=True)
        value.guild.get_member.side_effect = members.get
        cog = Esports(MagicMock())
        with patch("utils.permissions.GUILD_ID", GUILD):
            await Esports.room.callback(cog, value, 1, "PRIVATE-ROOM", "PRIVATE-PASSWORD")
        members[101].send.assert_not_awaited()
        members[102].send.assert_awaited_once()
        members[103].send.assert_awaited_once()
        self.assertNotIn(
            "PRIVATE-PASSWORD", str(value.followup.send.call_args.kwargs["embed"].to_dict())
        )
