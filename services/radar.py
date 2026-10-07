"""Human-review-only roster/data signals. This is NOT a Garena smurf detector."""

import hashlib
import json
import time
from collections import defaultdict

from config import RADAR_KILLS_PER_MATCH, RADAR_MIN_MATCHES, RADAR_NEW_ACCOUNT_DAYS
from services.arena_common import database, log, many, one, registered_teams, text, tournament

DISCORD_EPOCH_MS = 1420070400000


def _fingerprint(kind, key):
    return hashlib.sha256(json.dumps([kind, key], sort_keys=True).encode()).hexdigest()


async def scan_rosters(guild_id, tournament_id, actor_id, *, now=None):
    """Scope evidence to this tournament; normal reuse of a roster in other seasons is fine."""
    now = int(time.time() if now is None else now)
    async with database(write=True) as db:
        await tournament(db, tournament_id)
        teams = await registered_teams(db, tournament_id)
        team_ids = {t["id"] for t in teams}
        rows = await many(
            db,
            """SELECT tm.* FROM team_members tm WHERE tm.team_id IN
            (SELECT id FROM teams WHERE tournament_id=? UNION SELECT team_id FROM registrations
            WHERE tournament_id=? AND status='registered') ORDER BY tm.id""",
            (tournament_id, tournament_id),
        )
        uid_map = defaultdict(list)
        account_teams = defaultdict(set)
        for team in teams:
            account_teams[team["captain_id"]].add(team["id"])
        for row in rows:
            if row["uid"].strip():
                uid_map[row["uid"].strip().casefold()].append(row)
            if row["user_id"] > 0:
                account_teams[row["user_id"]].add(row["team_id"])
        signals = []

        def add(kind, severity, summary, key, evidence):
            signals.append(
                {
                    "fingerprint": _fingerprint(kind, key),
                    "kind": kind,
                    "severity": severity,
                    "summary": summary,
                    "evidence": evidence,
                }
            )

        for uid, players in sorted(uid_map.items()):
            if len(players) > 1:
                accounts = sorted({p["user_id"] for p in players if p["user_id"] > 0})
                add(
                    "duplicate_uid",
                    "high" if len(accounts) > 1 else "medium",
                    "The same Free Fire UID occurs in multiple roster slots.",
                    [uid, sorted(p["id"] for p in players)],
                    {
                        "uid": uid,
                        "roster_ids": [p["id"] for p in players],
                        "team_ids": sorted({p["team_id"] for p in players}),
                        "discord_ids": accounts,
                    },
                )
        for account, ids in sorted(account_teams.items()):
            if account <= 0:
                continue
            if len(ids) > 1:
                add(
                    "multi_squad_account",
                    "medium",
                    "One Discord account is assigned to several squads in this tournament.",
                    [account, sorted(ids)],
                    {"discord_id": account, "team_ids": sorted(ids)},
                )
            created = ((account >> 22) + DISCORD_EPOCH_MS) // 1000
            if 0 <= now - created < RADAR_NEW_ACCOUNT_DAYS * 86400:
                add(
                    "new_discord_account",
                    "low",
                    f"Discord account is under {RADAR_NEW_ACCOUNT_DAYS} days old; game-account age is unknown.",
                    account,
                    {
                        "discord_id": account,
                        "team_ids": sorted(ids),
                        "created_unix": created,
                        "age_days": round((now - created) / 86400, 2),
                    },
                )
        results = await many(
            db,
            """SELECT pr.id,pr.uid,pr.team_id,pr.match_id,pr.kills
            FROM player_results pr JOIN matches m ON m.id=pr.match_id
            WHERE m.tournament_id=? AND pr.verified=1 AND TRIM(pr.uid)!='' ORDER BY pr.match_id,pr.id""",
            (tournament_id,),
        )
        per_uid_match = defaultdict(list)
        for row in results:
            uid = row["uid"].strip().casefold()
            if row["team_id"] in team_ids and any(
                p["team_id"] == row["team_id"] for p in uid_map.get(uid, [])
            ):
                per_uid_match[(uid, row["match_id"])].append(row)
        stats = defaultdict(list)
        for (uid, match_id), records in sorted(per_uid_match.items()):
            if len(records) > 1:
                add(
                    "duplicate_player_results",
                    "medium",
                    "Several verified individual rows share one UID/match; aggregate stats may be inflated.",
                    [uid, match_id],
                    {"uid": uid, "match_id": match_id, "result_ids": [r["id"] for r in records]},
                )
            else:
                stats[uid].append(records[0]["kills"])
        for uid, kills in sorted(stats.items()):
            average = sum(kills) / len(kills)
            if len(kills) >= RADAR_MIN_MATCHES and average >= RADAR_KILLS_PER_MATCH:
                add(
                    "high_recorded_kill_rate",
                    "low",
                    "High recorded individual kill rate. Skill or scoring errors are possible; this is not smurf proof.",
                    uid,
                    {
                        "uid": uid,
                        "verified_matches": len(kills),
                        "kills": sum(kills),
                        "kills_per_match": round(average, 2),
                        "threshold": RADAR_KILLS_PER_MATCH,
                    },
                )
        await db.execute(
            "UPDATE radar_findings SET active=0 WHERE guild_id=? AND tournament_id=?",
            (guild_id, tournament_id),
        )
        for signal in signals:
            await db.execute(
                """INSERT INTO radar_findings
                (guild_id,tournament_id,fingerprint,kind,severity,summary,evidence_json) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(guild_id,tournament_id,fingerprint) DO UPDATE SET active=1,
                severity=excluded.severity,summary=excluded.summary,evidence_json=excluded.evidence_json,
                last_seen=CURRENT_TIMESTAMP""",
                (
                    guild_id,
                    tournament_id,
                    signal["fingerprint"],
                    signal["kind"],
                    signal["severity"],
                    signal["summary"],
                    json.dumps(signal["evidence"], ensure_ascii=False),
                ),
            )
        await log(db, actor_id, "radar_scan", f"{guild_id}:{tournament_id}:{len(signals)} signals")
        return {"teams": len(teams), "roster_slots": len(rows), "signals": len(signals)}


async def radar_findings(guild_id, tournament_id, *, include_inactive=False):
    async with database() as db:
        rows = await many(
            db,
            """SELECT * FROM radar_findings WHERE guild_id=? AND tournament_id=?
            AND (active=1 OR ?=1) ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,id""",
            (guild_id, tournament_id, int(include_inactive)),
        )
        for row in rows:
            row["evidence"] = json.loads(row.pop("evidence_json"))
        return rows


async def review_finding(guild_id, finding_id, actor_id, decision, note):
    if decision not in ("cleared", "confirmed"):
        raise ValueError("Review decision must be cleared or confirmed.")
    note = text(note, "Review note", 300)
    async with database(write=True) as db:
        row = await one(
            db, "SELECT id FROM radar_findings WHERE id=? AND guild_id=?", (finding_id, guild_id)
        )
        if not row:
            raise ValueError("Finding not found in this server.")
        await db.execute(
            """UPDATE radar_findings SET status=?,reviewed_by=?,review_note=?,
            reviewed_at=CURRENT_TIMESTAMP WHERE id=?""",
            (decision, actor_id, note, finding_id),
        )
        await log(db, actor_id, "radar_review", f"{guild_id}:{finding_id}:{decision}:{note}")
