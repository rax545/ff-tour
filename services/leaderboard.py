from database.db import connect


async def leaderboard(tournament_id: int):
    db = await connect()
    cur = await db.execute(
        """
        SELECT
            t.id,
            t.name,
            t.tag,
            COALESCE(SUM(res.total_points), 0) AS pts,
            COALESCE(SUM(res.kills), 0) AS kills,
            COUNT(DISTINCT res.match_id) AS matches
        FROM (
            SELECT DISTINCT id, name, tag
            FROM teams
            WHERE tournament_id = ?
            UNION
            SELECT DISTINCT t.id, t.name, t.tag
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
        GROUP BY t.id, t.name, t.tag
        ORDER BY pts DESC, kills DESC, t.name ASC
        """,
        (tournament_id, tournament_id, tournament_id)
    )
    rows = await cur.fetchall()
    await db.close()
    return rows
