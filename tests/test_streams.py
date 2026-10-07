import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from services.stream_delivery import (
    notify_players,
    post_announcement,
    stream_embed,
    update_stopped_announcement,
)
from services.streams import (
    get_stream,
    is_current_stream,
    list_streams,
    save_announcement,
    start_stream,
    stop_stream,
    stream_recipients,
)
from tests.helpers import GUILD, IsolatedArenaTest, interaction
from utils.validation import validate_stream_url


def forbidden():
    return discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"),
        {"message": "Missing permissions", "code": 50013},
    )


class StreamTests(IsolatedArenaTest):
    async def start(self, **kwargs):
        return await start_stream(1, "https://youtu.be/live", "YouTube", 101, **kwargs)

    async def test_start_is_idempotent_concurrently_and_rebroadcast_is_explicit(self):
        outcomes = await asyncio.gather(*(self.start() for _ in range(5)))
        self.assertEqual(sum(changed for row, changed in outcomes), 1)
        row = await get_stream(1)
        self.assertEqual(row["stream_revision"], 1)
        self.assertIsNotNone(row["stream_started_at"])
        self.assertTrue(await is_current_stream(1, 1))
        row, changed = await self.start(rebroadcast=True)
        self.assertTrue(changed)
        self.assertEqual(row["stream_revision"], 2)
        self.assertFalse(await is_current_stream(1, 1))
        self.assertEqual(len(await list_streams()), 1)
        self.assertEqual(await list_streams(2), [])

    async def test_stop_retains_replay_and_saved_message_and_is_idempotent(self):
        row, changed = await self.start()
        self.assertTrue(await save_announcement(1, row["stream_revision"], 201, 301))
        stopped = await stop_stream(1, 101)
        self.assertEqual(stopped["stream_url"], row["stream_url"])
        self.assertEqual(stopped["stream_message_id"], 301)
        self.assertIsNotNone(stopped["stream_ended_at"])
        self.assertEqual((await stop_stream(1))["stream_ended_at"], stopped["stream_ended_at"])
        self.assertFalse(await save_announcement(1, row["stream_revision"], 201, 302))
        self.assertIsNone(await stop_stream(12345))
        self.assertEqual(await list_streams(), [])

    async def test_captains_and_linked_players_are_deduplicated_across_squads(self):
        await self.sql("UPDATE teams SET captain_id=101 WHERE id=2")
        await self.sql("UPDATE team_members SET user_id=11 WHERE id=2")
        recipients, teams = await stream_recipients(GUILD, 1)
        self.assertEqual(teams, 3)
        self.assertEqual(set(recipients), {101, 103, 11, 13})

    async def test_notification_channel_send_failure_falls_back_with_fresh_attachment(self):
        row, changed = await self.start()
        value = interaction(administrator=True)
        value.channel_id = 201
        configured = MagicMock(spec=discord.TextChannel)
        configured.id, configured.guild = 202, value.guild
        configured.send = AsyncMock(side_effect=forbidden())
        fallback = MagicMock(spec=discord.TextChannel)
        fallback.id, fallback.guild = 201, value.guild
        message = MagicMock(spec=discord.Message)
        message.id = 303
        message.edit = AsyncMock()
        fallback.send = AsyncMock(return_value=message)
        value.channel = fallback
        value.guild.get_channel.return_value = configured
        with patch("services.stream_delivery.get_setting", AsyncMock(return_value="202")):
            posted, current = await post_announcement(value, row, b"PNG fixture")
        self.assertTrue(current)
        self.assertIs(posted, message)
        configured.send.assert_awaited_once()
        fallback.send.assert_awaited_once()
        first_file = configured.send.call_args.kwargs["file"]
        second_file = fallback.send.call_args.kwargs["file"]
        self.assertIsNot(first_file, second_file)
        self.assertEqual((await get_stream(1))["stream_channel_id"], 201)

    async def test_all_channel_failures_leave_retryable_live_state_with_clear_error(self):
        row, changed = await self.start()
        value = interaction(administrator=True)
        value.channel_id = 201
        value.channel = MagicMock(spec=discord.TextChannel)
        value.channel.id = 201
        value.channel.send = AsyncMock(side_effect=forbidden())
        with (
            patch("services.stream_delivery.get_setting", AsyncMock(return_value=None)),
            self.assertRaises(ValueError),
        ):
            await post_announcement(value, row, b"PNG fixture")
        self.assertEqual((await get_stream(1))["stream_live"], 1)
        self.assertEqual((await get_stream(1))["stream_message_id"], 0)

    async def test_broadcast_stop_during_post_strips_the_stale_live_card(self):
        row, changed = await self.start()
        value = interaction(administrator=True)
        value.channel_id = 201
        value.channel = MagicMock(spec=discord.TextChannel)
        value.channel.id = 201
        message = MagicMock(spec=discord.Message)
        message.id = 303
        message.edit = AsyncMock()

        async def stopped_send(**kwargs):
            await stop_stream(1, 101)
            return message

        value.channel.send = AsyncMock(side_effect=stopped_send)
        with patch("services.stream_delivery.get_setting", AsyncMock(return_value=None)):
            posted, current = await post_announcement(value, row, b"PNG fixture")
        self.assertFalse(current)
        self.assertEqual(message.edit.call_args.kwargs["attachments"], [])
        self.assertIn("STREAM ENDED", message.edit.call_args.kwargs["embed"].title)

    async def test_blocked_dms_are_counted_and_no_dm_is_sent_for_stale_revisions(self):
        row, changed = await self.start()
        guild = MagicMock(spec=discord.Guild)
        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.send = AsyncMock(side_effect=forbidden())
        guild.get_member.return_value = member
        recipients = {11: {"name": "Squad"}, 12: {"name": "Squad"}}
        counts = await notify_players(guild, row, recipients, b"PNG fixture")
        self.assertEqual(counts, {"sent": 0, "failed": 2, "skipped": 0})
        await stop_stream(1, 101)
        member.send.reset_mock()
        counts = await notify_players(guild, row, recipients, b"PNG fixture")
        self.assertEqual(counts, {"sent": 0, "failed": 0, "skipped": 2})
        member.send.assert_not_awaited()

    async def test_stop_refreshes_replay_and_removes_live_image_without_room_secrets(self):
        row, changed = await self.start()
        await save_announcement(1, row["stream_revision"], 201, 301)
        row = await stop_stream(1, 101)
        guild = MagicMock(spec=discord.Guild)
        guild.id = GUILD
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = guild
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        channel.fetch_message = AsyncMock(return_value=message)
        guild.get_channel.return_value = channel
        await update_stopped_announcement(guild, row)
        data = message.edit.call_args.kwargs
        self.assertEqual(data["attachments"], [])
        self.assertEqual(data["view"].children[0].label, "Watch Replay")
        row["room_password"] = "PRIVATE-ROOM-PASSWORD"
        self.assertNotIn("PRIVATE-ROOM-PASSWORD", str(stream_embed(row).to_dict()))

    async def test_url_validation_rejects_private_addresses_and_credentials_without_fetching(self):
        for url in (
            "https://127.0.0.1/live",
            "https://[::1]/live",
            "https://host.internal/live",
            "https://localhost/live",
            "https://youtube.com\\@evil.com/live",
            "https://user:secret@youtube.com/live",
            "https://-invalid.com/live",
            "https://youtube.com/<script>",
            "file:///stream.mp4",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_stream_url(url)
        self.assertEqual(
            validate_stream_url("https://www.twitch.tv/rootlu"), "https://www.twitch.tv/rootlu"
        )

    async def test_dm_fanout_is_bounded_and_bots_are_skipped(self):
        row, _changed = await self.start()
        guild = MagicMock(spec=discord.Guild)
        member = MagicMock(spec=discord.Member)
        member.bot = False
        active = peak = 0

        async def send(**kwargs):
            nonlocal active, peak
            active += 1
            peak = max(active, peak)
            await asyncio.sleep(0.01)
            active -= 1

        member.send = AsyncMock(side_effect=send)
        guild.get_member.return_value = member
        recipients = {i: {"name": "Squad"} for i in range(1, 21)}
        with patch("services.stream_delivery.is_current_stream", AsyncMock(return_value=True)):
            counts = await notify_players(guild, row, recipients, b"PNG fixture")
        self.assertEqual(counts["sent"], 20)
        self.assertEqual(peak, 4)
        member.bot = True
        member.send.reset_mock()
        with patch("services.stream_delivery.is_current_stream", AsyncMock(return_value=True)):
            counts = await notify_players(guild, row, recipients, b"PNG fixture")
        self.assertEqual(counts["skipped"], 20)
        member.send.assert_not_awaited()

    async def test_finalized_tournament_cannot_restart_a_live_stream_even_if_legacy_match_status_changes(
        self,
    ):
        await self.sql("UPDATE tournaments SET status='finished' WHERE id=1")
        await self.sql("UPDATE matches SET status='room_open' WHERE id=1")
        with self.assertRaises(ValueError):
            await self.start()
