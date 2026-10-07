import io
import os
import sys
import unittest
import tempfile
from unittest import mock
import aiosqlite

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SERVER_NAME
import database.db as db_module
from database.db import connect, init_db, get_setting, set_setting
from services.leaderboard import section_leaderboard, top_fraggers
from utils.banner import (
    generate_tournament_banner,
    generate_match_banner,
    clean_text_for_image
)
from utils.embeds import (
    stream_live_dm_embed
)
from utils.cards import live_broadcast
from cogs.esports import OFFICIAL_5_MAP_ROTATION


class FeatureTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = mock.patch.object(db_module, 'DATABASE_PATH', os.path.join(self.tmp.name, 'features.sqlite3'))
        self.path_patch.start()
        await init_db()

    async def asyncTearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    async def test_01_clean_text_and_banners(self):
        # 1. clean_text_for_image
        cleaned = clean_text_for_image("Root LU Esports")
        self.assertIn("ROOT LU", cleaned.upper())

        # 2. Tournament banner
        tourn_buf = generate_tournament_banner(
            tournament_name="ROOT LU CSE CHAMPIONSHIP 2026",
            server_name="Root LU",
            max_teams=24,
            prize_pool=5000,
            entry_fee=100,
            tournament_id=1,
            status="OPEN"
        )
        self.assertIsInstance(tourn_buf, io.BytesIO)
        self.assertGreater(len(tourn_buf.getvalue()), 10000)

        # 3. Match banner
        match_buf = generate_match_banner(
            tournament_name="ROOT LU CSE CHAMPIONSHIP 2026",
            match_no=1,
            map_name="Bermuda",
            scheduled_at="Tonight 9:00 PM",
            server_name="Root LU"
        )
        self.assertIsInstance(match_buf, io.BytesIO)
        self.assertGreater(len(match_buf.getvalue()), 10000)

    async def test_02_student_verification_system(self):
        """Feature 2: /student verify verification logic & DB constraints"""
        db = await connect()

        # Clean existing test verifications
        await db.execute("DELETE FROM student_verifications WHERE user_id IN (1001, 1002)")
        await db.commit()

        # Insert student verification
        await db.execute(
            """
            INSERT INTO student_verifications
            (user_id, student_id, full_name, department, batch, section, status)
            VALUES (?, ?, ?, ?, ?, ?, 'verified')
            """,
            (1001, "2012020123", "Joy Ahmed", "CSE", "60", "A")
        )
        await db.commit()

        # Verify entry
        cur = await db.execute("SELECT * FROM student_verifications WHERE user_id=?", (1001,))
        row = await cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["student_id"], "2012020123")
        self.assertEqual(row["full_name"], "Joy Ahmed")
        self.assertEqual(row["department"], "CSE")
        self.assertEqual(row["batch"], "60")
        self.assertEqual(row["section"], "A")
        self.assertEqual(row["status"], "verified")

        # Duplicate user_id constraint test
        with self.assertRaises(Exception):
            await db.execute(
                """
                INSERT INTO student_verifications
                (user_id, student_id, full_name, department, batch, section, status)
                VALUES (?, ?, ?, ?, ?, ?, 'verified')
                """,
                (1001, "2012020999", "Another Name", "CSE", "61", "B")
            )
            await db.commit()

        # Duplicate student_id constraint test
        with self.assertRaises(Exception):
            await db.execute(
                """
                INSERT INTO student_verifications
                (user_id, student_id, full_name, department, batch, section, status)
                VALUES (?, ?, ?, ?, ?, ?, 'verified')
                """,
                (1002, "2012020123", "Duplicate ID User", "CSE", "60", "A")
            )
            await db.commit()

        await db.close()

    async def test_03_team_create_with_batch_and_section(self):
        """Feature 5: /team create with batch, section and 4+1 roster"""
        db = await connect()

        # Insert tournament
        cur = await db.execute(
            "INSERT INTO tournaments (name, description, max_teams, entry_fee, prize_pool) VALUES ('LU Premier League', 'Test', 12, 0, 1000)"
        )
        t_id = cur.lastrowid

        # Insert team with batch and section
        cur = await db.execute(
            """
            INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section)
            VALUES (?, 'CSE Predators', 'PRED', 1001, '60', 'A')
            """,
            (t_id,)
        )
        team_id = cur.lastrowid

        # Insert 4 starters + 1 substitute
        players = [
            (team_id, 1001, "PRED_Joy", "UID001", "IGL", 0),
            (team_id, 1002, "PRED_Rusher", "UID002", "Rusher", 0),
            (team_id, 1003, "PRED_Sniper", "UID003", "Sniper", 0),
            (team_id, 1004, "PRED_Assault", "UID004", "Assaulter", 0),
            (team_id, 1005, "PRED_Sub", "UID005", "Substitute", 1),
        ]
        for p in players:
            await db.execute(
                "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) VALUES (?, ?, ?, ?, ?, ?)",
                p
            )
        await db.commit()

        # Query team
        cur = await db.execute("SELECT * FROM teams WHERE id=?", (team_id,))
        t_row = await cur.fetchone()
        self.assertEqual(t_row["batch"], "60")
        self.assertEqual(t_row["section"], "A")

        # Query members
        cur = await db.execute("SELECT COUNT(*) AS c FROM team_members WHERE team_id=?", (team_id,))
        self.assertEqual((await cur.fetchone())["c"], 5)

        await db.close()

    async def test_04_section_leaderboard_and_rankings(self):
        """Feature 1: /section leaderboard - Points aggregation by CSE Batch and Section"""
        db = await connect()

        # Create tournament
        cur = await db.execute("INSERT INTO tournaments (name) VALUES ('LU Section Clash')")
        t_id = cur.lastrowid

        # Create 3 teams across 2 sections
        # Batch 60 Sec A - Team 1
        cur = await db.execute("INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) VALUES (?, 'LU 60A Alpha', '60A1', 2001, '60', 'A')", (t_id,))
        team_60a_1 = cur.lastrowid
        # Batch 60 Sec A - Team 2
        cur = await db.execute("INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) VALUES (?, 'LU 60A Bravo', '60A2', 2002, '60', 'A')", (t_id,))
        team_60a_2 = cur.lastrowid
        # Batch 58 Sec B - Team 1
        cur = await db.execute("INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) VALUES (?, 'LU 58B Legends', '58B', 2003, '58', 'B')", (t_id,))
        team_58b = cur.lastrowid

        # Create matches
        cur = await db.execute("INSERT INTO matches (tournament_id, match_no, map) VALUES (?, 1, 'Bermuda')", (t_id,))
        m1 = cur.lastrowid
        cur = await db.execute("INSERT INTO matches (tournament_id, match_no, map) VALUES (?, 2, 'Purgatory')", (t_id,))

        # Submit verified results
        # Team 60A_1: Match 1: 1st place (12 pts) + 8 kills (8 pts) = 20 pts
        # Team 60A_2: Match 1: 3rd place (8 pts) + 4 kills (4 pts) = 12 pts
        # Team 58B: Match 1: 2nd place (9 pts) + 6 kills (6 pts) = 15 pts
        # Batch 60A total = 32 pts, 12 kills
        # Batch 58B total = 15 pts, 6 kills
        await db.execute("INSERT INTO results (match_id, team_id, placement, kills, placement_points, kill_points, total_points, verified) VALUES (?, ?, 1, 8, 12, 8, 20, 1)", (m1, team_60a_1))
        await db.execute("INSERT INTO results (match_id, team_id, placement, kills, placement_points, kill_points, total_points, verified) VALUES (?, ?, 3, 4, 8, 4, 12, 1)", (m1, team_60a_2))
        await db.execute("INSERT INTO results (match_id, team_id, placement, kills, placement_points, kill_points, total_points, verified) VALUES (?, ?, 2, 6, 9, 6, 15, 1)", (m1, team_58b))
        await db.commit()
        await db.close()

        # Run section leaderboard
        sec_rows = await section_leaderboard(t_id)
        self.assertEqual(len(sec_rows), 2)

        # Rank 1 must be Batch 60 Section A
        rank1 = sec_rows[0]
        self.assertEqual(rank1["batch"], "60")
        self.assertEqual(rank1["section"], "A")
        self.assertEqual(rank1["pts"], 32)
        self.assertEqual(rank1["kills"], 12)
        self.assertEqual(rank1["teams_count"], 2)
        self.assertEqual(rank1["top_team_name"], "LU 60A Alpha")

        # Rank 2 must be Batch 58 Section B
        rank2 = sec_rows[1]
        self.assertEqual(rank2["batch"], "58")
        self.assertEqual(rank2["section"], "B")
        self.assertEqual(rank2["pts"], 15)
        self.assertEqual(rank2["kills"], 6)
        self.assertEqual(rank2["teams_count"], 1)

    async def test_05_result_topfraggers(self):
        """Feature 3: /result topfraggers - Most kills & MVP leaderboard"""
        db = await connect()

        # Create tournament and teams
        cur = await db.execute("INSERT INTO tournaments (name) VALUES ('LU Fraggers League')")
        t_id = cur.lastrowid

        cur = await db.execute("INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) VALUES (?, 'Root Hunters', 'RH', 3001, '60', 'A')", (t_id,))
        t1_id = cur.lastrowid
        cur = await db.execute("INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) VALUES (?, 'Root Assassins', 'RA', 3002, '59', 'B')", (t_id,))
        t2_id = cur.lastrowid

        # Insert players
        await db.execute("INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) VALUES (?, 3001, 'RH_SniperGod', '111', 'Sniper', 0)", (t1_id,))
        await db.execute("INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) VALUES (?, 3002, 'RA_RusherKing', '222', 'Rusher', 0)", (t2_id,))

        cur = await db.execute("INSERT INTO matches (tournament_id, match_no, map) VALUES (?, 1, 'Bermuda')", (t_id,))
        m1 = cur.lastrowid

        # Insert individual player results
        await db.execute("INSERT INTO player_results (match_id, team_id, ign, uid, kills, verified) VALUES (?, ?, 'RH_SniperGod', '111', 9, 1)", (m1, t1_id))
        await db.execute("INSERT INTO player_results (match_id, team_id, ign, uid, kills, verified) VALUES (?, ?, 'RA_RusherKing', '222', 5, 1)", (m1, t2_id))
        await db.commit()
        await db.close()

        # Query top fraggers
        fraggers = await top_fraggers(t_id, limit=5)
        self.assertGreaterEqual(len(fraggers), 2)

        # Top fragger must be RH_SniperGod with 9 kills
        self.assertEqual(fraggers[0]["ign"], "RH_SniperGod")
        self.assertEqual(fraggers[0]["kills"], 9)
        self.assertEqual(fraggers[0]["team_tag"], "RH")

        # 2nd fragger must be RA_RusherKing with 5 kills
        self.assertEqual(fraggers[1]["ign"], "RA_RusherKing")
        self.assertEqual(fraggers[1]["kills"], 5)

    async def test_06_tournament_fixtures_and_5_map_rotation(self):
        """Feature 4: /tournament fixtures & 5-map rotation schedule"""
        # Verify 5 official competitive maps
        expected_maps = ["Bermuda", "Purgatory", "Kalahari", "Alpine", "NexTerra"]
        actual_maps = [m[1] for m in OFFICIAL_5_MAP_ROTATION]
        self.assertEqual(actual_maps, expected_maps)
        self.assertEqual(len(OFFICIAL_5_MAP_ROTATION), 5)

    async def test_07_live_stream_broadcast_notification(self):
        """Feature 7: /match stream - Live stream broadcast notification + HD card"""
        db = await connect()

        # Create tournament, team and match
        cur = await db.execute("INSERT INTO tournaments (name) VALUES ('LU Broadcast Cup')")
        t_id = cur.lastrowid

        cur = await db.execute(
            "INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) "
            "VALUES (?, 'Root Broadcasters', 'RB', 4001, '60', 'C')",
            (t_id,)
        )

        cur = await db.execute(
            "INSERT INTO matches (tournament_id, match_no, map, scheduled_at) VALUES (?, 1, 'Bermuda', 'Tonight 9 PM')",
            (t_id,)
        )
        match_id = cur.lastrowid
        await db.commit()

        # Columns should exist and default to offline/empty
        cur = await db.execute("SELECT stream_url, stream_platform, stream_live FROM matches WHERE id=?", (match_id,))
        row = await cur.fetchone()
        self.assertEqual(row["stream_url"], "")
        self.assertEqual(row["stream_platform"], "")
        self.assertEqual(row["stream_live"], 0)

        # Simulate /match stream going live
        await db.execute(
            "UPDATE matches SET stream_url=?, stream_platform=?, stream_live=1 WHERE id=?",
            ("https://youtube.com/watch?v=root-lu-live", "YouTube", match_id)
        )
        await db.commit()

        cur = await db.execute("SELECT stream_url, stream_platform, stream_live FROM matches WHERE id=?", (match_id,))
        row = await cur.fetchone()
        self.assertEqual(row["stream_url"], "https://youtube.com/watch?v=root-lu-live")
        self.assertEqual(row["stream_platform"], "YouTube")
        self.assertEqual(row["stream_live"], 1)

        await db.close()

        # DM embed should surface the clickable stream link and squad info
        dm_embed = stream_live_dm_embed(
            team_name="Root Broadcasters",
            team_tag="RB",
            tournament_name="LU Broadcast Cup",
            match_no=1,
            match_id=match_id,
            map_name="Bermuda",
            platform="YouTube",
            stream_url="https://youtube.com/watch?v=root-lu-live",
            server_name=SERVER_NAME
        )
        self.assertIn("LIVE", dm_embed.title)
        field_values = " ".join(f.value for f in dm_embed.fields)
        self.assertIn("Root Broadcasters", field_values)
        self.assertIn("https://youtube.com/watch?v=root-lu-live", field_values)

        # HD broadcast card must be a real 1280x720 PNG
        card_buf = live_broadcast("LU Broadcast Cup", 1, "Bermuda", "YouTube")
        self.assertIsInstance(card_buf, io.BytesIO)
        self.assertGreater(len(card_buf.getvalue()), 10000)

    async def test_08_settings_upsert(self):
        key = "test_notification_channel"
        await set_setting(key, "111")
        self.assertEqual(await get_setting(key), "111")
        await set_setting(key, "222")
        self.assertEqual(await get_setting(key), "222")
        self.assertEqual(await get_setting("missing_test_setting", "fallback"), "fallback")

        db = await connect()
        cur = await db.execute("SELECT COUNT(*) AS c FROM settings WHERE key=?", (key,))
        self.assertEqual((await cur.fetchone())["c"], 1)
        await db.execute("DELETE FROM settings WHERE key=?", (key,))
        await db.commit()
        await db.close()

    async def test_09_backward_compatible_stream_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_path = os.path.join(tmp, "legacy.sqlite3")
            legacy = await aiosqlite.connect(legacy_path)
            await legacy.executescript("""
                CREATE TABLE tournaments (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE matches (
                    id INTEGER PRIMARY KEY,
                    tournament_id INTEGER NOT NULL,
                    match_no INTEGER NOT NULL,
                    map TEXT
                );
            """)
            await legacy.commit()
            await legacy.close()

            with mock.patch.object(db_module, "DATABASE_PATH", legacy_path):
                await db_module.init_db()
                migrated = await db_module.connect()
                cur = await migrated.execute("PRAGMA table_info(matches)")
                columns = {row[1] for row in await cur.fetchall()}
                await migrated.close()

            self.assertTrue(
                {"stream_url", "stream_platform", "stream_live"}.issubset(columns)
            )


if __name__ == "__main__":
    unittest.main()
