"""Roster-authorized private strategy notes and restart-safe, expiring ready checks."""

import time

from services.arena_common import (
    database,
    log,
    many,
    match,
    match_teams,
    one,
    scheduled_timestamp,
    squad_access,
    text,
)

MAPS = ("Bermuda", "Purgatory", "Kalahari", "Alpine", "NexTerra")


async def save_plan(guild_id, team_id, actor_id, map_name, drop_zone, strategy, *, is_staff=False):
    if map_name not in MAPS:
        raise ValueError("Select an official Free Fire map.")
    drop_zone = text(drop_zone, "Drop zone", 80)
    strategy = text(strategy, "Strategy", 1500)
    async with database(write=True) as db:
        await squad_access(db, team_id, actor_id, is_staff=is_staff, captain_only=True)
        await db.execute(
            """INSERT INTO squad_plans(guild_id,team_id,map_name,drop_zone,strategy,updated_by)
            VALUES(?,?,?,?,?,?) ON CONFLICT(guild_id,team_id) DO UPDATE SET map_name=excluded.map_name,
            drop_zone=excluded.drop_zone,strategy=excluded.strategy,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP""",
            (guild_id, team_id, map_name, drop_zone, strategy, actor_id),
        )
        # Strategy content is private and is intentionally not copied into audit_logs.
        await log(db, actor_id, "squad_plan_save", f"{guild_id}:{team_id}")


async def squad_briefing(guild_id, team_id, actor_id, *, is_staff=False):
    async with database() as db:
        team, members, ids = await squad_access(db, team_id, actor_id, is_staff=is_staff)
        plan = await one(
            db, "SELECT * FROM squad_plans WHERE guild_id=? AND team_id=?", (guild_id, team_id)
        )
        checks = await many(
            db,
            """SELECT c.*,m.match_no FROM squad_ready_checks c JOIN matches m ON m.id=c.match_id
            WHERE c.guild_id=? AND c.team_id=? ORDER BY c.id DESC LIMIT 5""",
            (guild_id, team_id),
        )
        return {
            "team": team,
            "members": members,
            "discord_ids": sorted(ids),
            "plan": plan,
            "checks": checks,
        }


async def open_ready_check(guild_id, team_id, match_id, actor_id, *, is_staff=False, now=None):
    now = int(time.time() if now is None else now)
    async with database(write=True) as db:
        team, members, ids = await squad_access(
            db, team_id, actor_id, is_staff=is_staff, captain_only=True
        )
        fixture = await match(db, match_id)
        entrants = await match_teams(db, fixture, guild_id)
        if team_id not in {t["id"] for t in entrants} or fixture["status"] in (
            "finished",
            "cancelled",
        ):
            raise ValueError("Choose an upcoming fixture that includes this squad.")
        existing = await one(
            db,
            "SELECT * FROM squad_ready_checks WHERE guild_id=? AND team_id=? AND match_id=?",
            (guild_id, team_id, match_id),
        )
        if existing:
            if existing["status"] == "closed" or existing["expires_at"] <= now:
                raise ValueError(
                    "This fixture’s ready check has closed/expired and cannot be reopened."
                )
            return existing, False
        start = scheduled_timestamp(fixture["scheduled_at"])
        expires = min(now + 3600, start) if start is not None else now + 3600
        if expires <= now:
            raise ValueError("The scheduled match has already started.")
        cursor = await db.execute(
            """INSERT INTO squad_ready_checks
            (guild_id,team_id,match_id,opened_by,expires_at) VALUES(?,?,?,?,?)""",
            (guild_id, team_id, match_id, actor_id, expires),
        )
        await log(
            db, actor_id, "squad_ready_open", f"{guild_id}:{team_id}:{match_id}:{cursor.lastrowid}"
        )
        return await one(
            db, "SELECT * FROM squad_ready_checks WHERE id=?", (cursor.lastrowid,)
        ), True


async def _ready_check(db, guild_id, check_id, actor_id, is_staff):
    row = await one(
        db,
        """SELECT c.*,t.name AS team_name,m.match_no,m.scheduled_at,
        m.status AS match_status FROM squad_ready_checks c JOIN teams t ON t.id=c.team_id
        JOIN matches m ON m.id=c.match_id WHERE c.id=? AND c.guild_id=?""",
        (check_id, guild_id),
    )
    if not row:
        raise ValueError("Ready check not found in this server.")
    team, members, ids = await squad_access(db, row["team_id"], actor_id, is_staff=is_staff)
    responses = await many(
        db, "SELECT user_id,ready FROM squad_ready_responses WHERE check_id=?", (check_id,)
    )
    row["ready_ids"] = sorted(
        {r["user_id"] for r in responses if r["ready"] and r["user_id"] in ids}
    )
    row["pending_ids"] = sorted(ids - set(row["ready_ids"]))
    row["unlinked_slots"] = sum(m["user_id"] <= 0 for m in members)
    return row, ids


def _expired(row, now):
    start = scheduled_timestamp(row["scheduled_at"])
    return (
        row["status"] == "closed"
        or row["expires_at"] <= now
        or row["match_status"] in ("finished", "cancelled")
        or (start is not None and start <= now)
    )


async def ready_status(guild_id, check_id, actor_id, *, is_staff=False, now=None):
    now = int(time.time() if now is None else now)
    async with database() as db:
        row, ids = await _ready_check(db, guild_id, check_id, actor_id, is_staff)
        row["status"] = "closed" if _expired(row, now) else "open"
        return row


async def set_ready(guild_id, check_id, actor_id, ready=True, *, now=None):
    now = int(time.time() if now is None else now)
    async with database(write=True) as db:
        # Staff may see the briefing, but can only mark their own roster readiness.
        row, ids = await _ready_check(db, guild_id, check_id, actor_id, False)
        if _expired(row, now):
            raise ValueError("This ready check is closed/expired or the fixture has started.")
        await db.execute(
            """INSERT INTO squad_ready_responses(check_id,user_id,ready) VALUES(?,?,?)
            ON CONFLICT(check_id,user_id) DO UPDATE SET ready=excluded.ready,updated_at=CURRENT_TIMESTAMP""",
            (check_id, actor_id, int(ready)),
        )
        updated, ids = await _ready_check(db, guild_id, check_id, actor_id, False)
        return updated


async def close_ready_check(guild_id, check_id, actor_id, *, is_staff=False):
    async with database(write=True) as db:
        row, ids = await _ready_check(db, guild_id, check_id, actor_id, is_staff)
        await squad_access(db, row["team_id"], actor_id, is_staff=is_staff, captain_only=True)
        await db.execute("UPDATE squad_ready_checks SET status='closed' WHERE id=?", (check_id,))
        await log(db, actor_id, "squad_ready_close", f"{guild_id}:{check_id}")
