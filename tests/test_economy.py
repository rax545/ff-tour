"""Coin economy, bounty board and match prediction tests (isolated temp DB)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db_module
from database.db import init_db, connect
from services.economy import (
    EconomyError,
    DAILY_REWARD,
    MIN_BOUNTY,
    MIN_PREDICTION,
    PREDICTION_PAYOUT_MULTIPLIER,
    get_balance,
    add_coins,
    claim_daily,
    tip,
    coin_leaderboard,
    place_bounty,
    bounty_board,
    claim_bounty,
    cancel_bounty,
    place_prediction,
    resolve_predictions,
)


class EconomyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "test_economy.sqlite3")
        self._patcher = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patcher.start()
        await init_db()

    async def asyncTearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    # ----------------------------------------------------
    # Coins
    # ----------------------------------------------------

    async def test_balance_defaults_to_zero(self):
        self.assertEqual(await get_balance(12345), 0)

    async def test_add_coins_and_balance(self):
        await add_coins(1, 250, "test", 0, "seed")
        self.assertEqual(await get_balance(1), 250)
        await add_coins(1, 50, "test")
        self.assertEqual(await get_balance(1), 300)

    async def test_daily_claim_and_cooldown(self):
        reward, next_at = await claim_daily(42)
        self.assertEqual(reward, DAILY_REWARD)
        self.assertEqual(await get_balance(42), DAILY_REWARD)
        self.assertIsNotNone(next_at)
        # Second claim on the same day is rejected
        with self.assertRaises(EconomyError):
            await claim_daily(42)
        # Balance unchanged after rejected claim
        self.assertEqual(await get_balance(42), DAILY_REWARD)

    async def test_tip_transfers_coins(self):
        await add_coins(1, 500, "seed")
        await tip(1, 2, 120)
        self.assertEqual(await get_balance(1), 380)
        self.assertEqual(await get_balance(2), 120)

    async def test_tip_rejects_self_and_insufficient(self):
        await add_coins(1, 100, "seed")
        with self.assertRaises(EconomyError):
            await tip(1, 1, 10)
        with self.assertRaises(EconomyError):
            await tip(1, 2, 1000)
        with self.assertRaises(EconomyError):
            await tip(1, 2, 0)
        # Balances untouched
        self.assertEqual(await get_balance(1), 100)
        self.assertEqual(await get_balance(2), 0)

    async def test_coin_leaderboard_ordering(self):
        await add_coins(1, 100, "seed")
        await add_coins(2, 300, "seed")
        await add_coins(3, 200, "seed")
        board = await coin_leaderboard(10)
        self.assertEqual([r["user_id"] for r in board], [2, 3, 1])
        self.assertEqual(board[0]["balance"], 300)

    async def test_transactions_are_audited(self):
        await add_coins(7, 90, "seed")
        db = await connect()
        try:
            cur = await db.execute(
                "SELECT amount, kind FROM coin_transactions WHERE user_id=7"
            )
            rows = await cur.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["amount"], 90)
            self.assertEqual(rows[0]["kind"], "seed")
        finally:
            await db.close()

    # ----------------------------------------------------
    # Bounties
    # ----------------------------------------------------

    async def _seed_match_result(self, target_user, match_id, placement, verified=1):
        db = await connect()
        try:
            cur = await db.execute(
                "INSERT INTO tournaments (name) VALUES ('Bounty Cup')"
            )
            t_id = cur.lastrowid
            cur = await db.execute(
                "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, 'T', 'T', ?)",
                (t_id, target_user),
            )
            team_id = cur.lastrowid
            await db.execute(
                "INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub) "
                "VALUES (?, ?, 'TargetIGN', 'UIDT', 'Rusher', 0)",
                (team_id, target_user),
            )
            cur = await db.execute(
                "INSERT INTO matches (tournament_id, match_no, map) VALUES (?, ?, 'Bermuda')",
                (t_id, match_id),
            )
            m_id = cur.lastrowid
            await db.execute(
                "INSERT INTO results (match_id, team_id, placement, kills, "
                "placement_points, kill_points, total_points, verified) "
                "VALUES (?, ?, ?, 5, 0, 5, 5, ?)",
                (m_id, team_id, placement, verified),
            )
            await db.commit()
            return m_id
        finally:
            await db.close()

    async def test_place_bounty_locks_coins(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300, "revenge")
        self.assertGreater(bounty_id, 0)
        self.assertEqual(await get_balance(1), 700)
        board = await bounty_board()
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["status"], "active")
        self.assertEqual(board[0]["amount"], 300)
        self.assertEqual(board[0]["target_id"], 2)

    async def test_place_bounty_validation(self):
        await add_coins(1, 100, "seed")
        with self.assertRaises(EconomyError):
            await place_bounty(1, 1, 100)          # self bounty
        with self.assertRaises(EconomyError):
            await place_bounty(1, 2, MIN_BOUNTY - 1)  # below minimum
        with self.assertRaises(EconomyError):
            await place_bounty(1, 2, 500)          # insufficient funds
        self.assertEqual(await get_balance(1), 100)

    async def test_claim_bounty_pays_hunter(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        m_id = await self._seed_match_result(target_user=2, match_id=5, placement=4)
        result = await claim_bounty(bounty_id, 99, m_id)
        self.assertEqual(result["payout"], 300)
        self.assertEqual(await get_balance(99), 300)
        self.assertEqual(await get_balance(1), 700)  # locked, not refunded
        board = await bounty_board("claimed")
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["claimed_by"], 99)

    async def test_claim_bounty_rejects_winner(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        m_id = await self._seed_match_result(target_user=2, match_id=6, placement=1)
        with self.assertRaises(EconomyError):
            await claim_bounty(bounty_id, 99, m_id)
        # Bounty still active
        self.assertEqual(len(await bounty_board("active")), 1)

    async def test_claim_bounty_rejects_unverified(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        m_id = await self._seed_match_result(target_user=2, match_id=7, placement=4, verified=0)
        with self.assertRaises(EconomyError):
            await claim_bounty(bounty_id, 99, m_id)

    async def test_claim_bounty_rejects_self_claim(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        m_id = await self._seed_match_result(target_user=2, match_id=8, placement=4)
        with self.assertRaises(EconomyError):
            await claim_bounty(bounty_id, 2, m_id)

    async def test_cancel_bounty_refunds(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        await cancel_bounty(bounty_id, 1)
        self.assertEqual(await get_balance(1), 1000)
        self.assertEqual(len(await bounty_board("active")), 0)
        self.assertEqual(len(await bounty_board("cancelled")), 1)

    async def test_cancel_bounty_rejects_stranger(self):
        await add_coins(1, 1000, "seed")
        bounty_id = await place_bounty(1, 2, 300)
        with self.assertRaises(EconomyError):
            await cancel_bounty(bounty_id, 555, staff=False)
        # Staff can cancel
        await cancel_bounty(bounty_id, 555, staff=True)
        self.assertEqual(await get_balance(1), 1000)

    # ----------------------------------------------------
    # Predictions
    # ----------------------------------------------------

    async def _seed_match(self, match_no=1):
        db = await connect()
        try:
            cur = await db.execute("INSERT INTO tournaments (name) VALUES ('Pred Cup')")
            t_id = cur.lastrowid
            for i, name in enumerate(("Alpha", "Bravo"), start=1):
                await db.execute(
                    "INSERT INTO teams (tournament_id, name, tag, captain_id) VALUES (?, ?, ?, ?)",
                    (t_id, name, name[:2].upper(), 1000 + i),
                )
            cur = await db.execute(
                "INSERT INTO matches (tournament_id, match_no, map) VALUES (?, ?, 'Bermuda')",
                (t_id, match_no),
            )
            m_id = cur.lastrowid
            cur = await db.execute("SELECT id FROM teams WHERE tournament_id=? ORDER BY id", (t_id,))
            team_ids = [r["id"] for r in await cur.fetchall()]
            await db.commit()
            return m_id, team_ids
        finally:
            await db.close()

    async def test_prediction_flow_win_and_loss(self):
        m_id, team_ids = await self._seed_match()
        await add_coins(1, 500, "seed")
        await add_coins(2, 500, "seed")

        await place_prediction(m_id, 1, team_ids[0], 100)
        await place_prediction(m_id, 2, team_ids[1], 200)

        # Stakes locked
        self.assertEqual(await get_balance(1), 400)
        self.assertEqual(await get_balance(2), 300)

        summary = await resolve_predictions(m_id, team_ids[0])
        self.assertEqual(summary["won"], 1)
        self.assertEqual(summary["lost"], 1)
        self.assertEqual(summary["payout_total"], 100 * PREDICTION_PAYOUT_MULTIPLIER)

        # Winner gets stake * multiplier back; loser forfeits stake
        self.assertEqual(await get_balance(1), 400 + 200)
        self.assertEqual(await get_balance(2), 300)

    async def test_prediction_validation(self):
        m_id, team_ids = await self._seed_match(match_no=2)
        await add_coins(1, 500, "seed")
        with self.assertRaises(EconomyError):
            await place_prediction(m_id, 1, team_ids[0], MIN_PREDICTION - 1)
        with self.assertRaises(EconomyError):
            await place_prediction(m_id, 1, team_ids[0], 10000)
        with self.assertRaises(EconomyError):
            await place_prediction(m_id, 1, 999999, 100)  # unknown team
        with self.assertRaises(EconomyError):
            await place_prediction(999999, 1, team_ids[0], 100)  # unknown match
        # One prediction per user per match
        await place_prediction(m_id, 1, team_ids[0], 100)
        with self.assertRaises(EconomyError):
            await place_prediction(m_id, 1, team_ids[1], 100)

    async def test_prediction_closed_after_completion(self):
        m_id, team_ids = await self._seed_match(match_no=3)
        db = await connect()
        try:
            await db.execute("UPDATE matches SET status='completed' WHERE id=?", (m_id,))
            await db.commit()
        finally:
            await db.close()
        await add_coins(1, 500, "seed")
        with self.assertRaises(EconomyError):
            await place_prediction(m_id, 1, team_ids[0], 100)


if __name__ == "__main__":
    unittest.main()
