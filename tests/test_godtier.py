"""God-tier feature tests: schema, brackets, security scans, player cards,
hall of fame and the complete slash-command surface."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db_module
from database.db import init_db, connect
from services.bracket import (
    BracketError,
    generate_bracket,
    get_bracket,
    record_bracket_result,
    _seeding_order,
    _bracket_size,
)
from services.security import run_security_scan, recent_scans
from services.players import compute_attributes, compute_ovr, player_card_profile, ATTRIBUTE_KEYS
from services.economy import add_coins


class SchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "schema.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_godtier_tables_exist(self):
        db = await connect()
        try:
            cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r["name"] for r in await cur.fetchall()}
        finally:
            await db.close()
        expected = {
            "coins", "coin_transactions", "daily_claims", "bounties",
            "predictions", "hall_of_fame", "bracket_matches", "security_scans",
        }
        self.assertTrue(expected.issubset(tables), f"missing: {expected - tables}")

    async def test_bounty_status_check_constraint(self):
        db = await connect()
        try:
            with self.assertRaises(Exception):
                await db.execute(
                    "INSERT INTO bounties (placer_id, target_id, amount, status) "
                    "VALUES (1, 2, 100, 'bogus')"
                )
                await db.commit()
        finally:
            await db.close()


class BracketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "bracket.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def test_seeding_order(self):
        self.assertEqual(_seeding_order(2), [1, 2])
        self.assertEqual(_seeding_order(4), [1, 4, 2, 3])
        self.assertEqual(_seeding_order(8), [1, 8, 4, 5, 2, 7, 3, 6])
        self.assertEqual(_seeding_order(16)[0], 1)
        self.assertEqual(_seeding_order(16)[1], 16)
        self.assertEqual(sorted(_seeding_order(16)), list(range(1, 17)))
        self.assertEqual(_bracket_size(12), 16)
        self.assertEqual(_bracket_size(2), 2)
        self.assertEqual(_bracket_size(1), 2)

    async def _seed_tournament(self, n_teams=12):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('Bracket Cup')")
            t_id = cur.lastrowid
            for i in range(1, n_teams + 1):
                await db.execute(
                    "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, ?, ?, ?)",
                    (t_id, f"Team {i}", f"T{i}", 5000 + i),
                )
            await db.commit()
            return t_id
        finally:
            await db.close()

    async def test_generate_bracket_12_teams(self):
        t_id = await self._seed_tournament(12)
        bracket = await generate_bracket(t_id)
        # 12 teams -> 16 bracket -> 4 rounds: 8 + 4 + 2 + 1 = 15 matches
        self.assertEqual(bracket["total_rounds"], 4)
        self.assertEqual([len(r) for r in bracket["rounds"]], [8, 4, 2, 1])
        total = sum(len(r) for r in bracket["rounds"])
        self.assertEqual(total, 15)

        # Round 1: 12 teams placed, 4 byes (16 - 12)
        round1 = bracket["rounds"][0]
        byes = [m for m in round1 if m["status"] == "bye"]
        self.assertEqual(len(byes), 4)
        # Byes auto-advance
        for m in byes:
            self.assertTrue(m["winner_id"])

    async def test_bracket_idempotent_and_force(self):
        t_id = await self._seed_tournament(8)
        b1 = await generate_bracket(t_id)
        b2 = await generate_bracket(t_id)  # no force -> same bracket
        self.assertEqual(
            [(m["round"], m["slot"], m["team_a_id"], m["team_b_id"]) for r in b1["rounds"] for m in r],
            [(m["round"], m["slot"], m["team_a_id"], m["team_b_id"]) for r in b2["rounds"] for m in r],
        )
        b3 = await generate_bracket(t_id, force=True)
        self.assertEqual(b3["total_rounds"], 3)

    async def test_bracket_requires_two_teams(self):
        t_id = await self._seed_tournament(1)
        with self.assertRaises(BracketError):
            await generate_bracket(t_id)

    async def test_record_bracket_result_propagates(self):
        t_id = await self._seed_tournament(4)
        bracket = await generate_bracket(t_id)
        r1 = bracket["rounds"][0]
        # No byes with 4 teams; play both round-1 matches
        for m in r1:
            await record_bracket_result(t_id, 1, m["slot"], m["team_a_id"])
        bracket = await get_bracket(t_id)
        semifinal = bracket["rounds"][1][0]
        self.assertEqual(semifinal["team_a_id"], r1[0]["team_a_id"])
        self.assertEqual(semifinal["team_b_id"], r1[1]["team_a_id"])

    async def test_record_bracket_result_validation(self):
        t_id = await self._seed_tournament(4)
        bracket = await generate_bracket(t_id)
        m = bracket["rounds"][0][0]
        with self.assertRaises(BracketError):
            await record_bracket_result(t_id, 1, m["slot"], 999999)
        with self.assertRaises(BracketError):
            await record_bracket_result(t_id, 9, 9, m["team_a_id"])


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "security.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_clean_scan_has_no_findings(self):
        summary = await run_security_scan(1, "full")
        self.assertEqual(summary["findings_count"], 0)
        self.assertEqual(summary["findings"], [])
        self.assertEqual(summary["scope"], "full")
        # Persisted
        scans = await recent_scans(5)
        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0]["scanner_id"], 1)

    async def test_scan_detects_issues(self):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('Scan Cup')")
            t_id = cur.lastrowid
            # Team with only 2 starters + unverified captain + negative coins
            cur = await db.execute(
                "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, 'Half', 'HF', 777)",
                (t_id,),
            )
            team_id = cur.lastrowid
            await db.execute(
                "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) "
                "VALUES (?, 777, 'A', 'UID1', 'IGL', 0)", (team_id,))
            await db.execute(
                "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) "
                "VALUES (?, 778, 'B', 'UID2', 'Rusher', 0)", (team_id,))
            await db.execute("INSERT INTO coins (user_id, balance) VALUES (999, -50)")
            await db.execute(
                "INSERT INTO reports (reporter_id, target_id, reason) VALUES (1, 2, 'cheating')"
            )
            await db.commit()
        finally:
            await db.close()
        # Negative balance directly (bypassing service guards)
        await add_coins(999, -10, "test_seed")

        summary = await run_security_scan(1)
        findings = "\n".join(summary["findings"])
        self.assertIn("Half", findings)          # incomplete roster
        self.assertIn("777", findings)           # unverified captain
        self.assertIn("999", findings)           # negative balance
        self.assertIn("report", findings.lower())  # open reports
        self.assertGreaterEqual(summary["findings_count"], 4)

    async def test_scan_detects_duplicate_uids(self):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('Dup Cup')")
            t_id = cur.lastrowid
            for i, captain in enumerate((11, 22), start=1):
                cur = await db.execute(
                    "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, ?, ?, ?)",
                    (t_id, f"Team {i}", f"T{i}", captain),
                )
                team_id = cur.lastrowid
                # Same FF UID linked to two different Discord accounts
                await db.execute(
                    "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) "
                    "VALUES (?, ?, 'Shared', 'SHARED_UID', 'IGL', 0)",
                    (team_id, captain),
                )
            await db.commit()
        finally:
            await db.close()
        summary = await run_security_scan(1)
        self.assertTrue(any("SHARED_UID" in f for f in summary["findings"]))


class PlayerCardTests(unittest.TestCase):
    def test_compute_attributes_keys_and_caps(self):
        attrs = compute_attributes(kills=1000, damage=99999, matches=500, wins=100)
        self.assertEqual(set(attrs.keys()), set(ATTRIBUTE_KEYS))
        for v in attrs.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 99)

    def test_compute_attributes_zeroes(self):
        attrs = compute_attributes(0, 0, 0, 0)
        self.assertTrue(all(v >= 30 for v in attrs.values()))

    def test_compute_ovr(self):
        attrs = {k: 90 for k in ATTRIBUTE_KEYS}
        self.assertEqual(compute_ovr(attrs), 90)
        attrs = {k: 99 for k in ATTRIBUTE_KEYS}
        self.assertEqual(compute_ovr(attrs), 99)  # capped
        attrs = {k: 0 for k in ATTRIBUTE_KEYS}
        self.assertEqual(compute_ovr(attrs), 0)


class PlayerProfileDbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "players.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_player_card_profile_empty(self):
        self.assertEqual(await player_card_profile(424242), {})

    async def test_player_card_profile_aggregation(self):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('Card Cup')")
            t_id = cur.lastrowid
            cur = await db.execute(
                "INSERT INTO teams (tournament_id, name, tag, captain_id, batch, section) "
                "VALUES (?, 'Root Wolves', 'RW', 31337, '60', 'A')", (t_id,))
            team_id = cur.lastrowid
            await db.execute(
                "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) "
                "VALUES (?, 31337, 'JoyPro', 'UID31337', 'IGL', 0)", (team_id,))
            cur = await db.execute(
                "INSERT INTO matches (tournament_id, match_no, map) VALUES (?, 1, 'Bermuda')", (t_id,))
            m1 = cur.lastrowid
            cur = await db.execute(
                "INSERT INTO matches (tournament_id, match_no, map) VALUES (?, 2, 'Purgatory')", (t_id,))
            m2 = cur.lastrowid
            # Verified individual results
            await db.execute(
                "INSERT INTO player_results (match_id, team_id, ign, uid, kills, damage, verified) "
                "VALUES (?, ?, 'JoyPro', 'UID31337', 7, 2100, 1)", (m1, team_id))
            await db.execute(
                "INSERT INTO player_results (match_id, team_id, ign, uid, kills, damage, verified) "
                "VALUES (?, ?, 'JoyPro', 'UID31337', 5, 1500, 1)", (m2, team_id))
            # Unverified result must be ignored
            await db.execute(
                "INSERT INTO player_results (match_id, team_id, ign, uid, kills, damage, verified) "
                "VALUES (?, ?, 'JoyPro', 'UID31337', 99, 99999, 0)", (m2, team_id))
            # A verified win for the win counter
            await db.execute(
                "INSERT INTO results (match_id, team_id, placement, kills, "
                "placement_points, kill_points, total_points, verified) "
                "VALUES (?, ?, 1, 12, 12, 12, 24, 1)", (m1, team_id))
            await db.commit()
        finally:
            await db.close()

        profile = await player_card_profile(31337)
        self.assertEqual(profile["ign"], "JoyPro")
        self.assertEqual(profile["uid"], "UID31337")
        self.assertEqual(profile["role"], "IGL")
        self.assertEqual(profile["team_name"], "Root Wolves")
        self.assertEqual(profile["team_tag"], "RW")
        self.assertEqual(profile["batch"], "60")
        self.assertEqual(profile["section"], "A")
        self.assertEqual(profile["kills"], 12)      # 7 + 5, unverified ignored
        self.assertEqual(profile["damage"], 3600)
        self.assertEqual(profile["matches"], 2)
        self.assertEqual(profile["wins"], 1)
        self.assertEqual(set(profile["attributes"].keys()), set(ATTRIBUTE_KEYS))
        self.assertGreaterEqual(profile["ovr"], 30)
        self.assertLessEqual(profile["ovr"], 99)


class CommandSurfaceTests(unittest.TestCase):
    """Verify the complete required slash-command surface exists."""

    def test_required_command_groups(self):
        from unittest.mock import MagicMock
        from discord import app_commands
        from cogs.esports import Esports
        from cogs.economy import Economy
        from cogs.players import Players
        from cogs.security import Security
        from cogs.arena import Arena

        cogs = [
            Esports(MagicMock()), Economy(MagicMock()), Players(MagicMock()),
            Security(MagicMock()), Arena(MagicMock()),
        ]
        groups = {}
        for cog in cogs:
            for attr in vars(type(cog)).values():
                if isinstance(attr, app_commands.Group):
                    groups.setdefault(attr.name, set()).update(c.name for c in attr.commands)

        required = {
            "tournament": {"create", "close", "leaderboard", "slotlist", "bracket", "halloffame"},
            "team": {"register", "info", "myteam"},
            "match": {"create", "credentials", "start", "end", "dropmap", "warrooms",
                      "cleanup_warrooms", "clash", "predict", "killfeed", "countdown"},
            "player": {"passport", "card"},
            "bounty": {"place", "board"},
            "coin": {"balance", "daily", "tip", "leaderboard"},
            "certificate": {"generate"},
            "student": {"verify", "info", "list"},
            "section": {"leaderboard", "stats"},
            "security": {"scan"},
        }
        for grp, subs in required.items():
            have = groups.get(grp, set())
            missing = subs - have
            self.assertFalse(missing, f"/{grp} missing subcommands: {sorted(missing)}")

    def test_team_register_alias_shares_create_logic(self):
        from cogs.esports import Esports

        register = next(c for c in Esports.team.commands if c.name == "register")
        create = next(c for c in Esports.team.commands if c.name == "create")
        self.assertIs(register.callback, create.callback)


class HallOfFameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "hof.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_hall_of_fame_insert_and_read(self):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('HOF Cup')")
            t_id = cur.lastrowid
            cur = await db.execute(
                "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, 'Champs', 'CH', 1)",
                (t_id,))
            team_id = cur.lastrowid
            await db.execute(
                "INSERT INTO hall_of_fame (tournament_id, team_id, team_name, team_tag, "
                "achievement, points, kills, season) VALUES (?, ?, 'Champs', 'CH', 'CHAMPION', 99, 40, '2026 Season')",
                (t_id, team_id))
            await db.commit()
            cur = await db.execute("SELECT * FROM hall_of_fame WHERE tournament_id=?", (t_id,))
            row = await cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["achievement"], "CHAMPION")
            self.assertEqual(row["points"], 99)
        finally:
            await db.close()


if __name__ == "__main__":
    unittest.main()
