"""Single-elimination knockout bracket generation and tracking."""
import math

from database.db import connect


class BracketError(ValueError):
    pass


def _bracket_size(n: int) -> int:
    """Next power of two >= n (minimum 2)."""
    size = 2
    while size < max(2, n):
        size *= 2
    return size


def _seeding_order(size: int):
    """Standard tournament seeding: 1 vs last, 2 vs last-1, ...

    size=8 -> [1, 8, 4, 5, 2, 7, 3, 6]
    """
    if size <= 1:
        return [1]
    prev = _seeding_order(size // 2)
    out = []
    for s in prev:
        out.append(s)
        out.append(size + 1 - s)
    return out


async def get_tournament_teams(tournament_id: int):
    db = await connect()
    try:
        cur = await db.execute(
            """
            SELECT DISTINCT t.id, t.name, t.tag
            FROM teams t
            WHERE t.tournament_id=?
            UNION
            SELECT DISTINCT t.id, t.name, t.tag
            FROM teams t
            JOIN registrations r ON r.team_id = t.id
            WHERE r.tournament_id=?
            ORDER BY id
            """,
            (tournament_id, tournament_id),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def generate_bracket(tournament_id: int, force: bool = False):
    """Create the knockout bracket for a tournament (idempotent unless force)."""
    teams = await get_tournament_teams(tournament_id)
    if len(teams) < 2:
        raise BracketError("Need at least 2 registered squads to build a bracket.")

    db = await connect()
    try:
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM bracket_matches WHERE tournament_id=?",
            (tournament_id,),
        )
        if (await cur.fetchone())["c"] > 0 and not force:
            return await _read_bracket(db, tournament_id)

        await db.execute("DELETE FROM bracket_matches WHERE tournament_id=?", (tournament_id,))

        size = _bracket_size(len(teams))
        rounds = int(math.log2(size))

        # Seed teams into round 1 slots; byes get team_b_id=0 and auto-advance.
        order = _seeding_order(size)
        slots = [0] * size
        for idx, team in enumerate(teams):
            slots[order[idx] - 1] = team["id"]

        for r in range(1, rounds + 1):
            matches_in_round = size // (2 ** r)
            for slot in range(matches_in_round):
                if r == 1:
                    team_a = slots[slot * 2]
                    team_b = slots[slot * 2 + 1]
                else:
                    team_a = 0
                    team_b = 0
                status = "pending"
                winner = 0
                if r == 1 and team_a and not team_b:
                    status = "bye"
                    winner = team_a
                elif r == 1 and team_b and not team_a:
                    status = "bye"
                    winner = team_b
                await db.execute(
                    """
                    INSERT INTO bracket_matches
                        (tournament_id, round, slot, team_a_id, team_b_id, winner_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tournament_id, r, slot, team_a, team_b, winner, status),
                )

        # Propagate all round-1 byes into round 2.
        await _propagate_byes(db, tournament_id, size, rounds)
        await db.commit()
        return await _read_bracket(db, tournament_id)
    finally:
        await db.close()


async def _propagate_byes(db, tournament_id: int, size: int, rounds: int):
    for r in range(1, rounds):
        next_round = r + 1
        matches_in_round = size // (2 ** r)
        for slot in range(matches_in_round):
            cur = await db.execute(
                "SELECT * FROM bracket_matches WHERE tournament_id=? AND round=? AND slot=?",
                (tournament_id, r, slot),
            )
            m = await cur.fetchone()
            if not m or m["status"] != "bye":
                continue
            next_slot = slot // 2
            field = "team_a_id" if slot % 2 == 0 else "team_b_id"
            await db.execute(
                f"UPDATE bracket_matches SET {field}=? WHERE tournament_id=? AND round=? AND slot=?",
                (m["winner_id"], tournament_id, next_round, next_slot),
            )
            # If both feeders were byes, the next match is also a bye.
            cur = await db.execute(
                "SELECT * FROM bracket_matches WHERE tournament_id=? AND round=? AND slot=?",
                (tournament_id, next_round, next_slot),
            )
            nxt = await cur.fetchone()
            if nxt and nxt["team_a_id"] and nxt["team_b_id"]:
                # check whether the other feeder was also a bye winner
                other_slot = slot + (1 if slot % 2 == 0 else -1)
                cur = await db.execute(
                    "SELECT * FROM bracket_matches WHERE tournament_id=? AND round=? AND slot=?",
                    (tournament_id, r, other_slot),
                )
                other = await cur.fetchone()
                if other and other["status"] == "bye" and other["winner_id"]:
                    await db.execute(
                        "UPDATE bracket_matches SET status='bye', winner_id=? "
                        "WHERE tournament_id=? AND round=? AND slot=?",
                        (nxt["team_a_id"], tournament_id, next_round, next_slot),
                    )


async def _read_bracket(db, tournament_id: int):
    cur = await db.execute(
        """
        SELECT b.*,
            ta.name AS team_a_name, ta.tag AS team_a_tag,
            tb.name AS team_b_name, tb.tag AS team_b_tag,
            tw.name AS winner_name
        FROM bracket_matches b
        LEFT JOIN teams ta ON ta.id = b.team_a_id
        LEFT JOIN teams tb ON tb.id = b.team_b_id
        LEFT JOIN teams tw ON tw.id = b.winner_id
        WHERE b.tournament_id=?
        ORDER BY b.round ASC, b.slot ASC
        """,
        (tournament_id,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    rounds = {}
    for row in rows:
        rounds.setdefault(row["round"], []).append(row)
    return {
        "tournament_id": tournament_id,
        "rounds": [rounds[r] for r in sorted(rounds)],
        "total_rounds": len(rounds),
    }


async def get_bracket(tournament_id: int):
    db = await connect()
    try:
        return await _read_bracket(db, tournament_id)
    finally:
        await db.close()


async def record_bracket_result(tournament_id: int, round_no: int, slot: int, winner_id: int):
    """Record a match winner and propagate it to the next round."""
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "SELECT * FROM bracket_matches WHERE tournament_id=? AND round=? AND slot=?",
            (tournament_id, round_no, slot),
        )
        match = await cur.fetchone()
        if not match:
            await db.rollback()
            raise BracketError("Bracket match not found.")
        if winner_id not in (match["team_a_id"], match["team_b_id"]):
            await db.rollback()
            raise BracketError("Winner must be one of the two squads in this bracket match.")
        await db.execute(
            "UPDATE bracket_matches SET winner_id=?, status='completed' "
            "WHERE tournament_id=? AND round=? AND slot=?",
            (winner_id, tournament_id, round_no, slot),
        )
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM bracket_matches WHERE tournament_id=? AND round=?",
            (tournament_id, round_no),
        )
        total = (await cur.fetchone())["c"]
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM bracket_matches "
            "WHERE tournament_id=? AND round=? AND status='completed'",
            (tournament_id, round_no),
        )
        done = (await cur.fetchone())["c"]
        if done == total:
            # Advance every winner of this round into the next round.
            cur = await db.execute(
                "SELECT * FROM bracket_matches WHERE tournament_id=? AND round=? ORDER BY slot",
                (tournament_id, round_no),
            )
            winners = [r["winner_id"] for r in await cur.fetchall() if r["winner_id"]]
            for idx, winner in enumerate(winners):
                field = "team_a_id" if idx % 2 == 0 else "team_b_id"
                await db.execute(
                    f"UPDATE bracket_matches SET {field}=? "
                    "WHERE tournament_id=? AND round=? AND slot=?",
                    (winner, tournament_id, round_no + 1, idx // 2),
                )
        await db.commit()
        return dict(match) | {"winner_id": winner_id}
    finally:
        await db.close()
