"""Root LU coin economy, bounty board and match predictions.

All balance mutations are atomic: the ``coins`` row is upserted and a
``coin_transactions`` audit row is written inside the same transaction.
"""
from datetime import datetime, timedelta, timezone

from database.db import connect

DAILY_REWARD = 100
DAILY_COOLDOWN = timedelta(hours=24)
MIN_TIP = 1
MIN_BOUNTY = 50
MIN_PREDICTION = 10
PREDICTION_PAYOUT_MULTIPLIER = 2  # winners receive stake * multiplier


class EconomyError(ValueError):
    """Raised for any rejected economy operation."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def get_balance(user_id: int) -> int:
    db = await connect()
    try:
        cur = await db.execute("SELECT balance FROM coins WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return int(row["balance"]) if row else 0
    finally:
        await db.close()


async def _adjust(db, user_id: int, amount: int, kind: str, counterparty_id: int = 0, note: str = ""):
    """Apply a balance delta and record the transaction. Caller commits."""
    await db.execute(
        """
        INSERT INTO coins (user_id, balance, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            balance = balance + excluded.balance,
            updated_at = excluded.updated_at
        """,
        (user_id, amount, _utcnow()),
    )
    await db.execute(
        """
        INSERT INTO coin_transactions (user_id, amount, kind, counterparty_id, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, amount, kind, counterparty_id, note),
    )


async def add_coins(user_id: int, amount: int, kind: str, counterparty_id: int = 0, note: str = ""):
    if amount == 0:
        return
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        await _adjust(db, user_id, amount, kind, counterparty_id, note)
        await db.commit()
    finally:
        await db.close()


async def transfer_coins(sender_id: int, receiver_id: int, amount: int, kind: str, note: str = ""):
    """Atomically move coins between two users."""
    if amount <= 0:
        raise EconomyError("Amount must be positive.")
    if sender_id == receiver_id:
        raise EconomyError("You cannot send coins to yourself.")
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT balance FROM coins WHERE user_id=?", (sender_id,))
        row = await cur.fetchone()
        balance = int(row["balance"]) if row else 0
        if balance < amount:
            await db.rollback()
            raise EconomyError(f"Insufficient balance. You have **{balance}** coins, need **{amount}**.")
        await _adjust(db, sender_id, -amount, kind, receiver_id, note)
        await _adjust(db, receiver_id, amount, kind, sender_id, note)
        await db.commit()
    finally:
        await db.close()


async def claim_daily(user_id: int):
    """Claim the daily coin reward. Returns (reward, next_available_utc)."""
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cur = await db.execute(
            "SELECT claimed_at FROM daily_claims WHERE user_id=? AND claim_date=?",
            (user_id, today),
        )
        if await cur.fetchone():
            await db.rollback()
            raise EconomyError("Daily reward already claimed today. Come back tomorrow!")
        await db.execute(
            "INSERT INTO daily_claims (user_id, claim_date) VALUES (?, ?)",
            (user_id, today),
        )
        await _adjust(db, user_id, DAILY_REWARD, "daily", 0, "Daily login reward")
        await db.commit()
        return DAILY_REWARD, datetime.now(timezone.utc) + DAILY_COOLDOWN
    finally:
        await db.close()


async def tip(sender_id: int, receiver_id: int, amount: int):
    if amount < MIN_TIP:
        raise EconomyError(f"Minimum tip is **{MIN_TIP}** coin.")
    await transfer_coins(sender_id, receiver_id, amount, "tip", "Coin tip")


async def coin_leaderboard(limit: int = 10):
    db = await connect()
    try:
        cur = await db.execute(
            """
            SELECT c.user_id, c.balance,
                   COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS earned
            FROM coins c
            LEFT JOIN coin_transactions t ON t.user_id = c.user_id
            GROUP BY c.user_id
            ORDER BY c.balance DESC, earned DESC
            LIMIT ?
            """,
            (max(1, min(limit, 25)),),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


# ============================================================
# BOUNTIES
# ============================================================

async def place_bounty(placer_id: int, target_id: int, amount: int, reason: str = ""):
    """Lock coins on a target's head. Returns the new bounty id."""
    if target_id == placer_id:
        raise EconomyError("You cannot place a bounty on yourself.")
    if amount < MIN_BOUNTY:
        raise EconomyError(f"Minimum bounty is **{MIN_BOUNTY}** coins.")
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT balance FROM coins WHERE user_id=?", (placer_id,))
        row = await cur.fetchone()
        balance = int(row["balance"]) if row else 0
        if balance < amount:
            await db.rollback()
            raise EconomyError(f"Insufficient balance. You have **{balance}** coins, need **{amount}**.")
        await _adjust(db, placer_id, -amount, "bounty_locked", target_id, reason or "Bounty placed")
        cur = await db.execute(
            """
            INSERT INTO bounties (placer_id, target_id, amount, reason, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (placer_id, target_id, amount, reason.strip()[:200]),
        )
        bounty_id = cur.lastrowid
        await db.commit()
        return bounty_id
    finally:
        await db.close()


async def bounty_board(status: str = "active", limit: int = 20):
    db = await connect()
    try:
        cur = await db.execute(
            """
            SELECT * FROM bounties
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (status, max(1, min(limit, 50))),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def claim_bounty(bounty_id: int, claimer_id: int, match_id: int):
    """Claim a bounty when the target's squad was eliminated (placement > 1)
    in a verified match. Pays the locked amount to the claimer."""
    if claimer_id == 0:
        raise EconomyError("Claimer is required.")
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT * FROM bounties WHERE id=?", (bounty_id,))
        bounty = await cur.fetchone()
        if not bounty:
            await db.rollback()
            raise EconomyError("Bounty not found.")
        if bounty["status"] != "active":
            await db.rollback()
            raise EconomyError(f"This bounty is already **{bounty['status']}**.")
        if bounty["target_id"] == claimer_id:
            await db.rollback()
            raise EconomyError("You cannot claim a bounty placed on yourself.")

        # The target must have a verified result in this match and must NOT have won.
        cur = await db.execute(
            """
            SELECT r.placement, r.verified, t.id AS team_id
            FROM results r
            JOIN teams t ON t.id = r.team_id
            JOIN team_members tm ON tm.team_id = t.id AND tm.user_id = ?
            WHERE r.match_id = ?
            ORDER BY r.id DESC
            LIMIT 1
            """,
            (bounty["target_id"], match_id),
        )
        result = await cur.fetchone()
        if not result or not result["verified"]:
            await db.rollback()
            raise EconomyError("No verified result found for the target in this match.")
        if result["placement"] <= 1:
            await db.rollback()
            raise EconomyError("The target won that match — the bounty survives. Try again!")

        await _adjust(
            db, claimer_id, bounty["amount"], "bounty_claimed", bounty["placer_id"],
            f"Bounty #{bounty_id} claimed",
        )
        await db.execute(
            """
            UPDATE bounties
            SET status='claimed', claimed_by=?, resolved_at=?
            WHERE id=?
            """,
            (claimer_id, _utcnow(), bounty_id),
        )
        await db.commit()
        return dict(bounty) | {"payout": bounty["amount"], "claimer_id": claimer_id}
    finally:
        await db.close()


async def cancel_bounty(bounty_id: int, actor_id: int, staff: bool = False):
    """Cancel an active bounty; the placer (or staff) is refunded."""
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT * FROM bounties WHERE id=?", (bounty_id,))
        bounty = await cur.fetchone()
        if not bounty:
            await db.rollback()
            raise EconomyError("Bounty not found.")
        if bounty["status"] != "active":
            await db.rollback()
            raise EconomyError(f"This bounty is already **{bounty['status']}**.")
        if bounty["placer_id"] != actor_id and not staff:
            await db.rollback()
            raise EconomyError("Only the placer or staff can cancel this bounty.")
        await _adjust(db, bounty["placer_id"], bounty["amount"], "bounty_refund", 0, f"Bounty #{bounty_id} cancelled")
        await db.execute(
            "UPDATE bounties SET status='cancelled', resolved_at=? WHERE id=?",
            (_utcnow(), bounty_id),
        )
        await db.commit()
        return dict(bounty)
    finally:
        await db.close()


# ============================================================
# MATCH PREDICTIONS
# ============================================================

async def place_prediction(match_id: int, user_id: int, team_id: int, amount: int):
    """Stake coins on a team for a match. One prediction per user per match."""
    if amount < MIN_PREDICTION:
        raise EconomyError(f"Minimum prediction stake is **{MIN_PREDICTION}** coins.")
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT status FROM matches WHERE id=?", (match_id,))
        match = await cur.fetchone()
        if not match:
            await db.rollback()
            raise EconomyError("Match not found.")
        if match["status"] == "completed":
            await db.rollback()
            raise EconomyError("This match is already completed — predictions are closed.")
        cur = await db.execute("SELECT id FROM teams WHERE id=?", (team_id,))
        if not await cur.fetchone():
            await db.rollback()
            raise EconomyError("Team not found.")
        cur = await db.execute(
            "SELECT balance FROM coins WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        balance = int(row["balance"]) if row else 0
        if balance < amount:
            await db.rollback()
            raise EconomyError(f"Insufficient balance. You have **{balance}** coins, need **{amount}**.")
        try:
            await db.execute(
                """
                INSERT INTO predictions (match_id, user_id, team_id, amount, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (match_id, user_id, team_id, amount),
            )
        except Exception:
            await db.rollback()
            raise EconomyError("You already have a prediction on this match.")
        await _adjust(db, user_id, -amount, "prediction_stake", 0, f"Prediction on match #{match_id}")
        await db.commit()
    finally:
        await db.close()


async def resolve_predictions(match_id: int, winning_team_id: int):
    """Resolve all pending predictions for a match.

    Winners receive stake * PREDICTION_PAYOUT_MULTIPLIER; losers forfeit the stake.
    Returns a summary dict.
    """
    db = await connect()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "SELECT * FROM predictions WHERE match_id=? AND status='pending'",
            (match_id,),
        )
        rows = await cur.fetchall()
        won_count = 0
        lost_count = 0
        payout_total = 0
        for row in rows:
            if row["team_id"] == winning_team_id:
                payout = row["amount"] * PREDICTION_PAYOUT_MULTIPLIER
                await _adjust(db, row["user_id"], payout, "prediction_win", 0,
                              f"Prediction won on match #{match_id}")
                await db.execute(
                    "UPDATE predictions SET status='won', resolved_at=? WHERE id=?",
                    (_utcnow(), row["id"]),
                )
                won_count += 1
                payout_total += payout
            else:
                await db.execute(
                    "UPDATE predictions SET status='lost', resolved_at=? WHERE id=?",
                    (_utcnow(), row["id"]),
                )
                lost_count += 1
        await db.commit()
        return {
            "match_id": match_id,
            "winning_team_id": winning_team_id,
            "won": won_count,
            "lost": lost_count,
            "payout_total": payout_total,
        }
    finally:
        await db.close()
