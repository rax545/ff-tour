from database.db import connect


async def leaderboard(tournament_id: int):
    """
    Standard squad leaderboard by tournament ID.
    """
    db = await connect()
    cur = await db.execute(
        """
        SELECT
            t.id,
            t.name,
            t.tag,
            COALESCE(t.batch, '') AS batch,
            COALESCE(t.section, '') AS section,
            COALESCE(SUM(res.total_points), 0) AS pts,
            COALESCE(SUM(res.kills), 0) AS kills,
            COUNT(DISTINCT res.match_id) AS matches
        FROM (
            SELECT DISTINCT id, name, tag, batch, section
            FROM teams
            WHERE tournament_id = ?
            UNION
            SELECT DISTINCT t.id, t.name, t.tag, t.batch, t.section
            FROM teams t
            JOIN registrations reg ON t.id = reg.team_id
            WHERE reg.tournament_id = ?
        ) t
        LEFT JOIN matches m
            ON m.tournament_id = ?
        LEFT JOIN results res
            ON res.match_id = m.id
            AND res.team_id = t.id
            AND res.verified = 1
        GROUP BY t.id, t.name, t.tag, t.batch, t.section
        ORDER BY pts DESC, kills DESC, t.name ASC
        """,
        (tournament_id, tournament_id, tournament_id)
    )
    rows = await cur.fetchall()
    await db.close()
    return rows


async def section_leaderboard(tournament_id: int = 0):
    """
    Aggregate points, kills, and team rankings by CSE Batch & Section for Root LU.
    """
    db = await connect()
    try:
        # Fetch team-level verified stats
        cur = await db.execute(
            """
            SELECT
                t.id,
                t.name,
                t.tag,
                COALESCE(NULLIF(TRIM(t.batch), ''), 'General') AS batch,
                COALESCE(NULLIF(TRIM(UPPER(t.section)), ''), 'Open') AS section,
                COALESCE(SUM(res.total_points), 0) AS pts,
                COALESCE(SUM(res.kills), 0) AS kills,
                COUNT(DISTINCT res.match_id) AS matches
            FROM (
                SELECT DISTINCT id, name, tag, batch, section, tournament_id
                FROM teams
                WHERE (? = 0 OR tournament_id = ?)
                UNION
                SELECT DISTINCT t.id, t.name, t.tag, t.batch, t.section, reg.tournament_id
                FROM teams t
                JOIN registrations reg ON t.id = reg.team_id
                WHERE (? = 0 OR reg.tournament_id = ?)
            ) t
            LEFT JOIN matches m
                ON (? = 0 OR m.tournament_id = ?)
                AND m.tournament_id = t.tournament_id
            LEFT JOIN results res
                ON res.match_id = m.id
                AND res.team_id = t.id
                AND res.verified = 1
            GROUP BY t.id, t.name, t.tag, batch, section
            ORDER BY pts DESC, kills DESC
            """,
            (tournament_id, tournament_id, tournament_id, tournament_id, tournament_id, tournament_id)
        )
        team_rows = await cur.fetchall()

        if not team_rows:
            return []

        # Aggregate per (batch, section)
        sections_map = {}
        for row in team_rows:
            key = (row["batch"], row["section"])
            if key not in sections_map:
                sections_map[key] = {
                    "batch": row["batch"],
                    "section": row["section"],
                    "pts": 0,
                    "kills": 0,
                    "matches": 0,
                    "teams_count": 0,
                    "top_team_name": row["name"],
                    "top_team_tag": row["tag"],
                    "top_team_pts": row["pts"],
                    "teams": []
                }
            sec = sections_map[key]
            sec["pts"] += row["pts"]
            sec["kills"] += row["kills"]
            sec["matches"] = max(sec["matches"], row["matches"])
            sec["teams_count"] += 1
            sec["teams"].append({
                "id": row["id"],
                "name": row["name"],
                "tag": row["tag"],
                "pts": row["pts"],
                "kills": row["kills"]
            })
            if row["pts"] > sec["top_team_pts"]:
                sec["top_team_pts"] = row["pts"]
                sec["top_team_name"] = row["name"]
                sec["top_team_tag"] = row["tag"]

        # Sort sections: total points DESC, total kills DESC, teams_count DESC
        sorted_sections = sorted(
            sections_map.values(),
            key=lambda s: (s["pts"], s["kills"], s["teams_count"]),
            reverse=True
        )
        return sorted_sections

    finally:
        await db.close()


async def top_fraggers(tournament_id: int = 0, limit: int = 10):
    """
    Get the top-killing fraggers across verified tournament results.
    """
    db = await connect()
    try:
        # 1. Check if individual player_results exist
        cur = await db.execute(
            """
            SELECT COUNT(*) AS c
            FROM player_results pr
            JOIN matches m ON m.id = pr.match_id
            WHERE (? = 0 OR m.tournament_id = ?) AND pr.verified = 1
            """,
            (tournament_id, tournament_id)
        )
        has_pr = (await cur.fetchone())["c"] > 0

        if has_pr:
            cur = await db.execute(
                """
                SELECT
                    pr.ign,
                    pr.uid,
                    COALESCE(tm.role, 'Player') AS role,
                    t.name AS team_name,
                    t.tag AS team_tag,
                    COALESCE(t.batch, '') AS batch,
                    COALESCE(t.section, '') AS section,
                    SUM(pr.kills) AS kills,
                    COUNT(DISTINCT pr.match_id) AS matches
                FROM player_results pr
                JOIN matches m ON m.id = pr.match_id
                JOIN teams t ON t.id = pr.team_id
                LEFT JOIN team_members tm ON tm.team_id = t.id AND (tm.ign = pr.ign OR tm.uid = pr.uid)
                WHERE (? = 0 OR m.tournament_id = ?) AND pr.verified = 1
                GROUP BY pr.ign, pr.uid, t.name, t.tag
                ORDER BY kills DESC, matches ASC, pr.ign ASC
                LIMIT ?
                """,
                (tournament_id, tournament_id, limit)
            )
            return await cur.fetchall()

        # 2. Aggregate from verified team results and active players
        cur = await db.execute(
            """
            SELECT
                tm.ign,
                tm.uid,
                tm.role,
                t.name AS team_name,
                t.tag AS team_tag,
                COALESCE(t.batch, '') AS batch,
                COALESCE(t.section, '') AS section,
                COALESCE(SUM(r.kills), 0) AS kills,
                COUNT(DISTINCT r.match_id) AS matches
            FROM results r
            JOIN matches m ON m.id = r.match_id
            JOIN teams t ON t.id = r.team_id
            JOIN team_members tm ON tm.team_id = t.id AND tm.is_sub = 0
            WHERE (? = 0 OR m.tournament_id = ?) AND r.verified = 1
            GROUP BY tm.id, tm.ign, tm.uid, tm.role, t.name, t.tag
            ORDER BY kills DESC, tm.id ASC
            LIMIT ?
            """,
            (tournament_id, tournament_id, limit)
        )
        return await cur.fetchall()

    finally:
        await db.close()
