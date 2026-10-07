"""Staff-attested individual results, the only source of passport/MVP kill stats."""

from services.arena_common import database, log, many, match, match_teams, one


async def record_player_result(guild_id, match_id, member_id, kills, damage, actor_id):
    if not 0 <= kills <= 100 or not 0 <= damage <= 100000:
        raise ValueError("Kills must be 0–100 and damage 0–100000.")
    async with database(write=True) as db:
        fixture = await match(db, match_id)
        member = await one(db, "SELECT * FROM team_members WHERE id=?", (member_id,))
        if not member or not member["uid"].strip():
            raise ValueError("A roster member with a nonempty Free Fire UID is required.")
        teams = await match_teams(db, fixture, guild_id)
        if member["team_id"] not in {t["id"] for t in teams}:
            raise ValueError("This player’s squad is not an entrant in this fixture.")
        existing = await many(
            db,
            """SELECT id, team_id FROM player_results WHERE match_id=?
            AND LOWER(TRIM(uid))=LOWER(TRIM(?))""",
            (match_id, member["uid"]),
        )
        if len(existing) > 1 or (existing and existing[0]["team_id"] != member["team_id"]):
            raise ValueError(
                "Conflicting legacy results exist for this UID/match. Staff must reconcile them first."
            )
        team_result = await one(
            db,
            "SELECT kills FROM results WHERE match_id=? AND team_id=? AND verified=1",
            (match_id, member["team_id"]),
        )
        other = await one(
            db,
            """SELECT COALESCE(SUM(kills),0) AS kills FROM player_results
            WHERE match_id=? AND team_id=? AND verified=1 AND id!=?""",
            (match_id, member["team_id"], existing[0]["id"] if existing else 0),
        )
        if team_result and other["kills"] + kills > team_result["kills"]:
            raise ValueError(
                "Verified individual kills cannot exceed the verified squad kill total."
            )
        if existing:
            result_id = existing[0]["id"]
            await db.execute(
                """UPDATE player_results SET member_id=?,ign=?,uid=?,kills=?,damage=?,verified=1
                WHERE id=?""",
                (member_id, member["ign"], member["uid"].strip(), kills, damage, result_id),
            )
        else:
            cursor = await db.execute(
                """INSERT INTO player_results
                (match_id,team_id,member_id,ign,uid,kills,damage,verified) VALUES(?,?,?,?,?,?,?,1)""",
                (
                    match_id,
                    member["team_id"],
                    member_id,
                    member["ign"],
                    member["uid"].strip(),
                    kills,
                    damage,
                ),
            )
            result_id = cursor.lastrowid
        await db.execute(
            "UPDATE prediction_pools SET status='locked' WHERE match_id=? AND status='open'",
            (match_id,),
        )
        await log(
            db,
            actor_id,
            "player_result_record",
            f"{guild_id}:{match_id}:{member_id}:{kills}:{damage}",
        )
        return result_id


async def verified_fraggers(db, tournament_id, limit=10):
    """Never synthesize individual kills from squad totals or multiply roster joins.

    Duplicate UID/match rows and UIDs linked to different accounts are excluded
    rather than selecting an arbitrary owner. Blank UIDs cannot identify a player.
    """
    rows = await many(
        db,
        """SELECT MIN(pr.ign) AS ign, LOWER(TRIM(pr.uid)) AS uid,
        SUM(pr.kills) AS kills, SUM(pr.damage) AS damage, COUNT(DISTINCT pr.match_id) AS matches
        FROM player_results pr JOIN matches m ON m.id=pr.match_id
        WHERE pr.verified=1 AND TRIM(pr.uid)!='' AND pr.kills>=0 AND pr.damage>=0 AND (?=0 OR m.tournament_id=?)
        AND EXISTS (SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE tm.team_id=pr.team_id
            AND LOWER(TRIM(tm.uid))=LOWER(TRIM(pr.uid)) AND (t.tournament_id=m.tournament_id OR EXISTS (
                SELECT 1 FROM registrations r WHERE r.team_id=t.id AND r.tournament_id=m.tournament_id
                AND r.status='registered')))
        AND NOT EXISTS (SELECT 1 FROM player_results dup WHERE dup.match_id=pr.match_id
            AND LOWER(TRIM(dup.uid))=LOWER(TRIM(pr.uid)) AND dup.id!=pr.id)
        AND (SELECT COUNT(DISTINCT tm.user_id) FROM team_members tm
            WHERE LOWER(TRIM(tm.uid))=LOWER(TRIM(pr.uid)) AND tm.user_id>0)<=1
        GROUP BY LOWER(TRIM(pr.uid)) ORDER BY kills DESC, damage DESC, uid ASC LIMIT ?""",
        (tournament_id, tournament_id, limit),
    )

    for row in rows:
        metadata = await one(
            db,
            """SELECT t.name AS team_name,t.tag AS team_tag,t.batch,t.section,
            COALESCE((SELECT tm.role FROM team_members tm WHERE tm.team_id=t.id
                AND LOWER(TRIM(tm.uid))=? ORDER BY tm.id LIMIT 1),'Player') AS role
            FROM player_results pr JOIN matches m ON m.id=pr.match_id JOIN teams t ON t.id=pr.team_id
            WHERE LOWER(TRIM(pr.uid))=? AND pr.verified=1 AND (?=0 OR m.tournament_id=?)
            ORDER BY pr.match_id DESC,pr.id DESC LIMIT 1""",
            (row["uid"], row["uid"], tournament_id, tournament_id),
        )
        row.update(
            metadata
            or {
                "team_name": "Recorded squad",
                "team_tag": "",
                "batch": "",
                "section": "",
                "role": "Player",
            }
        )
    return rows
