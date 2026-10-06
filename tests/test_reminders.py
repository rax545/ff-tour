"""
Tests for the Match Reminder & Schedule Notification system:
schedule-time parsing, offset parsing, reminder scheduling,
due-reminder querying, status updates and cancellation.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use an isolated database for this test module
os.environ.setdefault("DATABASE_PATH", "data/test_reminders.sqlite3")

from config import TZ_OFFSET_MINUTES
from database.db import connect, init_db
from services.reminders import (
    DEFAULT_OFFSETS,
    parse_schedule_time,
    parse_offsets,
    compute_remind_times,
    schedule_match_reminders,
    due_reminders,
    pending_reminders,
    mark_reminder,
    cancel_match_reminders,
    iso,
    local_tz,
)
from utils.embeds import match_reminder_embed


class ParsingTests(unittest.TestCase):

    def test_parse_full_datetime(self):
        now = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
        result = parse_schedule_time("2026-12-25 21:00", now=now)
        self.assertEqual(result.tzinfo, timezone.utc)
        local = result.astimezone(local_tz())
        self.assertEqual((local.year, local.month, local.day), (2026, 12, 25))
        self.assertEqual((local.hour, local.minute), (21, 0))

    def test_parse_day_first_with_meridiem(self):
        now = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
        result = parse_schedule_time("25/12/2026 9:00 PM", now=now)
        local = result.astimezone(local_tz())
        self.assertEqual((local.day, local.month, local.hour), (25, 12, 21))

    def test_parse_tomorrow(self):
        now = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
        result = parse_schedule_time("tomorrow 8:30 pm", now=now)
        local_now = now.astimezone(local_tz())
        local = result.astimezone(local_tz())
        self.assertEqual(local.date(), (local_now + timedelta(days=1)).date())
        self.assertEqual((local.hour, local.minute), (20, 30))

    def test_parse_bare_time_rolls_to_tomorrow_if_past(self):
        # 23:50 local "now"; asking for 01:00 should land tomorrow
        local_now = datetime(2026, 10, 7, 23, 50, tzinfo=local_tz())
        now = local_now.astimezone(timezone.utc)
        result = parse_schedule_time("01:00", now=now)
        self.assertGreater(result, now)

    def test_parse_rejects_past_time(self):
        now = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            parse_schedule_time("2020-01-01 10:00", now=now)

    def test_parse_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_schedule_time("not a time at all")
        with self.assertRaises(ValueError):
            parse_schedule_time("")

    def test_parse_offsets_default(self):
        self.assertEqual(parse_offsets(""), list(DEFAULT_OFFSETS))
        self.assertEqual(parse_offsets(None), list(DEFAULT_OFFSETS))

    def test_parse_offsets_custom(self):
        self.assertEqual(parse_offsets("5, 60, 15"), [60, 15, 5])
        self.assertEqual(parse_offsets("30,30,30"), [30])

    def test_parse_offsets_invalid(self):
        with self.assertRaises(ValueError):
            parse_offsets("60,abc")
        with self.assertRaises(ValueError):
            parse_offsets("0")
        with self.assertRaises(ValueError):
            parse_offsets("99999")
        with self.assertRaises(ValueError):
            parse_offsets("1,2,3,4,5,6,7")

    def test_compute_remind_times_skips_past(self):
        match_time = datetime.now(timezone.utc) + timedelta(minutes=20)
        pairs = compute_remind_times(match_time, [60, 15, 5])
        offs = [o for o, _ in pairs]
        self.assertEqual(offs, [15, 5])  # 60-min mark already passed

    def test_timezone_default_is_dhaka(self):
        self.assertEqual(TZ_OFFSET_MINUTES, 360)


class ReminderDbTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.db = await connect()

        # Seed tournament + match
        cur = await self.db.execute(
            "INSERT INTO tournaments (name, max_teams) VALUES (?, ?)",
            ("Reminder Cup", 12)
        )
        self.tournament_id = cur.lastrowid

        cur = await self.db.execute(
            "INSERT INTO matches (tournament_id, match_no, map) VALUES (?, ?, ?)",
            (self.tournament_id, 1, "Bermuda")
        )
        self.match_id = cur.lastrowid
        await self.db.commit()

    async def asyncTearDown(self):
        await self.db.execute(
            "DELETE FROM tournaments WHERE id=?", (self.tournament_id,)
        )
        await self.db.commit()
        await self.db.close()

    async def test_schedule_and_list(self):
        match_time = datetime.now(timezone.utc) + timedelta(hours=2)
        scheduled = await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=123, created_by=42,
            match_time_utc=match_time, offsets=[60, 15, 5]
        )
        self.assertEqual(len(scheduled), 3)

        rows = await pending_reminders(self.db, self.tournament_id)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["offset_minutes"], 60)  # earliest remind first
        self.assertEqual(rows[0]["tournament_name"], "Reminder Cup")
        self.assertEqual(rows[0]["match_no"], 1)

    async def test_reschedule_replaces_pending(self):
        match_time = datetime.now(timezone.utc) + timedelta(hours=2)
        await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=0, created_by=42,
            match_time_utc=match_time, offsets=[60, 15, 5]
        )
        await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=0, created_by=42,
            match_time_utc=match_time + timedelta(hours=1), offsets=[30]
        )
        rows = await pending_reminders(self.db, self.tournament_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["offset_minutes"], 30)

    async def test_due_and_mark_sent(self):
        match_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=0, created_by=42,
            match_time_utc=match_time, offsets=[5]
        )

        # Not due yet
        rows = await due_reminders(self.db)
        ours = [r for r in rows if r["match_id"] == self.match_id]
        self.assertEqual(len(ours), 0)

        # Due when "now" is past the remind_at
        future_now = match_time - timedelta(minutes=4)
        rows = await due_reminders(self.db, now=future_now)
        ours = [r for r in rows if r["match_id"] == self.match_id]
        self.assertEqual(len(ours), 1)

        await mark_reminder(self.db, ours[0]["id"], "sent")
        rows = await due_reminders(self.db, now=future_now)
        ours = [r for r in rows if r["match_id"] == self.match_id]
        self.assertEqual(len(ours), 0)

    async def test_cancel(self):
        match_time = datetime.now(timezone.utc) + timedelta(hours=1)
        await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=0, created_by=42,
            match_time_utc=match_time, offsets=[30, 10]
        )
        count = await cancel_match_reminders(self.db, self.match_id)
        self.assertEqual(count, 2)

        rows = await pending_reminders(self.db, self.tournament_id)
        self.assertEqual(len(rows), 0)

        # Cancelling again affects nothing
        count = await cancel_match_reminders(self.db, self.match_id)
        self.assertEqual(count, 0)

    async def test_cascade_delete_with_match(self):
        match_time = datetime.now(timezone.utc) + timedelta(hours=1)
        await schedule_match_reminders(
            self.db, self.match_id, self.tournament_id,
            channel_id=0, created_by=42,
            match_time_utc=match_time, offsets=[15]
        )
        await self.db.execute(
            "DELETE FROM matches WHERE id=?", (self.match_id,)
        )
        await self.db.commit()

        cur = await self.db.execute(
            "SELECT COUNT(*) AS c FROM reminders WHERE match_id=?",
            (self.match_id,)
        )
        row = await cur.fetchone()
        self.assertEqual(row["c"], 0)


class ReminderEmbedTests(unittest.TestCase):

    def test_embed_contents(self):
        unix = int(datetime.now(timezone.utc).timestamp()) + 900
        embed = match_reminder_embed(
            tournament_name="Reminder Cup",
            tournament_id=1,
            match_no=3,
            match_id=7,
            map_name="Purgatory",
            match_time_unix=unix,
            offset_minutes=15
        )
        self.assertIn("15 MINUTES", embed.title.upper())
        self.assertIn("Reminder Cup", embed.description)
        names = [f.name for f in embed.fields]
        self.assertIn("🕒 Match Time", names)
        values = " ".join(f.value for f in embed.fields)
        self.assertIn(f"<t:{unix}:F>", values)
        self.assertIn("Purgatory", values)

    def test_embed_hour_countdown(self):
        unix = int(datetime.now(timezone.utc).timestamp()) + 3600
        embed = match_reminder_embed(
            tournament_name="Reminder Cup",
            tournament_id=1,
            match_no=1,
            match_id=1,
            map_name="Bermuda",
            match_time_unix=unix,
            offset_minutes=90
        )
        self.assertIn("1H 30M", embed.title.upper())


if __name__ == "__main__":
    unittest.main()
