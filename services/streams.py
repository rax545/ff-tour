"""Restart-safe, manually controlled live/replay metadata (not a streaming host)."""

from services.arena_common import database, log, many, match, match_teams, one, text
from utils.validation import validate_stream_url


async def start_stream(match_id, url, platform, actor_id, *, rebroadcast=False):
    url = validate_stream_url(url)
    platform = text(platform, "Platform", 40)
    async with database(write=True) as db:
        row = await match(db, match_id)
        if row["status"] in ("finished", "cancelled") or row["tournament_status"] == "finished":
            raise ValueError("A finished/cancelled fixture cannot be marked live.")
        if (
            row["stream_live"]
            and (row["stream_url"], row["stream_platform"]) == (url, platform)
            and not rebroadcast
        ):
            return row, False
        await db.execute(
            """UPDATE matches SET stream_url=?,stream_platform=?,stream_live=1,
            stream_started_at=CURRENT_TIMESTAMP,stream_ended_at=NULL,stream_revision=stream_revision+1,
            stream_channel_id=0,stream_message_id=0 WHERE id=?""",
            (url, platform, match_id),
        )
        # Live play must lock predictions even if staff supplied a later cutoff.
        await db.execute(
            "UPDATE prediction_pools SET status='locked' WHERE match_id=? AND status='open'",
            (match_id,),
        )
        await log(db, actor_id, "stream_start", str(match_id))
        return await match(db, match_id), True


async def stop_stream(match_id, actor_id=None):
    async with database(write=True) as db:
        row = await one(db, "SELECT id FROM matches WHERE id=?", (match_id,))
        if not row:
            return None
        await db.execute(
            """UPDATE matches SET
            stream_ended_at=CASE WHEN stream_live=1 THEN CURRENT_TIMESTAMP ELSE stream_ended_at END,
            stream_live=0 WHERE id=?""",
            (match_id,),
        )
        if actor_id is not None:
            await log(db, actor_id, "stream_stop", str(match_id))
        return await match(db, match_id)


async def get_stream(match_id):
    async with database() as db:
        try:
            return await match(db, match_id)
        except ValueError:
            return None


async def list_streams(tournament_id=0):
    async with database() as db:
        return await many(
            db,
            """SELECT m.id,m.match_no,m.map,m.stream_url,m.stream_platform,
            m.stream_started_at,t.name AS tournament_name FROM matches m
            JOIN tournaments t ON t.id=m.tournament_id WHERE m.stream_live=1
            AND (?=0 OR m.tournament_id=?) ORDER BY m.id DESC""",
            (tournament_id, tournament_id),
        )


async def stream_recipients(guild_id, match_id):
    """Globally deduplicate Discord accounts, including captains on several rosters."""
    async with database() as db:
        row = await match(db, match_id)
        teams = await match_teams(db, row, guild_id)
        recipients = {}
        for team in teams:
            members = await many(
                db, "SELECT user_id FROM team_members WHERE team_id=? AND user_id>0", (team["id"],)
            )
            for user_id in {m["user_id"] for m in members} | {team["captain_id"]}:
                if user_id > 0:
                    recipients.setdefault(user_id, team)
        return recipients, len(teams)


async def save_announcement(match_id, revision, channel_id, message_id):
    async with database(write=True) as db:
        cursor = await db.execute(
            """UPDATE matches SET stream_channel_id=?,stream_message_id=?
            WHERE id=? AND stream_revision=? AND stream_live=1""",
            (channel_id, message_id, match_id, revision),
        )
        return bool(cursor.rowcount)


async def is_current_stream(match_id, revision):
    async with database() as db:
        return bool(
            await one(
                db,
                "SELECT id FROM matches WHERE id=? AND stream_revision=? AND stream_live=1",
                (match_id, revision),
            )
        )
