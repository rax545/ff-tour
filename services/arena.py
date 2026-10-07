"""Persisted player identity, certificate registry and stream lifecycle."""

import secrets

from database.db import connect
from utils.validation import validate_stream_url as validate_stream_url


async def player_passport(user_id):
    """Self-only passport data; do not expose student IDs or assign team kills to players."""
    db = await connect()
    try:
        cur = await db.execute(
            """SELECT DISTINCT tm.uid, tm.ign, tm.role, tm.is_sub,
            t.name AS team_name, t.tag, t.batch, t.section, t.id AS team_id
            FROM team_members tm JOIN teams t ON t.id=tm.team_id
            WHERE tm.user_id=? ORDER BY t.id DESC, tm.id DESC""",
            (user_id,),
        )
        rosters = [dict(r) for r in await cur.fetchall()]
        # UID identifies a player across tournament rosters. EXISTS avoids join multiplication.
        cur = await db.execute(
            """SELECT COALESCE(SUM(pr.kills),0) AS kills,
            COALESCE(SUM(pr.damage),0) AS damage, COUNT(DISTINCT pr.match_id) AS matches
            FROM player_results pr JOIN matches m ON m.id=pr.match_id
            WHERE pr.verified=1 AND TRIM(pr.uid)!='' AND pr.kills>=0 AND pr.damage>=0
            AND EXISTS (SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id
                WHERE tm.user_id=? AND LOWER(TRIM(tm.uid))=LOWER(TRIM(pr.uid)) AND tm.team_id=pr.team_id
                AND (t.tournament_id=m.tournament_id OR EXISTS (SELECT 1 FROM registrations r
                    WHERE r.team_id=t.id AND r.tournament_id=m.tournament_id AND r.status='registered')))
            AND NOT EXISTS (SELECT 1 FROM team_members conflict WHERE conflict.user_id>0 AND conflict.user_id!=?
                AND LOWER(TRIM(conflict.uid))=LOWER(TRIM(pr.uid)))
            AND NOT EXISTS (SELECT 1 FROM player_results dup WHERE dup.match_id=pr.match_id
                AND LOWER(TRIM(dup.uid))=LOWER(TRIM(pr.uid)) AND dup.id!=pr.id)""",
            (user_id, user_id),
        )
        stats = dict(await cur.fetchone())
        cur = await db.execute(
            """SELECT department, batch, section, status
            FROM student_verifications WHERE user_id=? AND status='verified' """,
            (user_id,),
        )
        student = await cur.fetchone()
        return rosters, stats, dict(student) if student else None
    finally:
        await db.close()


async def issue_certificate(guild_id, tournament_id, team_id, recipient_id, award, actor_id):
    award = award.strip()
    if not award or len(award) > 80:
        raise ValueError("Award must contain 1–80 characters.")
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            """SELECT t.name, tr.name AS tournament_name,
            (SELECT ign FROM team_members WHERE team_id=t.id AND user_id=? ORDER BY id LIMIT 1) AS ign
            FROM teams t JOIN tournaments tr ON tr.id=? WHERE t.id=?
            AND (t.tournament_id=? OR EXISTS (SELECT 1 FROM registrations r
                WHERE r.team_id=t.id AND r.tournament_id=?))
            AND (t.captain_id=? OR EXISTS (SELECT 1 FROM team_members tm
                WHERE tm.team_id=t.id AND tm.user_id=?))""",
            (
                recipient_id,
                tournament_id,
                team_id,
                tournament_id,
                tournament_id,
                recipient_id,
                recipient_id,
            ),
        )
        team = await cur.fetchone()
        if not team:
            raise ValueError(
                "Recipient must be a registered squad member or captain in this tournament."
            )
        name = team["ign"] or f"Captain {recipient_id}"
        code = "RLU-" + secrets.token_hex(12).upper()
        await db.execute(
            """INSERT INTO certificates
            (code,guild_id,tournament_id,team_id,recipient_id,recipient_name,award,issued_by)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(guild_id,tournament_id,team_id,recipient_id,award)
            DO NOTHING""",
            (code, guild_id, tournament_id, team_id, recipient_id, name, award, actor_id),
        )
        cur = await db.execute(
            """SELECT c.*, t.name AS team_name, tr.name AS tournament_name
            FROM certificates c JOIN teams t ON t.id=c.team_id JOIN tournaments tr ON tr.id=c.tournament_id
            WHERE c.guild_id=? AND c.tournament_id=? AND c.team_id=? AND c.recipient_id=? AND c.award=?""",
            (guild_id, tournament_id, team_id, recipient_id, award),
        )
        cert = dict(await cur.fetchone())
        if cert["revoked_at"]:
            raise ValueError(
                "This award was revoked; issue a distinct award or contact the issuer."
            )
        await db.execute(
            "INSERT INTO audit_logs(actor_id,action,details) VALUES(?,'certificate_issue',?)",
            (actor_id, cert["code"]),
        )
        await db.commit()
        return cert
    finally:
        await db.close()


async def verify_certificate(guild_id, code):
    db = await connect()
    try:
        cur = await db.execute(
            """SELECT c.*, t.name AS team_name, tr.name AS tournament_name
            FROM certificates c JOIN teams t ON t.id=c.team_id JOIN tournaments tr ON tr.id=c.tournament_id
            WHERE c.guild_id=? AND c.code=?""",
            (guild_id, code.strip().upper()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def revoke_certificate(guild_id, code, actor_id):
    db = await connect()
    try:
        cur = await db.execute(
            """UPDATE certificates SET revoked_at=CURRENT_TIMESTAMP
            WHERE guild_id=? AND code=? AND revoked_at IS NULL""",
            (guild_id, code.strip().upper()),
        )
        if cur.rowcount:
            await db.execute(
                "INSERT INTO audit_logs(actor_id,action,details) VALUES(?,'certificate_revoke',?)",
                (actor_id, code.strip().upper()),
            )
        await db.commit()
        return bool(cur.rowcount)
    finally:
        await db.close()


async def stream_status(match_id, stop=False):
    """Compatibility API for existing callers; lifecycle is implemented in streams."""
    from services.streams import get_stream, stop_stream

    return await stop_stream(match_id) if stop else await get_stream(match_id)
