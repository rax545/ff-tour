"""Individual player aggregation for passports and FUT-style ultimate cards."""
from database.db import connect

# FUT-style attribute keys in display order.
ATTRIBUTE_KEYS = ("PAC", "SHO", "PAS", "DRI", "DEF", "PHY")

ATTRIBUTE_LABELS = {
    "PAC": "Pace",
    "SHO": "Shooting",
    "PAS": "Passing",
    "DRI": "Dribbling",
    "DEF": "Defense",
    "PHY": "Physical",
}


def compute_attributes(kills: int, damage: int, matches: int, wins: int) -> dict:
    """Deterministically derive the 6 FUT-style attributes from verified stats."""
    kills = max(0, int(kills))
    damage = max(0, int(damage))
    matches = max(0, int(matches))
    wins = max(0, int(wins))
    return {
        "PAC": min(99, 40 + kills * 2 + matches * 3),
        "SHO": min(99, 35 + kills * 3 + wins),
        "PAS": min(99, 35 + matches * 4 + wins * 2),
        "DRI": min(99, 40 + int(damage // 100) + matches * 2),
        "DEF": min(99, 30 + matches * 3 + wins),
        "PHY": min(99, 35 + wins * 4 + matches * 2),
    }


def compute_ovr(attributes: dict) -> int:
    """Overall rating = rounded mean of the 6 attributes (capped at 99)."""
    vals = [int(attributes[k]) for k in ATTRIBUTE_KEYS]
    return min(99, round(sum(vals) / len(vals)))


async def player_card_profile(user_id: int) -> dict:
    """Aggregate a player's verified identity + stats for cards.

    Identity comes from team rosters; stats come from verified individual
    ``player_results`` (falling back to zeroes when none exist).
    """
    db = await connect()
    try:
        cur = await db.execute(
            """
            SELECT tm.ign, tm.uid, tm.role, tm.is_sub,
                   t.name AS team_name, t.tag AS team_tag, t.batch, t.section
            FROM team_members tm
            JOIN teams t ON t.id = tm.team_id
            WHERE tm.user_id = ?
            ORDER BY tm.is_sub ASC, tm.id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        identity = await cur.fetchone()
        if not identity:
            return {}

        # Verified individual stats across every roster this UID appears on.
        cur = await db.execute(
            """
            SELECT COALESCE(SUM(pr.kills), 0) AS kills,
                   COALESCE(SUM(pr.damage), 0) AS damage,
                   COUNT(DISTINCT pr.match_id) AS matches
            FROM player_results pr
            WHERE pr.verified = 1 AND pr.uid != '' AND EXISTS (
                SELECT 1 FROM team_members tm
                WHERE tm.user_id = ? AND tm.uid = pr.uid AND tm.team_id = pr.team_id
            )
            """,
            (user_id,),
        )
        stats = dict(await cur.fetchone())

        # Verified wins: matches where the player's team placed #1.
        cur = await db.execute(
            """
            SELECT COUNT(DISTINCT r.match_id) AS wins
            FROM results r
            JOIN team_members tm ON tm.team_id = r.team_id
            WHERE r.verified = 1 AND r.placement = 1 AND tm.user_id = ?
            """,
            (user_id,),
        )
        wins = (await cur.fetchone())["wins"]

        cur = await db.execute(
            "SELECT full_name, batch, section, department FROM student_verifications WHERE user_id=?",
            (user_id,),
        )
        student = await cur.fetchone()

        attributes = compute_attributes(stats["kills"], stats["damage"], stats["matches"], wins)
        profile = {
            "ign": identity["ign"],
            "uid": identity["uid"],
            "role": identity["role"],
            "is_sub": bool(identity["is_sub"]),
            "team_name": identity["team_name"],
            "team_tag": identity["team_tag"],
            "batch": identity["batch"] or (student["batch"] if student else ""),
            "section": identity["section"] or (student["section"] if student else ""),
            "kills": int(stats["kills"]),
            "damage": int(stats["damage"]),
            "matches": int(stats["matches"]),
            "wins": int(wins),
            "attributes": attributes,
            "ovr": compute_ovr(attributes),
            "student_name": student["full_name"] if student else "",
        }
        return profile
    finally:
        await db.close()
