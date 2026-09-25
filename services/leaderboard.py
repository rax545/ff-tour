from database.db import connect
async def leaderboard(tournament_id):
    db=await connect(); cur=await db.execute('''SELECT t.name,t.tag,COALESCE(SUM(r.total_points),0) pts,COALESCE(SUM(r.kills),0) kills,COUNT(r.id) matches FROM teams t JOIN matches m ON m.tournament_id=t.tournament_id LEFT JOIN results r ON r.match_id=m.id AND r.team_id=t.id AND r.verified=1 WHERE t.tournament_id=? GROUP BY t.id ORDER BY pts DESC,kills DESC''',(tournament_id,)); rows=await cur.fetchall(); await db.close(); return rows
