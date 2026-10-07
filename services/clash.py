"""Public clash-poster data: no UIDs, student IDs, private notes or room credentials."""

from services.arena_common import database, many, match, match_teams, one


async def clash_poster_data(guild_id, match_id, team_a_id, team_b_id):
    if team_a_id == team_b_id:
        raise ValueError("Choose two different squads.")
    async with database() as db:
        fixture = await match(db, match_id)
        entrants = {t["id"]: t for t in await match_teams(db, fixture, guild_id)}
        if team_a_id not in entrants or team_b_id not in entrants:
            raise ValueError("Both squads must be entrants in this fixture.")
        squads = []
        for team_id in (team_a_id, team_b_id):
            team = entrants[team_id]
            stats = await one(
                db,
                """SELECT COALESCE(SUM(r.total_points),0) AS points,
                COALESCE(SUM(r.kills),0) AS kills, COUNT(*) AS matches FROM results r
                JOIN matches m ON m.id=r.match_id WHERE r.team_id=? AND r.verified=1 AND m.tournament_id=?""",
                (team_id, fixture["tournament_id"]),
            )
            lineup = await many(
                db,
                "SELECT ign,role,is_sub FROM team_members WHERE team_id=? ORDER BY is_sub,id",
                (team_id,),
            )
            squads.append(
                {
                    "id": team_id,
                    "name": team["name"],
                    "tag": team["tag"],
                    "stats": stats,
                    "lineup": lineup,
                }
            )
        public_fixture = {
            key: fixture[key]
            for key in ("id", "match_no", "map", "scheduled_at", "tournament_name")
        }
        return {"match": public_fixture, "squads": squads}
