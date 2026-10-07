"""Free, non-monetary predictions. One editable pick until lock, ten points per win."""

import time

from services.arena_common import (
    database,
    log,
    many,
    match,
    match_teams,
    one,
    scheduled_timestamp,
    tournament,
)

WIN_POINTS = 10


def _now(now):
    return int(time.time() if now is None else now)


async def _pool(db, guild_id, pool_id, now=None):
    pool = await one(
        db,
        """SELECT p.*,m.match_no,m.map,m.scheduled_at,m.tournament_id,
        m.status AS match_status,m.stream_live,t.name AS tournament_name FROM prediction_pools p
        JOIN matches m ON m.id=p.match_id JOIN tournaments t ON t.id=m.tournament_id
        WHERE p.id=? AND p.guild_id=?""",
        (pool_id, guild_id),
    )
    if not pool:
        raise ValueError("Prediction arena not found in this server.")
    scheduled = scheduled_timestamp(pool["scheduled_at"])
    pool["effective_closes_at"] = (
        min(pool["closes_at"], scheduled) if scheduled is not None else pool["closes_at"]
    )
    if pool["status"] == "open":
        results_exist = await one(
            db,
            "SELECT id FROM results WHERE match_id=? UNION ALL SELECT id FROM player_results WHERE match_id=? LIMIT 1",
            (pool["match_id"], pool["match_id"]),
        )
        if (
            _now(now) >= pool["effective_closes_at"]
            or pool["stream_live"]
            or pool["match_status"] != "scheduled"
            or results_exist
        ):
            pool["status"] = "locked"
    return pool


async def _details(db, pool, user_id=None):
    pool["entries"] = await many(
        db,
        """SELECT e.*,COUNT(p.user_id) AS picks FROM prediction_entries e
        LEFT JOIN prediction_picks p ON p.pool_id=e.pool_id AND p.team_id=e.team_id
        WHERE e.pool_id=? GROUP BY e.pool_id,e.team_id ORDER BY e.team_id""",
        (pool["id"],),
    )
    pool["total_picks"] = sum(e["picks"] for e in pool["entries"])
    if user_id is not None:
        pool["my_pick"] = await one(
            db,
            "SELECT team_id,awarded_points FROM prediction_picks WHERE pool_id=? AND user_id=?",
            (pool["id"], user_id),
        )
    return pool


async def open_predictions(guild_id, match_id, closes_at, actor_id, *, now=None):
    now = _now(now)
    closes_at = int(closes_at)
    if not now < closes_at <= now + 30 * 86400:
        raise ValueError("The cutoff must be in the future and within 30 days.")
    async with database(write=True) as db:
        fixture = await match(db, match_id)
        tour = await tournament(db, fixture["tournament_id"])
        if (
            tour["status"] == "finished"
            or fixture["status"] != "scheduled"
            or fixture["stream_live"]
        ):
            raise ValueError(
                "Open predictions before the fixture starts or room credentials are released."
            )
        if await one(
            db,
            "SELECT id FROM results WHERE match_id=? UNION ALL SELECT id FROM player_results WHERE match_id=? LIMIT 1",
            (match_id, match_id),
        ):
            raise ValueError("A fixture with submitted results cannot accept new predictions.")
        scheduled = scheduled_timestamp(fixture["scheduled_at"])
        if scheduled is not None and (scheduled <= now or closes_at > scheduled):
            raise ValueError("The cutoff must be no later than the scheduled match start.")
        if await one(
            db,
            "SELECT id FROM prediction_pools WHERE guild_id=? AND match_id=?",
            (guild_id, match_id),
        ):
            raise ValueError(
                "An arena already exists for this fixture. It cannot be reopened or replaced."
            )
        teams = await match_teams(db, fixture, guild_id)
        if len(teams) < 2:
            raise ValueError("At least two registered opponents are required.")
        cursor = await db.execute(
            "INSERT INTO prediction_pools(guild_id,match_id,closes_at,created_by) VALUES(?,?,?,?)",
            (guild_id, match_id, closes_at, actor_id),
        )
        pool_id = cursor.lastrowid
        await db.executemany(
            "INSERT INTO prediction_entries(pool_id,team_id,name,tag) VALUES(?,?,?,?)",
            [(pool_id, t["id"], t["name"], t["tag"]) for t in teams],
        )
        await log(db, actor_id, "prediction_open", f"{guild_id}:{match_id}:{pool_id}:{closes_at}")
        return await _details(db, await _pool(db, guild_id, pool_id, now))


async def prediction_pool(guild_id, pool_id, user_id=None, *, now=None):
    async with database() as db:
        return await _details(db, await _pool(db, guild_id, pool_id, now), user_id)


async def list_predictions(guild_id):
    async with database() as db:
        ids = await many(
            db, "SELECT id FROM prediction_pools WHERE guild_id=? ORDER BY id DESC", (guild_id,)
        )
        return [await _pool(db, guild_id, row["id"]) for row in ids]


async def pick_team(guild_id, pool_id, user_id, team_id, *, now=None):
    if user_id <= 0:
        raise ValueError("A Discord account is required.")
    async with database(write=True) as db:
        pool = await _pool(db, guild_id, pool_id, now)
        if pool["status"] != "open":
            raise ValueError(
                "Predictions are locked, settled or cancelled. No late changes are allowed."
            )
        entry = await one(
            db, "SELECT * FROM prediction_entries WHERE pool_id=? AND team_id=?", (pool_id, team_id)
        )
        if not entry:
            raise ValueError("Pick one of this arena’s registered opponents.")
        await db.execute(
            """INSERT INTO prediction_picks(pool_id,user_id,team_id) VALUES(?,?,?)
            ON CONFLICT(pool_id,user_id) DO UPDATE SET team_id=excluded.team_id,updated_at=CURRENT_TIMESTAMP""",
            (pool_id, user_id, team_id),
        )
        return entry


async def lock_predictions(guild_id, pool_id, actor_id):
    async with database(write=True) as db:
        pool = await _pool(db, guild_id, pool_id)
        if pool["status"] in ("settled", "cancelled"):
            raise ValueError("A settled/cancelled arena cannot be relocked.")
        await db.execute("UPDATE prediction_pools SET status='locked' WHERE id=?", (pool_id,))
        await log(db, actor_id, "prediction_lock", f"{guild_id}:{pool_id}")


async def cancel_predictions(guild_id, pool_id, actor_id):
    async with database(write=True) as db:
        pool = await _pool(db, guild_id, pool_id)
        if pool["status"] == "settled":
            raise ValueError("A settled arena cannot be cancelled or award points again.")
        await db.execute("UPDATE prediction_pools SET status='cancelled' WHERE id=?", (pool_id,))
        await log(db, actor_id, "prediction_cancel", f"{guild_id}:{pool_id}")


async def settle_predictions(guild_id, pool_id, actor_id, *, now=None):
    async with database(write=True) as db:
        pool = await _pool(db, guild_id, pool_id, now)
        if pool["status"] == "settled":
            return await _details(db, pool)  # Concurrency/retry cannot double-award.
        if pool["status"] != "locked":
            raise ValueError(
                "Lock the arena before settlement. Cancelled arenas never award points."
            )
        node = await one(
            db,
            """SELECT n.* FROM bracket_nodes n JOIN brackets b ON b.id=n.bracket_id
            WHERE n.match_id=? AND b.guild_id=?""",
            (pool["match_id"], guild_id),
        )
        if node:
            if node["status"] != "finished":
                raise ValueError("Resolve the bound knockout node before settling predictions.")
            winner_id = node["winner_id"]
        else:
            rows = await many(
                db,
                """SELECT e.team_id,r.placement,r.verified FROM prediction_entries e
                LEFT JOIN results r ON r.team_id=e.team_id AND r.match_id=? WHERE e.pool_id=?""",
                (pool["match_id"], pool_id),
            )
            pending = await one(
                db,
                "SELECT id FROM results WHERE match_id=? AND verified=0 LIMIT 1",
                (pool["match_id"],),
            )
            if pending or any(r["verified"] != 1 for r in rows):
                raise ValueError(
                    "Every arena entrant needs a verified squad result before settlement."
                )
            placements = [r["placement"] for r in rows]
            if len(set(placements)) != len(rows) or any(
                not 1 <= p <= len(rows) for p in placements
            ):
                raise ValueError("Verified placements must be unique, valid lobby positions.")
            winners = [r["team_id"] for r in rows if r["placement"] == 1]
            if len(winners) != 1:
                raise ValueError("Exactly one verified first-place squad is required.")
            winner_id = winners[0]
        if not await one(
            db,
            "SELECT team_id FROM prediction_entries WHERE pool_id=? AND team_id=?",
            (pool_id, winner_id),
        ):
            raise ValueError("The confirmed winner is not an original arena entrant.")
        await db.execute(
            """UPDATE prediction_picks SET awarded_points=CASE WHEN team_id=? THEN ? ELSE 0 END
            WHERE pool_id=?""",
            (winner_id, WIN_POINTS, pool_id),
        )
        await db.execute(
            """UPDATE prediction_pools SET status='settled',winner_team_id=?,settled_by=?,
            settled_at=CURRENT_TIMESTAMP WHERE id=?""",
            (winner_id, actor_id, pool_id),
        )
        await log(db, actor_id, "prediction_settle", f"{guild_id}:{pool_id}:{winner_id}")
        return await _details(db, await _pool(db, guild_id, pool_id, now))


async def prediction_leaderboard(guild_id):
    async with database() as db:
        return await many(
            db,
            """SELECT v.user_id,SUM(v.awarded_points) AS points,
            SUM(CASE WHEN v.awarded_points>0 THEN 1 ELSE 0 END) AS correct,COUNT(*) AS predictions
            FROM prediction_picks v JOIN prediction_pools p ON p.id=v.pool_id
            WHERE p.guild_id=? AND p.status='settled' GROUP BY v.user_id
            ORDER BY points DESC,correct DESC,v.user_id ASC""",
            (guild_id,),
        )
