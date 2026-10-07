import asyncio
import unittest

from services.brackets import bind_match, bracket_tree, create_bracket, resolve_node, seed_order
from services.predictions import open_predictions, settle_predictions
from tests.helpers import GUILD, NOW, IsolatedArenaTest


class SeedTests(unittest.TestCase):
    def test_seed_order_balanced_for_every_supported_size(self):
        for size in (2, 4, 8, 16, 32):
            with self.subTest(size=size):
                order = seed_order(size)
                self.assertEqual(sorted(order), list(range(1, size + 1)))
                self.assertEqual(
                    [sum(order[i : i + 2]) for i in range(0, size, 2)], [size + 1] * (size // 2)
                )
                self.assertEqual(order[0], 1)
        for invalid in (0, 1, 3, 64):
            with self.assertRaises(ValueError):
                seed_order(invalid)


class BracketTests(IsolatedArenaTest):
    async def test_three_teams_get_one_bye_not_a_premature_final_winner(self):
        bracket = await create_bracket(GUILD, 1, 101)
        self.assertEqual(bracket["size"], 4)
        self.assertEqual(len(bracket["nodes"]), 3)
        bye, playable, final = bracket["nodes"]
        self.assertEqual((bye["status"], bye["winner_id"]), ("bye", 1))
        self.assertEqual((playable["team_a"], playable["team_b"]), (2, 3))
        self.assertEqual(final["status"], "pending")
        bracket = await resolve_node(GUILD, playable["id"], 2, 2, 1, 101)
        self.assertEqual(bracket["nodes"][-1]["status"], "ready")
        self.assertEqual((bracket["nodes"][-1]["team_a"], bracket["nodes"][-1]["team_b"]), (1, 2))
        final = bracket["nodes"][-1]
        bracket = await resolve_node(GUILD, final["id"], 1, 3, 0, 101)
        self.assertEqual(bracket["status"], "finished")
        self.assertEqual(bracket["nodes"][-1]["winner_id"], 1)
        self.assertEqual(
            (await self.fetch("SELECT status FROM tournaments WHERE id=1"))[0]["status"], "closed"
        )

    async def test_manual_seeding_is_exactly_the_registered_lobby(self):
        for bad in ([1, 1, 3], [1, 2], [1, 2, 99]):
            with self.subTest(seeds=bad), self.assertRaises(ValueError):
                await create_bracket(GUILD, 1, 101, bad)
        bracket = await create_bracket(GUILD, 1, 101, [3, 1, 2])
        self.assertEqual([e["team_id"] for e in bracket["entries"]], [3, 1, 2])
        self.assertEqual(bracket["nodes"][0]["winner_id"], 3)

    async def test_concurrent_creation_never_replaces_existing_progress(self):
        outcomes = await asyncio.gather(
            *(create_bracket(GUILD, 1, 101) for _ in range(4)), return_exceptions=True
        )
        self.assertEqual(sum(isinstance(o, dict) for o in outcomes), 1)
        self.assertEqual(len(await self.fetch("SELECT * FROM brackets")), 1)
        self.assertEqual(len(await self.fetch("SELECT * FROM bracket_nodes")), 3)

    async def test_invalid_nodes_scores_and_guild_are_rejected(self):
        bracket = await create_bracket(GUILD, 1, 101)
        ready, final = bracket["nodes"][1:]
        for guild, node, winner, a, b in [
            (200, ready["id"], 2, 1, 0),
            (GUILD, final["id"], 1, 1, 0),
            (GUILD, ready["id"], 99, 1, 0),
            (GUILD, ready["id"], 2, 0, 1),
            (GUILD, ready["id"], 2, 1, 1),
            (GUILD, ready["id"], 2, -1, 0),
        ]:
            with self.subTest(guild=guild, node=node, score=(a, b)), self.assertRaises(ValueError):
                await resolve_node(guild, node, winner, a, b, 101)
        with self.assertRaises(ValueError):
            await bracket_tree(200, 1)
        self.assertEqual((await bracket_tree(GUILD, 1))["nodes"][-1]["status"], "pending")

    async def test_resolution_retries_are_idempotent_but_corrections_cannot_rewrite_downstream(
        self,
    ):
        bracket = await create_bracket(GUILD, 1, 101)
        node = bracket["nodes"][1]
        outcomes = await asyncio.gather(
            *(resolve_node(GUILD, node["id"], 2, 3, 1, 101) for _ in range(4))
        )
        self.assertTrue(all(o["nodes"][-1]["team_b"] == 2 for o in outcomes))
        self.assertEqual(
            len(await self.fetch("SELECT * FROM audit_logs WHERE action='bracket_resolve'")), 1
        )
        with self.assertRaises(ValueError):
            await resolve_node(GUILD, node["id"], 3, 1, 3, 101)

    async def test_bind_limits_fixture_predictions_to_opponents_and_settles_from_staff_result(self):
        bracket = await create_bracket(GUILD, 1, 101)
        node = bracket["nodes"][1]
        with self.assertRaises(ValueError):
            await bind_match(GUILD, node["id"], 99, 101)
        await bind_match(GUILD, node["id"], 1, 101)
        await bind_match(GUILD, node["id"], 1, 101)  # Retry is harmless.
        pool = await open_predictions(GUILD, 1, NOW + 60, 101, now=NOW)
        self.assertEqual({e["team_id"] for e in pool["entries"]}, {2, 3})
        await resolve_node(GUILD, node["id"], 3, 0, 2, 101)
        settled = await settle_predictions(GUILD, pool["id"], 101, now=NOW + 61)
        self.assertEqual(settled["winner_team_id"], 3)
        self.assertEqual(
            (await self.fetch("SELECT status FROM matches WHERE id=1"))[0]["status"], "finished"
        )

    async def test_binding_existing_prediction_fixture_is_rejected(self):
        await open_predictions(GUILD, 1, NOW + 60, 101, now=NOW)
        node = (await create_bracket(GUILD, 1, 101))["nodes"][1]
        with self.assertRaises(ValueError):
            await bind_match(GUILD, node["id"], 1, 101)

    async def test_snapshots_survive_renames_and_tournament_delete_cascades_tree(self):
        bracket = await create_bracket(GUILD, 1, 101)
        await self.sql("UPDATE teams SET name='New name' WHERE id=1")
        self.assertEqual((await bracket_tree(GUILD, 1))["entries"][0]["name"], "Squad 1")
        await self.sql("DELETE FROM tournaments WHERE id=1")
        for table in ("brackets", "bracket_entries", "bracket_nodes"):
            self.assertEqual(await self.fetch(f"SELECT * FROM {table}"), [])
        self.assertIsNotNone(bracket)

    async def test_all_bracket_sizes_finish_without_empty_or_duplicate_advancement(self):
        for count in (2, 5, 8, 17, 32):
            tour = 1000 + count
            await self.sql(
                "INSERT INTO tournaments(id,name,max_teams) VALUES(?,?,32)", (tour, f"Cup {count}")
            )
            for i in range(count):
                await self.sql(
                    "INSERT INTO teams(tournament_id,name,tag,captain_id) VALUES(?,?,?,?)",
                    (tour, f"Team {i}", f"T{i}", 500 + i),
                )
            bracket = await create_bracket(GUILD, tour, 101)
            played = 0
            while bracket["status"] != "finished":
                ready = [n for n in bracket["nodes"] if n["status"] == "ready"]
                self.assertTrue(ready, f"{count} teams got stuck without a ready node")
                node = ready[0]
                self.assertNotEqual(node["team_a"], node["team_b"])
                bracket = await resolve_node(GUILD, node["id"], node["team_a"], 1, 0, 101)
                played += 1
            self.assertEqual(played, count - 1)
            self.assertEqual(bracket["nodes"][-1]["winner_id"], bracket["entries"][0]["team_id"])
