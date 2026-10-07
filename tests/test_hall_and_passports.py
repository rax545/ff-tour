import asyncio
import json

from services.arena import player_passport
from services.brackets import create_bracket, resolve_node
from services.hall_of_fame import hall_of_fame, induct_tournament, revoke_induction
from services.leaderboard import top_fraggers
from services.player_stats import record_player_result
from services.predictions import open_predictions, prediction_pool
from tests.helpers import GUILD, NOW, IsolatedArenaTest


class HallTests(IsolatedArenaTest):
    async def complete(self):
        await self.squad_scores(1)
        await self.squad_scores(2)

    async def test_missing_pending_or_conflicting_lobby_results_block_finalization(self):
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)
        await self.squad_scores(1)
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)
        await self.squad_scores(2, verified=False)
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)
        await self.sql("UPDATE results SET verified=1,placement=1 WHERE match_id=2")
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)
        self.assertEqual(await hall_of_fame(GUILD), [])

    async def test_br_champion_and_individual_mvp_are_distinct_truthful_stats(self):
        await self.complete()
        await record_player_result(GUILD, 1, 2, 8, 1200, 101)
        await record_player_result(GUILD, 2, 2, 8, 1800, 101)
        records = await asyncio.gather(*(induct_tournament(GUILD, 1, 101) for _ in range(4)))
        self.assertEqual(len({r["id"] for r in records}), 1)
        record = records[0]
        self.assertEqual([p["id"] for p in record["podium"]], [1, 2, 3])
        self.assertEqual(record["podium"][0]["points"], 50)
        self.assertEqual(record["mvp"]["ign"], "Player 2")
        self.assertEqual(record["mvp"]["kills"], 16)
        self.assertNotIn("uid", record["mvp"])
        self.assertEqual(
            (await self.fetch("SELECT status FROM tournaments WHERE id=1"))[0]["status"], "finished"
        )
        self.assertEqual(
            (await self.fetch("SELECT status FROM matches WHERE id=1"))[0]["status"], "finished"
        )

    async def test_snapshot_survives_renames_score_edits_and_source_deletion(self):
        await self.complete()
        before = await induct_tournament(GUILD, 1, 101)
        await self.sql("UPDATE teams SET name='Renamed' WHERE id=1")
        await self.sql("UPDATE results SET total_points=999 WHERE team_id=2")
        after = await induct_tournament(GUILD, 1, 101)
        self.assertEqual(before["podium"], after["podium"])
        await self.sql("DELETE FROM tournaments WHERE id=1")
        self.assertEqual((await hall_of_fame(GUILD))[0]["podium"], before["podium"])
        self.assertEqual(await hall_of_fame(200), [])

    async def test_revocation_is_private_scoped_and_cannot_silently_reissue(self):
        await self.complete()
        record = await induct_tournament(GUILD, 1, 101)
        with self.assertRaises(ValueError):
            await revoke_induction(200, record["id"], 101, "Wrong server")
        await revoke_induction(GUILD, record["id"], 101, "Score dispute upheld")
        self.assertEqual(await hall_of_fame(GUILD), [])
        self.assertEqual(
            (await self.fetch("SELECT revoke_reason FROM hall_of_fame"))[0]["revoke_reason"],
            "Score dispute upheld",
        )
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)

    async def test_no_individual_data_means_no_invented_mvp(self):
        await self.complete()
        self.assertEqual(await top_fraggers(1), [])
        self.assertEqual((await induct_tournament(GUILD, 1, 101))["mvp"], {})

    async def test_knockout_archive_uses_the_final_not_aggregate_br_points(self):
        bracket = await create_bracket(GUILD, 1, 101)
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)
        node = bracket["nodes"][1]
        bracket = await resolve_node(GUILD, node["id"], 3, 0, 1, 101)
        final = bracket["nodes"][-1]
        await resolve_node(GUILD, final["id"], 3, 0, 3, 101)
        record = await induct_tournament(GUILD, 1, 101)
        self.assertEqual(record["format"], "knockout")
        self.assertEqual([p["id"] for p in record["podium"]], [3, 1])

    async def test_live_br_tournament_cannot_be_inducted(self):
        await self.complete()
        await self.sql("UPDATE matches SET stream_live=1 WHERE id=1")
        with self.assertRaises(ValueError):
            await induct_tournament(GUILD, 1, 101)


class IndividualStatsTests(IsolatedArenaTest):
    async def test_upsert_has_single_row_and_passport_does_not_leak_student_id(self):
        pool = await open_predictions(GUILD, 1, NOW + 60, 101, now=NOW)
        ids = await asyncio.gather(
            *(record_player_result(GUILD, 1, 1, 7, 500, 101) for _ in range(4))
        )
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(await self.fetch("SELECT * FROM player_results")), 1)
        await self.sql(
            "INSERT INTO student_verifications(user_id,student_id,full_name,batch,section) VALUES(11,'PRIVATE-STUDENT-ID','Student','60','A')"
        )
        roster, stats, student = await player_passport(11)
        self.assertEqual(stats, {"kills": 7, "damage": 500, "matches": 1})
        self.assertNotIn("PRIVATE-STUDENT-ID", json.dumps([roster, stats, student]))
        self.assertEqual((await prediction_pool(GUILD, pool["id"], now=NOW))["status"], "locked")
        await self.sql(
            "INSERT INTO team_members(team_id,user_id,ign,uid) VALUES(1,11,'Duplicate roster row','100001')"
        )
        self.assertEqual((await player_passport(11))[1]["kills"], 7)
        self.assertEqual((await top_fraggers(1))[0]["kills"], 7)

    async def test_ambiguous_uid_ownership_or_duplicate_match_rows_are_excluded(self):
        await record_player_result(GUILD, 1, 1, 7, 500, 101)
        await self.sql(
            "INSERT INTO team_members(team_id,user_id,ign,uid) VALUES(2,12,'Alias',' 100001 ')"
        )
        self.assertEqual((await player_passport(11))[1]["kills"], 0)
        self.assertEqual(await top_fraggers(1), [])
        await self.sql("DELETE FROM team_members WHERE ign='Alias'")
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills,verified) VALUES(1,1,'Duplicate','100001',70,1)"
        )
        self.assertEqual((await player_passport(11))[1]["kills"], 0)
        self.assertEqual(await top_fraggers(1), [])
        with self.assertRaises(ValueError):
            await record_player_result(GUILD, 1, 1, 1, 1, 101)

    async def test_player_scores_cannot_exceed_verified_squad_kills_or_cross_fixture_teams(self):
        await self.squad_scores(1)
        with self.assertRaises(ValueError):
            await record_player_result(GUILD, 1, 1, 10, 500, 101)  # Squad 1 has 9.
        with self.assertRaises(ValueError):
            await record_player_result(GUILD, 1, 99, 1, 500, 101)
        for kills, damage in ((-1, 0), (101, 0), (1, -1), (1, 100001)):
            with self.assertRaises(ValueError):
                await record_player_result(GUILD, 1, 1, kills, damage, 101)
        await record_player_result(GUILD, 1, 1, 9, 500, 101)
        await self.sql(
            "INSERT INTO team_members(id,team_id,ign,uid) VALUES(50,1,'Teammate','123456')"
        )
        with self.assertRaises(ValueError):
            await record_player_result(GUILD, 1, 50, 1, 100, 101)

    async def test_unverified_and_wrong_tournament_rows_never_become_passport_or_mvp_stats(self):
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills,verified) VALUES(1,1,'Player 1','100001',70,0),(99,1,'Player 1','100001',70,1)"
        )
        self.assertEqual((await player_passport(11))[1]["kills"], 0)
        self.assertEqual(await top_fraggers(), [])
