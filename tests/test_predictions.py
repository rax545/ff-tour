import asyncio

from services.brackets import bind_match, create_bracket, resolve_node
from services.predictions import (
    cancel_predictions,
    list_predictions,
    lock_predictions,
    open_predictions,
    pick_team,
    prediction_leaderboard,
    prediction_pool,
    settle_predictions,
)
from services.streams import start_stream, stop_stream
from tests.helpers import GUILD, NOW, IsolatedArenaTest


class PredictionTests(IsolatedArenaTest):
    async def pool(self, *, match_id=1, cutoff=NOW + 60):
        return await open_predictions(GUILD, match_id, cutoff, 101, now=NOW)

    async def test_open_captures_entrants_not_future_roster_or_team_name_changes(self):
        pool = await self.pool()
        self.assertEqual(len(pool["entries"]), 3)
        await self.sql("UPDATE teams SET name='Changed' WHERE id=1")
        detail = await prediction_pool(GUILD, pool["id"], 11, now=NOW)
        self.assertEqual(detail["entries"][0]["name"], "Squad 1")
        self.assertIsNone(detail["my_pick"])
        self.assertEqual(len(await list_predictions(GUILD)), 1)
        self.assertEqual(await list_predictions(200), [])
        with self.assertRaises(ValueError):
            await self.pool()

    async def test_pick_is_one_editable_record_per_account(self):
        pool = await self.pool()
        await asyncio.gather(
            *(pick_team(GUILD, pool["id"], 11, 1 + i % 3, now=NOW) for i in range(20))
        )
        self.assertEqual(len(await self.fetch("SELECT * FROM prediction_picks")), 1)
        await pick_team(GUILD, pool["id"], 11, 2, now=NOW + 59)
        detail = await prediction_pool(GUILD, pool["id"], 11, now=NOW)
        self.assertEqual(detail["total_picks"], 1)
        self.assertEqual(detail["my_pick"]["team_id"], 2)
        self.assertNotIn("user_id", detail["entries"][1])  # Other users' picks are private.

    async def test_exact_cutoff_and_invalid_entrant_or_guild_reject_changes(self):
        pool = await self.pool()
        for guild, team, now in [(GUILD, 1, NOW + 60), (GUILD, 99, NOW), (200, 1, NOW)]:
            with self.subTest(guild=guild, team=team, now=now), self.assertRaises(ValueError):
                await pick_team(guild, pool["id"], 11, team, now=now)
        self.assertEqual(await self.fetch("SELECT * FROM prediction_picks"), [])
        self.assertEqual(
            (await prediction_pool(GUILD, pool["id"], now=NOW + 60))["status"], "locked"
        )

    async def test_future_cutoff_bounds_and_absolute_match_schedule(self):
        for cutoff in (NOW, NOW - 1, NOW + 31 * 86400):
            with self.assertRaises(ValueError):
                await self.pool(cutoff=cutoff)
        await self.sql("UPDATE matches SET scheduled_at=? WHERE id=1", (f"<t:{NOW + 30}:F>",))
        with self.assertRaises(ValueError):
            await self.pool()
        pool = await self.pool(cutoff=NOW + 20)
        self.assertEqual(pool["effective_closes_at"], NOW + 20)
        await self.sql("UPDATE matches SET scheduled_at=? WHERE id=1", (f"<t:{NOW + 10}:F>",))
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 1, now=NOW + 10)

    async def test_live_start_locks_even_if_staff_chose_later_cutoff_and_offline_never_reopens(
        self,
    ):
        pool = await self.pool()
        await start_stream(1, "https://youtu.be/live", "YouTube", 101)
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await stop_stream(1, 101)
        self.assertEqual((await prediction_pool(GUILD, pool["id"], now=NOW))["status"], "locked")
        with self.assertRaises(ValueError):
            await open_predictions(GUILD, 1, NOW + 600, 101, now=NOW)

    async def test_room_open_and_any_submitted_result_block_late_votes(self):
        pool = await self.pool()
        await self.sql("UPDATE matches SET status='room_open' WHERE id=1")
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await self.sql("UPDATE matches SET status='scheduled' WHERE id=1")
        await self.squad_scores(1, verified=False)
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        with self.assertRaises(ValueError):
            await settle_predictions(GUILD, pool["id"], 101, now=NOW + 61)

    async def test_settle_awards_ten_once_under_concurrent_retries_and_guild_scopes_ranks(self):
        pool = await self.pool()
        await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await pick_team(GUILD, pool["id"], 12, 2, now=NOW)
        await self.squad_scores()
        results = await asyncio.gather(
            *(settle_predictions(GUILD, pool["id"], 101, now=NOW + 61) for _ in range(6))
        )
        self.assertTrue(all(r["winner_team_id"] == 1 for r in results))
        ranks = await prediction_leaderboard(GUILD)
        self.assertEqual(
            [(r["user_id"], r["points"], r["correct"]) for r in ranks], [(11, 10, 1), (12, 0, 0)]
        )
        self.assertEqual(await prediction_leaderboard(200), [])
        self.assertEqual(
            len(await self.fetch("SELECT * FROM audit_logs WHERE action='prediction_settle'")), 1
        )
        with self.assertRaises(ValueError):
            await cancel_predictions(GUILD, pool["id"], 101)
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 2, now=NOW)

    async def test_incomplete_results_and_duplicate_winners_never_award_points(self):
        pool = await self.pool()
        await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await lock_predictions(GUILD, pool["id"], 101)
        with self.assertRaises(ValueError):
            await settle_predictions(GUILD, pool["id"], 101, now=NOW)
        await self.squad_scores()
        await self.sql("UPDATE results SET placement=1 WHERE team_id=2")
        with self.assertRaises(ValueError):
            await settle_predictions(GUILD, pool["id"], 101, now=NOW)
        self.assertEqual(
            (await self.fetch("SELECT awarded_points FROM prediction_picks"))[0]["awarded_points"],
            0,
        )

    async def test_cancelled_arena_never_settles_reopens_or_appears_in_scored_ranks(self):
        pool = await self.pool()
        await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await cancel_predictions(GUILD, pool["id"], 101)
        await cancel_predictions(GUILD, pool["id"], 101)
        await self.squad_scores()
        with self.assertRaises(ValueError):
            await settle_predictions(GUILD, pool["id"], 101, now=NOW + 61)
        self.assertEqual(await prediction_leaderboard(GUILD), [])
        with self.assertRaises(ValueError):
            await self.pool()

    async def test_knockout_arena_cannot_settle_before_bound_result(self):
        bracket = await create_bracket(GUILD, 1, 101)
        node = bracket["nodes"][1]
        await bind_match(GUILD, node["id"], 1, 101)
        pool = await self.pool()
        await pick_team(GUILD, pool["id"], 11, node["team_b"], now=NOW)
        await lock_predictions(GUILD, pool["id"], 101)
        with self.assertRaises(ValueError):
            await settle_predictions(GUILD, pool["id"], 101, now=NOW)
        await resolve_node(GUILD, node["id"], node["team_b"], 1, 3, 101)
        await settle_predictions(GUILD, pool["id"], 101, now=NOW)
        self.assertEqual((await prediction_leaderboard(GUILD))[0]["points"], 10)

    async def test_player_result_is_a_start_signal_and_cascade_removes_pools_and_votes(self):
        pool = await self.pool()
        await pick_team(GUILD, pool["id"], 11, 1, now=NOW)
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills) VALUES(1,1,'Player 1','100001',2)"
        )
        with self.assertRaises(ValueError):
            await pick_team(GUILD, pool["id"], 11, 2, now=NOW)
        await self.sql("DELETE FROM matches WHERE id=1")
        for table in ("prediction_pools", "prediction_entries", "prediction_picks"):
            self.assertEqual(await self.fetch(f"SELECT * FROM {table}"), [])
