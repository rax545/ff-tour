import asyncio

from services.brackets import bind_match, create_bracket
from services.squad_ops import (
    close_ready_check,
    open_ready_check,
    ready_status,
    save_plan,
    set_ready,
    squad_briefing,
)
from tests.helpers import GUILD, NOW, IsolatedArenaTest


class SquadTests(IsolatedArenaTest):
    async def check(self, actor=101, **kwargs):
        return await open_ready_check(GUILD, 1, 1, actor, now=NOW, **kwargs)

    async def test_only_captain_or_staff_can_save_and_only_current_roster_can_read_strategy(self):
        with self.assertRaises(ValueError):
            await save_plan(GUILD, 1, 11, "Bermuda", "Clock Tower", "Rotate north")
        await save_plan(GUILD, 1, 101, "Bermuda", "Clock Tower", "Private tactical note")
        briefing = await squad_briefing(GUILD, 1, 11)
        self.assertEqual(briefing["plan"]["strategy"], "Private tactical note")
        with self.assertRaises(ValueError):
            await squad_briefing(GUILD, 1, 12)
        await save_plan(GUILD, 1, 999, "Kalahari", "Refinery", "Staff correction", is_staff=True)
        self.assertEqual((await squad_briefing(GUILD, 1, 11))["plan"]["map_name"], "Kalahari")
        self.assertNotIn("Private tactical note", str(await self.fetch("SELECT * FROM audit_logs")))

    async def test_map_and_note_length_validation(self):
        for map_name, zone, note in [
            ("Unknown", "Zone", "Plan"),
            ("Bermuda", "", "Plan"),
            ("Bermuda", "x" * 81, "Plan"),
            ("Bermuda", "Zone", "x" * 1501),
        ]:
            with self.assertRaises(ValueError):
                await save_plan(GUILD, 1, 101, map_name, zone, note)

    async def test_concurrent_open_reuses_one_id_with_a_one_hour_expiry(self):
        outcomes = await asyncio.gather(*(self.check() for _ in range(4)))
        self.assertEqual(len({c["id"] for c, created in outcomes}), 1)
        self.assertEqual(sum(created for check, created in outcomes), 1)
        self.assertEqual(outcomes[0][0]["expires_at"], NOW + 3600)
        self.assertEqual(len(await self.fetch("SELECT * FROM squad_ready_checks")), 1)
        with self.assertRaises(ValueError):
            await open_ready_check(GUILD, 1, 2, 11, now=NOW)

    async def test_readiness_is_self_only_idempotent_and_toggleable(self):
        check, created = await self.check()
        await asyncio.gather(*(set_ready(GUILD, check["id"], 11, now=NOW) for _ in range(4)))
        row = await ready_status(GUILD, check["id"], 101, now=NOW)
        self.assertEqual(row["ready_ids"], [11])
        self.assertEqual(row["pending_ids"], [101])
        self.assertEqual(len(await self.fetch("SELECT * FROM squad_ready_responses")), 1)
        with self.assertRaises(ValueError):
            await set_ready(
                GUILD, check["id"], 999, now=NOW
            )  # An off-roster staff member cannot be ready for a player.
        await set_ready(GUILD, check["id"], 11, False, now=NOW)
        self.assertEqual((await ready_status(GUILD, check["id"], 11, now=NOW))["ready_ids"], [])

    async def test_removed_members_cannot_access_briefings_or_change_saved_responses(self):
        check, created = await self.check()
        await set_ready(GUILD, check["id"], 11, now=NOW)
        await self.sql("DELETE FROM team_members WHERE id=1")
        for call in (
            squad_briefing(GUILD, 1, 11),
            ready_status(GUILD, check["id"], 11, now=NOW),
            set_ready(GUILD, check["id"], 11, now=NOW),
        ):
            with self.assertRaises(ValueError):
                await call
        self.assertEqual((await ready_status(GUILD, check["id"], 101, now=NOW))["ready_ids"], [])

    async def test_check_closes_at_match_start_expiry_or_captain_close_and_never_reopens(self):
        await self.sql("UPDATE matches SET scheduled_at=? WHERE id=1", (f"<t:{NOW + 30}:F>",))
        check, created = await self.check()
        self.assertEqual(check["expires_at"], NOW + 30)
        with self.assertRaises(ValueError):
            await set_ready(GUILD, check["id"], 11, now=NOW + 30)
        with self.assertRaises(ValueError):
            await close_ready_check(GUILD, check["id"], 11)
        await close_ready_check(GUILD, check["id"], 101)
        with self.assertRaises(ValueError):
            await set_ready(GUILD, check["id"], 11, now=NOW)
        with self.assertRaises(ValueError):
            await self.check()
        with self.assertRaises(ValueError):
            await ready_status(200, check["id"], 11, now=NOW)

    async def test_wrong_fixture_past_schedule_or_nonopponent_bracket_team_is_rejected(self):
        with self.assertRaises(ValueError):
            await open_ready_check(GUILD, 1, 99, 101, now=NOW)
        await self.sql("UPDATE matches SET scheduled_at=? WHERE id=1", (f"<t:{NOW - 1}:F>",))
        with self.assertRaises(ValueError):
            await self.check()
        await self.sql("UPDATE matches SET scheduled_at='TBA' WHERE id=1")
        node = (await create_bracket(GUILD, 1, 101))["nodes"][1]
        await bind_match(GUILD, node["id"], 1, 101)
        with self.assertRaises(ValueError):
            await self.check()

    async def test_team_deletion_cascades_private_notes_checks_and_votes(self):
        await save_plan(GUILD, 1, 101, "Bermuda", "Clock Tower", "Rotate")
        check, created = await self.check()
        await set_ready(GUILD, check["id"], 11, now=NOW)
        await self.sql("DELETE FROM teams WHERE id=1")
        for table in ("squad_plans", "squad_ready_checks", "squad_ready_responses"):
            self.assertEqual(await self.fetch(f"SELECT * FROM {table}"), [])

    async def test_saved_war_room_sync_removes_old_member_overwrite_and_keeps_staff(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        import discord

        from services.war_rooms import WarRoomService

        guild = MagicMock(spec=discord.Guild)
        guild.id = GUILD
        guild.me = MagicMock(spec=discord.Member)
        guild.default_role = MagicMock(spec=discord.Role)
        captain = MagicMock(spec=discord.Member)
        player = MagicMock(spec=discord.Member)
        role = MagicMock(spec=discord.Role)
        guild.get_member.side_effect = lambda user_id: {101: captain, 11: player}.get(user_id)
        guild.get_role.side_effect = lambda role_id: role if role_id == 234 else None
        text = MagicMock(spec=discord.TextChannel)
        text.id, text.guild, text.edit = 201, guild, AsyncMock()
        voice = MagicMock(spec=discord.VoiceChannel)
        voice.id, voice.guild, voice.edit = 202, guild, AsyncMock()
        guild.create_text_channel = AsyncMock(return_value=text)
        guild.create_voice_channel = AsyncMock(return_value=voice)
        guild.get_channel.return_value = None
        actor = MagicMock(spec=discord.Member)
        actor.id = 101
        service = WarRoomService()
        with (
            patch("services.war_rooms.GUILD_ID", GUILD),
            patch("services.war_rooms.STAFF_ROLE_IDS", {234}),
        ):
            await service.manage(guild, actor, 1)
            rules = guild.create_text_channel.call_args.kwargs["overwrites"]
            self.assertFalse(rules[guild.default_role].view_channel)
            self.assertTrue(rules[guild.me].attach_files)
            self.assertIn(player, rules)
            await self.sql("DELETE FROM team_members WHERE id=1")
            guild.get_channel.side_effect = lambda channel_id: {201: text, 202: voice}.get(
                channel_id
            )
            await service.manage(guild, actor, 1)
            synced = text.edit.call_args.kwargs["overwrites"]
            self.assertNotIn(player, synced)
            self.assertIn(captain, synced)
            self.assertIn(role, synced)
            guild.create_text_channel.assert_awaited_once()
