"""Seeded single-elimination brackets with transactional, irreversible advancement."""

import math

from services.arena_common import database, log, many, match, one, registered_teams, tournament

TERMINAL = {"bye", "finished"}


def seed_order(size):
    if size not in (2, 4, 8, 16, 32):
        raise ValueError("Bracket size must be a power of two between 2 and 32.")
    order = [1, 2]
    while len(order) < size:
        mirror = len(order) * 2 + 1
        order = [item for seed in order for item in (seed, mirror - seed)]
    return order


async def _propagate(db, bracket_id):
    """Feed resolved child winners upwards; an unresolved child is never a BYE."""
    nodes = await many(
        db,
        "SELECT * FROM bracket_nodes WHERE bracket_id=? ORDER BY round_no, position",
        (bracket_id,),
    )
    lookup = {(n["round_no"], n["position"]): n for n in nodes}
    for node in nodes:
        if node["status"] in TERMINAL or node["status"] == "ready":
            continue
        if node["round_no"] > 1:
            children = [
                lookup[(node["round_no"] - 1, node["position"] * 2 - 1)],
                lookup[(node["round_no"] - 1, node["position"] * 2)],
            ]
            if any(c["status"] not in TERMINAL for c in children):
                continue
            node["team_a"], node["team_b"] = (c["winner_id"] for c in children)
        entrants = [team for team in (node["team_a"], node["team_b"]) if team is not None]
        node["status"] = "ready" if len(entrants) == 2 else "bye"
        node["winner_id"] = entrants[0] if len(entrants) == 1 else None
        await db.execute(
            """UPDATE bracket_nodes SET team_a=?, team_b=?, status=?, winner_id=? WHERE id=?""",
            (node["team_a"], node["team_b"], node["status"], node["winner_id"], node["id"]),
        )
    if nodes[-1]["status"] in TERMINAL:
        await db.execute("UPDATE brackets SET status='finished' WHERE id=?", (bracket_id,))


async def _snapshot(db, bracket_id):
    bracket = await one(
        db,
        """SELECT b.*, t.name AS tournament_name FROM brackets b
        JOIN tournaments t ON t.id=b.tournament_id WHERE b.id=?""",
        (bracket_id,),
    )
    bracket["entries"] = await many(
        db, "SELECT * FROM bracket_entries WHERE bracket_id=? ORDER BY seed", (bracket_id,)
    )
    bracket["nodes"] = await many(
        db,
        "SELECT * FROM bracket_nodes WHERE bracket_id=? ORDER BY round_no, position",
        (bracket_id,),
    )
    return bracket


async def create_bracket(guild_id, tournament_id, actor_id, seeds=None):
    async with database(write=True) as db:
        tour = await tournament(db, tournament_id)
        existing = await one(
            db,
            "SELECT id FROM brackets WHERE guild_id=? AND tournament_id=?",
            (guild_id, tournament_id),
        )
        if existing:
            raise ValueError(
                "A bracket already exists. Use /bracket tree; existing progress is never overwritten."
            )
        if tour["status"] == "finished":
            raise ValueError("This tournament is already finalized.")
        teams = await registered_teams(db, tournament_id)
        if not 2 <= len(teams) <= 32:
            raise ValueError("A knockout bracket needs 2–32 registered squads.")
        if seeds is not None:
            if len(seeds) != len(teams) or set(seeds) != {t["id"] for t in teams}:
                raise ValueError(
                    "Seeds must list every registered team ID exactly once, best seed first."
                )
            teams_by_id = {t["id"]: t for t in teams}
            teams = [teams_by_id[team_id] for team_id in seeds]
        size = 2 ** math.ceil(math.log2(len(teams)))
        cursor = await db.execute(
            "INSERT INTO brackets(guild_id,tournament_id,size,created_by) VALUES(?,?,?,?)",
            (guild_id, tournament_id, size, actor_id),
        )
        bracket_id = cursor.lastrowid
        for seed, team in enumerate(teams, 1):
            await db.execute(
                "INSERT INTO bracket_entries(bracket_id,team_id,seed,name,tag) VALUES(?,?,?,?,?)",
                (bracket_id, team["id"], seed, team["name"], team["tag"]),
            )
        order = seed_order(size)
        for round_no in range(1, int(math.log2(size)) + 1):
            for pos in range(1, size // (2**round_no) + 1):
                a = b = None
                if round_no == 1:
                    sa, sb = order[(pos - 1) * 2 : pos * 2]
                    a = teams[sa - 1]["id"] if sa <= len(teams) else None
                    b = teams[sb - 1]["id"] if sb <= len(teams) else None
                await db.execute(
                    """INSERT INTO bracket_nodes(bracket_id,round_no,position,team_a,team_b)
                    VALUES(?,?,?,?,?)""",
                    (bracket_id, round_no, pos, a, b),
                )
        # Freeze the lobby by closing registration, not by changing BR match fixtures.
        await db.execute("UPDATE tournaments SET status='closed' WHERE id=?", (tournament_id,))
        await _propagate(db, bracket_id)
        await log(db, actor_id, "bracket_create", f"{guild_id}:{tournament_id}:{bracket_id}")
        return await _snapshot(db, bracket_id)


async def bracket_tree(guild_id, tournament_id):
    async with database() as db:
        row = await one(
            db,
            "SELECT id FROM brackets WHERE guild_id=? AND tournament_id=?",
            (guild_id, tournament_id),
        )
        if not row:
            raise ValueError("No bracket exists for this tournament in this server.")
        return await _snapshot(db, row["id"])


async def _node(db, guild_id, node_id):
    node = await one(
        db,
        """SELECT n.*, b.guild_id, b.tournament_id FROM bracket_nodes n
        JOIN brackets b ON b.id=n.bracket_id WHERE n.id=? AND b.guild_id=?""",
        (node_id, guild_id),
    )
    if not node:
        raise ValueError("Bracket node not found in this server.")
    return node


async def resolve_node(guild_id, node_id, winner_id, score_a, score_b, actor_id):
    if not 0 <= score_a <= 99 or not 0 <= score_b <= 99 or score_a == score_b:
        raise ValueError("Scores must be different whole numbers between 0 and 99.")
    async with database(write=True) as db:
        node = await _node(db, guild_id, node_id)
        if node["status"] == "finished":
            if (node["winner_id"], node["score_a"], node["score_b"]) == (
                winner_id,
                score_a,
                score_b,
            ):
                return await _snapshot(db, node["bracket_id"])
            raise ValueError(
                "This result is already final; changing it would invalidate downstream opponents."
            )
        if node["status"] != "ready" or winner_id not in (node["team_a"], node["team_b"]):
            raise ValueError("Choose one of the two opponents in a READY bracket node.")
        if winner_id != (node["team_a"] if score_a > score_b else node["team_b"]):
            raise ValueError(
                "The winner must have the higher score (A/B order shown in /bracket tree)."
            )
        await db.execute(
            """UPDATE bracket_nodes SET winner_id=?,score_a=?,score_b=?,status='finished',
            resolved_by=?,resolved_at=CURRENT_TIMESTAMP WHERE id=?""",
            (winner_id, score_a, score_b, actor_id, node_id),
        )
        if node["match_id"]:
            await db.execute(
                """UPDATE matches SET status='finished',
                stream_ended_at=CASE WHEN stream_live=1 THEN CURRENT_TIMESTAMP ELSE stream_ended_at END,
                stream_live=0 WHERE id=?""",
                (node["match_id"],),
            )
            await db.execute(
                "UPDATE prediction_pools SET status='locked' WHERE match_id=? AND status='open'",
                (node["match_id"],),
            )
        await _propagate(db, node["bracket_id"])
        await log(
            db, actor_id, "bracket_resolve", f"{guild_id}:{node_id}:{winner_id}:{score_a}-{score_b}"
        )
        return await _snapshot(db, node["bracket_id"])


async def bind_match(guild_id, node_id, match_id, actor_id):
    async with database(write=True) as db:
        node = await _node(db, guild_id, node_id)
        fixture = await match(db, match_id)
        if node["match_id"] == match_id:
            return node
        if node["status"] != "ready" or node["match_id"]:
            raise ValueError("Only an unbound READY node can be attached to a fixture.")
        if fixture["tournament_id"] != node["tournament_id"]:
            raise ValueError("The fixture must belong to the same tournament.")
        if fixture["status"] != "scheduled" or fixture["stream_live"]:
            raise ValueError("Bind a fixture before it starts.")
        used = await one(
            db,
            """SELECT id FROM bracket_nodes WHERE match_id=?
            UNION ALL SELECT id FROM prediction_pools WHERE match_id=?
            UNION ALL SELECT id FROM results WHERE match_id=? LIMIT 1""",
            (match_id, match_id, match_id),
        )
        if used:
            raise ValueError(
                "This fixture already has a bracket, predictions or results; it cannot be rebound."
            )
        await db.execute("UPDATE bracket_nodes SET match_id=? WHERE id=?", (match_id, node_id))
        await log(db, actor_id, "bracket_bind", f"{guild_id}:{node_id}:{match_id}")
        node["match_id"] = match_id
        return node
