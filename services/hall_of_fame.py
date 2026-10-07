"""Immutable, staff-finalized champions archive. Revocation retains audit history."""

import json

from services.arena_common import database, log, many, one, registered_teams, text, tournament
from services.player_stats import verified_fraggers


def _decode(record):
    record["podium"] = json.loads(record.pop("podium_json"))
    record["mvp"] = json.loads(record.pop("mvp_json"))
    return record


async def _standings(db, tournament_id, teams):
    rows = await many(
        db,
        """SELECT t.id,t.name,t.tag,COALESCE(SUM(r.total_points),0) AS points,
        COALESCE(SUM(r.kills),0) AS kills, COUNT(r.id) AS matches,
        COALESCE(SUM(CASE WHEN r.placement=1 THEN 1 ELSE 0 END),0) AS wins
        FROM teams t LEFT JOIN results r ON r.team_id=t.id AND r.verified=1
        AND r.match_id IN (SELECT id FROM matches WHERE tournament_id=?)
        WHERE t.id IN (SELECT id FROM teams WHERE tournament_id=? UNION
            SELECT team_id FROM registrations WHERE tournament_id=? AND status='registered')
        GROUP BY t.id ORDER BY points DESC,kills DESC,wins DESC,t.id ASC""",
        (tournament_id, tournament_id, tournament_id),
    )
    return [r for r in rows if r["id"] in {t["id"] for t in teams}]


async def induct_tournament(guild_id, tournament_id, actor_id):
    async with database(write=True) as db:
        existing = await one(
            db,
            "SELECT * FROM hall_of_fame WHERE guild_id=? AND tournament_id=?",
            (guild_id, tournament_id),
        )
        if existing:
            if existing["revoked_at"]:
                raise ValueError(
                    "This archive was revoked. Its historical record cannot be silently replaced."
                )
            return _decode(existing)
        tour = await tournament(db, tournament_id)
        teams = await registered_teams(db, tournament_id)
        if len(teams) < 2:
            raise ValueError(
                "At least two registered squads are required for a championship archive."
            )
        standings = await _standings(db, tournament_id, teams)
        bracket = await one(
            db,
            "SELECT * FROM brackets WHERE guild_id=? AND tournament_id=?",
            (guild_id, tournament_id),
        )
        if bracket:
            if bracket["status"] != "finished":
                raise ValueError("Finish the knockout final before inducting this tournament.")
            final = await one(
                db,
                "SELECT * FROM bracket_nodes WHERE bracket_id=? ORDER BY round_no DESC LIMIT 1",
                (bracket["id"],),
            )
            if final["status"] != "finished":
                raise ValueError("The final needs a staff-confirmed result, not a BYE.")
            entries = await many(
                db, "SELECT * FROM bracket_entries WHERE bracket_id=?", (bracket["id"],)
            )
            names = {e["team_id"]: e for e in entries}
            stats = {s["id"]: s for s in standings}
            runner = final["team_b"] if final["winner_id"] == final["team_a"] else final["team_a"]
            podium = []
            for team_id in (final["winner_id"], runner):
                entry = names[team_id]
                podium.append(
                    {
                        **stats.get(team_id, {"points": 0, "kills": 0, "matches": 0, "wins": 0}),
                        "id": team_id,
                        "name": entry["name"],
                        "tag": entry["tag"],
                    }
                )
            format_name = "knockout"
        else:
            fixtures = await many(
                db, "SELECT id FROM matches WHERE tournament_id=?", (tournament_id,)
            )
            pending = await one(
                db,
                """SELECT id FROM results WHERE verified=0 AND match_id IN
                (SELECT id FROM matches WHERE tournament_id=?) LIMIT 1""",
                (tournament_id,),
            )
            if not fixtures or pending or any(s["matches"] != len(fixtures) for s in standings):
                raise ValueError(
                    "Every registered squad needs a verified result for every BR fixture; pending/missing scores block finalization."
                )
            if await one(
                db,
                "SELECT id FROM matches WHERE tournament_id=? AND stream_live=1 LIMIT 1",
                (tournament_id,),
            ):
                raise ValueError("Stop live broadcasts before finalizing the championship.")
            scores = await many(
                db,
                """SELECT r.match_id,r.placement FROM results r JOIN matches m ON m.id=r.match_id
                WHERE m.tournament_id=? AND r.verified=1 AND r.team_id IN
                (SELECT id FROM teams WHERE tournament_id=? UNION SELECT team_id FROM registrations
                 WHERE tournament_id=? AND status='registered')""",
                (tournament_id, tournament_id, tournament_id),
            )
            for fixture in fixtures:
                placements = [s["placement"] for s in scores if s["match_id"] == fixture["id"]]
                if sorted(placements) != list(range(1, len(teams) + 1)):
                    raise ValueError(
                        "Each BR fixture needs a unique, complete sequence of verified lobby placements."
                    )
            await db.execute(
                "UPDATE matches SET status='finished' WHERE tournament_id=?", (tournament_id,)
            )
            await db.execute(
                "UPDATE prediction_pools SET status='locked' WHERE match_id IN (SELECT id FROM matches WHERE tournament_id=?) AND status='open'",
                (tournament_id,),
            )
            podium = standings[:3]
            format_name = "battle_royale"
        fraggers = await verified_fraggers(db, tournament_id, 1)
        mvp = {k: fraggers[0][k] for k in ("ign", "kills", "damage", "matches")} if fraggers else {}
        cursor = await db.execute(
            """INSERT INTO hall_of_fame
            (guild_id,tournament_id,tournament_name,format,podium_json,mvp_json,inducted_by) VALUES(?,?,?,?,?,?,?)""",
            (
                guild_id,
                tournament_id,
                tour["name"],
                format_name,
                json.dumps(podium, ensure_ascii=False),
                json.dumps(mvp, ensure_ascii=False),
                actor_id,
            ),
        )
        await db.execute("UPDATE tournaments SET status='finished' WHERE id=?", (tournament_id,))
        await log(
            db, actor_id, "hall_of_fame_induct", f"{guild_id}:{tournament_id}:{cursor.lastrowid}"
        )
        return _decode(await one(db, "SELECT * FROM hall_of_fame WHERE id=?", (cursor.lastrowid,)))


async def hall_of_fame(guild_id, tournament_id=0):
    async with database() as db:
        rows = await many(
            db,
            """SELECT * FROM hall_of_fame WHERE guild_id=? AND revoked_at IS NULL
            AND (?=0 OR tournament_id=?) ORDER BY id DESC""",
            (guild_id, tournament_id, tournament_id),
        )
        return [_decode(row) for row in rows]


async def revoke_induction(guild_id, archive_id, actor_id, reason):
    reason = text(reason, "Revocation reason", 300)
    async with database(write=True) as db:
        cursor = await db.execute(
            """UPDATE hall_of_fame SET revoked_at=CURRENT_TIMESTAMP,revoke_reason=?
            WHERE id=? AND guild_id=? AND revoked_at IS NULL""",
            (reason, archive_id, guild_id),
        )
        if not cursor.rowcount:
            raise ValueError("Archive not found in this server or already revoked.")
        await log(db, actor_id, "hall_of_fame_revoke", f"{guild_id}:{archive_id}:{reason}")
