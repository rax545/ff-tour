from services.radar import DISCORD_EPOCH_MS, radar_findings, review_finding, scan_rosters
from tests.helpers import GUILD, NOW, IsolatedArenaTest


class RadarTests(IsolatedArenaTest):
    async def scan(self):
        return await scan_rosters(GUILD, 1, 101, now=NOW)

    async def test_normal_uid_reuse_in_another_season_is_not_a_signal(self):
        await self.sql("UPDATE team_members SET uid='100001',user_id=11 WHERE team_id=99")
        self.assertEqual((await self.scan())["signals"], 0)
        self.assertEqual(await radar_findings(GUILD, 1), [])

    async def test_normalized_duplicate_uid_and_multi_squad_account_are_explained(self):
        await self.sql("UPDATE team_members SET uid=' 100001 ' WHERE id=2")
        await self.sql("UPDATE teams SET captain_id=101 WHERE id=2")
        result = await self.scan()
        rows = await radar_findings(GUILD, 1)
        self.assertEqual(result["signals"], 2)
        duplicate = next(r for r in rows if r["kind"] == "duplicate_uid")
        self.assertEqual(duplicate["severity"], "high")
        self.assertEqual(duplicate["evidence"]["team_ids"], [1, 2])
        self.assertEqual(duplicate["evidence"]["discord_ids"], [11, 12])
        self.assertEqual(await radar_findings(200, 1), [])

    async def test_review_survives_rescans_and_resolved_signals_become_inactive_without_bans(self):
        await self.sql("UPDATE team_members SET uid='100001' WHERE id=2")
        await self.scan()
        finding = (await radar_findings(GUILD, 1))[0]
        with self.assertRaises(ValueError):
            await review_finding(200, finding["id"], 101, "cleared", "Wrong guild")
        await review_finding(
            GUILD, finding["id"], 101, "cleared", "Captain corrected a registration typo"
        )
        await self.scan()
        self.assertEqual((await radar_findings(GUILD, 1))[0]["status"], "cleared")
        await self.sql("UPDATE team_members SET uid='100002' WHERE id=2")
        await self.scan()
        self.assertEqual(await radar_findings(GUILD, 1), [])
        history = await radar_findings(GUILD, 1, include_inactive=True)
        self.assertEqual((history[0]["active"], history[0]["status"]), (0, "cleared"))
        self.assertEqual(len(await self.fetch("SELECT * FROM teams")), 4)
        self.assertEqual(await self.fetch("SELECT * FROM reports"), [])

    async def test_new_discord_age_is_low_severity_not_a_game_account_age_claim(self):
        fresh = ((NOW - 86400) * 1000 - DISCORD_EPOCH_MS) << 22
        await self.sql("UPDATE team_members SET user_id=? WHERE id=1", (fresh,))
        await self.scan()
        row = (await radar_findings(GUILD, 1))[0]
        self.assertEqual(row["kind"], "new_discord_account")
        self.assertEqual(row["severity"], "low")
        self.assertIn("game-account age is unknown", row["summary"])
        self.assertEqual(row["evidence"]["age_days"], 1)

    async def test_high_kill_rate_needs_minimum_verified_individual_sample_and_skips_duplicates(
        self,
    ):
        for match_id in (1, 2):
            await self.sql(
                "INSERT INTO player_results(match_id,team_id,ign,uid,kills,verified) VALUES(?,1,'Player 1','100001',13,1)",
                (match_id,),
            )
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills,verified) VALUES(1,2,'Unverified','100002',100,0)"
        )
        self.assertEqual((await self.scan())["signals"], 0)
        await self.sql("INSERT INTO matches(id,tournament_id,match_no) VALUES(3,1,3)")
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills) VALUES(3,1,'Player 1','100001',13)"
        )
        await self.scan()
        rows = await radar_findings(GUILD, 1)
        self.assertEqual([r["kind"] for r in rows], ["high_recorded_kill_rate"])
        self.assertEqual(rows[0]["evidence"]["verified_matches"], 3)
        self.assertIn("not smurf proof", rows[0]["summary"])
        await self.sql(
            "INSERT INTO player_results(match_id,team_id,ign,uid,kills) VALUES(3,1,'Duplicate','100001',100)"
        )
        await self.scan()
        self.assertEqual(
            [r["kind"] for r in await radar_findings(GUILD, 1)], ["duplicate_player_results"]
        )

    async def test_reviews_validate_decisions_and_require_a_human_note(self):
        await self.sql("UPDATE team_members SET uid='100001' WHERE id=2")
        await self.scan()
        finding = (await radar_findings(GUILD, 1))[0]
        for decision, note in [("ban", "Do not ban"), ("confirmed", ""), ("cleared", "x" * 301)]:
            with self.assertRaises(ValueError):
                await review_finding(GUILD, finding["id"], 101, decision, note)
        self.assertEqual((await radar_findings(GUILD, 1))[0]["status"], "open")
