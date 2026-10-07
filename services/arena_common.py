"""Small shared SQL helpers. All mutating arena workflows use IMMEDIATE transactions."""

import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from database.db import connect


@asynccontextmanager
async def database(*, write=False):
    db = await connect()
    try:
        if write:
            await db.execute("BEGIN IMMEDIATE")
        yield db
        if write:
            await db.commit()
    except BaseException:
        if write:
            await db.rollback()
        raise
    finally:
        await db.close()


async def one(db, sql, params=()):
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    return dict(row) if row else None


async def many(db, sql, params=()):
    cursor = await db.execute(sql, params)
    return [dict(row) for row in await cursor.fetchall()]


async def log(db, actor_id, action, details):
    await db.execute(
        "INSERT INTO audit_logs(actor_id, action, details) VALUES(?, ?, ?)",
        (actor_id, action, str(details)),
    )


async def tournament(db, tournament_id):
    row = await one(db, "SELECT * FROM tournaments WHERE id=?", (tournament_id,))
    if not row:
        raise ValueError("Tournament not found.")
    return row


async def match(db, match_id):
    row = await one(
        db,
        """SELECT m.*, t.name AS tournament_name, t.status AS tournament_status FROM matches m
        JOIN tournaments t ON t.id=m.tournament_id WHERE m.id=?""",
        (match_id,),
    )
    if not row:
        raise ValueError("Match not found.")
    return row


async def registered_teams(db, tournament_id):
    """Match the existing bot's direct-team + registration membership convention."""
    return await many(
        db,
        """SELECT t.* FROM teams t WHERE t.tournament_id=? OR EXISTS (
        SELECT 1 FROM registrations r WHERE r.team_id=t.id AND r.tournament_id=?
        AND r.status='registered') ORDER BY t.id""",
        (tournament_id, tournament_id),
    )


async def match_teams(db, row, guild_id):
    """A bound knockout fixture has two entrants; BR fixtures use the whole lobby."""
    node = await one(
        db,
        """SELECT n.* FROM bracket_nodes n JOIN brackets b ON b.id=n.bracket_id
        WHERE n.match_id=? AND b.guild_id=?""",
        (row["id"], guild_id),
    )
    if node:
        if node["status"] not in ("ready", "finished"):
            raise ValueError("This bracket fixture does not yet have two opponents.")
        teams = await many(
            db,
            "SELECT * FROM teams WHERE id IN (?, ?) ORDER BY id",
            (node["team_a"], node["team_b"]),
        )
        if len(teams) != 2:
            raise ValueError(
                "A bracket entrant was removed. Contact staff before using this fixture."
            )
        return teams
    return await registered_teams(db, row["tournament_id"])


async def squad_access(db, team_id, actor_id, *, is_staff=False, captain_only=False):
    team = await one(db, "SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise ValueError("Squad not found.")
    members = await many(
        db, "SELECT * FROM team_members WHERE team_id=? ORDER BY is_sub, id", (team_id,)
    )
    ids = {m["user_id"] for m in members if m["user_id"] > 0} | {team["captain_id"]}
    permitted = actor_id == team["captain_id"] if captain_only else actor_id in ids
    if not is_staff and not permitted:
        raise ValueError(
            "Only the squad captain or staff can do this."
            if captain_only
            else "Only current squad members or staff can view this private briefing."
        )
    return team, members, ids


def text(value, label, limit):
    value = value.strip()
    if not value or len(value) > limit or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{label} must contain 1–{limit} characters without control characters.")
    return value


def page_slice(rows, page, size):
    total = max(1, (len(rows) + size - 1) // size)
    if not 1 <= page <= total:
        raise ValueError(f"Page must be between 1 and {total}.")
    return rows[(page - 1) * size : page * size], total


def scheduled_timestamp(value):
    """Only unambiguous absolute schedules participate in automatic vote cutoffs."""
    from services.reminders import local_tz, parse_schedule_time

    value = (value or "").strip()
    discord_time = re.fullmatch(r"<t:(\d+)(?::[tTdDfFR])?>", value)
    if discord_time:
        return int(discord_time[1])
    if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(date.replace(tzinfo=date.tzinfo or local_tz()).timestamp())
        except ValueError:
            return None
    if re.match(r"^(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}) ", value):
        try:
            return int(
                parse_schedule_time(
                    value, now=datetime(1970, 1, 1, tzinfo=timezone.utc)
                ).timestamp()
            )
        except ValueError:
            return None
    return None
