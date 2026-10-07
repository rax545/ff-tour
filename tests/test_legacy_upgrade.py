import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database.db as db_module
from database.arena_schema import STREAM_COLUMNS
from services.arena_common import database, page_slice, scheduled_timestamp
from tests.helpers import NOW


class UpgradeTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrades_a_copy_of_the_shipped_database_twice_without_data_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "upgrade.sqlite3")
            original = sqlite3.connect(
                Path(__file__).resolve().parents[1] / "data" / "esports.sqlite3"
            )
            target = sqlite3.connect(path)
            original.backup(target)
            counts = {
                table: target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("tournaments", "teams", "team_members", "matches", "results")
            }
            original.close()
            target.close()
            with patch.object(db_module, "DATABASE_PATH", path):
                await db_module.init_db()
                await db_module.init_db()
                async with database() as db:
                    for table, count in counts.items():
                        result = await (
                            await db.execute(f"SELECT COUNT(*) FROM {table}")
                        ).fetchone()
                        self.assertEqual(result[0], count)
                    columns = {
                        row[1]
                        for row in await (await db.execute("PRAGMA table_info(matches)")).fetchall()
                    }
                    self.assertTrue(set(STREAM_COLUMNS).issubset(columns))
                    self.assertEqual(
                        await (await db.execute("PRAGMA foreign_key_check")).fetchall(), []
                    )
                    tables = {
                        row[0]
                        for row in await (
                            await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "brackets",
                            "hall_of_fame",
                            "prediction_pools",
                            "radar_findings",
                            "squad_plans",
                            "squad_ready_checks",
                        }.issubset(tables)
                    )

    async def test_transaction_failure_rolls_back_and_closes_connection(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(db_module, "DATABASE_PATH", str(Path(folder) / "rollback.sqlite3")),
        ):
            await db_module.init_db()
            with self.assertRaises(RuntimeError):
                async with database(write=True) as db:
                    await db.execute("INSERT INTO tournaments(name) VALUES('Never saved')")
                    raise RuntimeError("simulated error")
            async with database() as db:
                self.assertEqual(
                    (await (await db.execute("SELECT COUNT(*) FROM tournaments")).fetchone())[0], 0
                )


class CommonTests(unittest.TestCase):
    def test_absolute_schedules_and_unambiguous_cutoffs(self):
        self.assertEqual(scheduled_timestamp(f"<t:{NOW}:F>"), NOW)
        self.assertEqual(scheduled_timestamp("2026-10-07T12:00:00+00:00"), NOW)
        self.assertEqual(scheduled_timestamp("2026-10-07 18:00"), NOW)
        for ambiguous in ("TBA", "tomorrow 9 PM", "21:00", "<t:bad:F>", "2026-99-99T00:00:00Z"):
            self.assertIsNone(scheduled_timestamp(ambiguous))

    def test_page_bounds_are_explicit(self):
        self.assertEqual(page_slice([], 1, 12), ([], 1))
        self.assertEqual(page_slice(list(range(25)), 3, 12), ([24], 3))
        for page in (0, -1, 4):
            with self.assertRaises(ValueError):
                page_slice(list(range(25)), page, 12)
