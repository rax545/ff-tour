"""Server security & integrity scanner for the Root LU esports bot."""
import json
from datetime import datetime, timezone

from database.db import connect


async def run_security_scan(scanner_id: int, scope: str = "full") -> dict:
    """Run integrity checks across the database and persist the report.

    Returns a summary dict with a list of human-readable findings.
    """
    findings = []
    db = await connect()
    try:
        # 1. Squads with incomplete 4-man active rosters
        cur = await db.execute(
            """
            SELECT t.id, t.name, t.tag,
                   SUM(CASE WHEN tm.is_sub = 0 THEN 1 ELSE 0 END) AS starters
            FROM teams t
            LEFT JOIN team_members tm ON tm.team_id = t.id
            GROUP BY t.id
            HAVING starters < 4
            """
        )
        for row in await cur.fetchall():
            findings.append(
                f"⚠️ Squad **{row['name']}** `[{row['tag']}]` (ID #{row['id']}) has only "
                f"**{row['starters'] or 0}/4** active starters."
            )

        # 2. Duplicate Free Fire UIDs linked to different Discord accounts
        cur = await db.execute(
            """
            SELECT uid, COUNT(DISTINCT CASE WHEN user_id > 0 THEN user_id ELSE NULL END) AS users
            FROM team_members
            WHERE uid != ''
            GROUP BY uid
            HAVING users > 1
            """
        )
        for row in await cur.fetchall():
            findings.append(
                f"🚨 Free Fire UID `{row['uid']}` is linked to **{row['users']}** different Discord accounts."
            )

        # 3. Duplicate team names inside the same tournament
        cur = await db.execute(
            """
            SELECT tournament_id, name, COUNT(*) AS c
            FROM teams
            GROUP BY tournament_id, name
            HAVING c > 1
            """
        )
        for row in await cur.fetchall():
            findings.append(
                f"⚠️ Duplicate squad name **{row['name']}** in tournament #{row['tournament_id']} "
                f"({row['c']} occurrences)."
            )

        # 4. Unverified captains (no student verification on file)
        cur = await db.execute(
            """
            SELECT t.id, t.name, t.captain_id
            FROM teams t
            LEFT JOIN student_verifications sv ON sv.user_id = t.captain_id
            WHERE sv.id IS NULL
            """
        )
        for row in await cur.fetchall():
            findings.append(
                f"🎓 Captain <@{row['captain_id']}> of **{row['name']}** (team #{row['id']}) "
                f"is not a verified student."
            )

        # 5. Negative coin balances (economy integrity)
        cur = await db.execute("SELECT user_id, balance FROM coins WHERE balance < 0")
        for row in await cur.fetchall():
            findings.append(
                f"💰 Negative coin balance detected for user <@{row['user_id']}>: **{row['balance']}**."
            )

        # 6. Open dispute reports
        cur = await db.execute("SELECT COUNT(*) AS c FROM reports WHERE status='open'")
        open_reports = (await cur.fetchone())["c"]
        if open_reports:
            findings.append(f"📋 **{open_reports}** open dispute report(s) awaiting staff review.")

        # 7. Matches stuck in 'room_open' state for a long time (informational)
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM matches WHERE status='room_open'"
        )
        stale_rooms = (await cur.fetchone())["c"]
        if stale_rooms:
            findings.append(
                f"🔑 **{stale_rooms}** match room(s) are still open — remember `/match end` after play."
            )

        summary = {
            "scanner_id": scanner_id,
            "scope": scope,
            "findings_count": len(findings),
            "findings": findings,
            "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        await db.execute(
            """
            INSERT INTO security_scans (scanner_id, scope, findings_count, findings)
            VALUES (?, ?, ?, ?)
            """,
            (scanner_id, scope, len(findings), json.dumps(findings)),
        )
        await db.commit()
        return summary
    finally:
        await db.close()


async def recent_scans(limit: int = 10):
    db = await connect()
    try:
        cur = await db.execute(
            "SELECT * FROM security_scans ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 25)),),
        )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["findings_list"] = json.loads(d["findings"])
            except Exception:
                d["findings_list"] = []
            rows.append(d)
        return rows
    finally:
        await db.close()
