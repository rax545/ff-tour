"""
Match Reminder & Schedule Notification service.

Handles schedule-time parsing, reminder-offset parsing and all
database operations for the automated match reminder system.
"""

import re
from datetime import datetime, timedelta, timezone

from config import TZ_OFFSET_MINUTES

# Default reminder offsets (minutes before match start)
DEFAULT_OFFSETS = (60, 15, 5)

# Maximum number of reminder offsets allowed per match
MAX_OFFSETS = 6

_TIME_RE = re.compile(
    r"^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$",
    re.IGNORECASE
)

_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %I:%M %p",
    "%Y/%m/%d %H:%M",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %I:%M %p",
    "%d/%m/%Y %I:%M %p",
)


def local_tz() -> timezone:
    """Server-local timezone (configured via TIMEZONE_UTC_OFFSET, default +06:00 / Dhaka)."""
    return timezone(timedelta(minutes=TZ_OFFSET_MINUTES))


def parse_schedule_time(text: str, now: datetime | None = None) -> datetime:
    """
    Parse a human friendly schedule string into an aware UTC datetime.

    Supported formats (interpreted in the configured local timezone):
      - "2026-10-07 21:00"       (full date + 24h time)
      - "07/10/2026 9:00 PM"     (day-first date + 12h time)
      - "today 21:00"            / "today 9:00 pm"
      - "tomorrow 20:30"         / "tomorrow 8:30 pm"
      - "21:00" / "9:00 pm"      (today, or tomorrow if already past)

    Raises ValueError when the text cannot be parsed or is in the past.
    """
    if not text or not text.strip():
        raise ValueError("Schedule time cannot be empty.")

    raw = text.strip()
    tz = local_tz()
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_local = now_utc.astimezone(tz)

    lowered = raw.lower()
    day_shift = None
    time_part = lowered

    if lowered.startswith(("today", "আজ")):
        day_shift = 0
        time_part = re.sub(r"^(today|আজ)\s*", "", lowered).strip()
    elif lowered.startswith(("tomorrow", "আগামীকাল", "কাল")):
        day_shift = 1
        time_part = re.sub(r"^(tomorrow|আগামীকাল|কাল)\s*", "", lowered).strip()

    parsed_local = None

    # 1) Explicit date + time formats
    if day_shift is None:
        for fmt in _DATETIME_FORMATS:
            try:
                parsed_local = datetime.strptime(raw, fmt).replace(tzinfo=tz)
                break
            except ValueError:
                continue

    # 2) Time-only (with optional today/tomorrow prefix)
    if parsed_local is None:
        m = _TIME_RE.match(time_part)
        if not m:
            raise ValueError(
                f"Could not understand schedule time: `{text}`.\n"
                "Try formats like `2026-10-07 21:00`, `today 9:00 PM`, "
                "`tomorrow 20:30` or `21:00`."
            )

        hour = int(m.group(1))
        minute = int(m.group(2))
        meridiem = (m.group(3) or "").lower()

        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        if hour > 23 or minute > 59:
            raise ValueError(f"Invalid time value in `{text}`.")

        base_day = now_local + timedelta(days=day_shift or 0)
        parsed_local = base_day.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        # Bare time already past today -> roll to tomorrow
        if day_shift is None and parsed_local <= now_local:
            parsed_local += timedelta(days=1)

    parsed_utc = parsed_local.astimezone(timezone.utc)

    if parsed_utc <= now_utc:
        raise ValueError(
            f"Schedule time `{text}` is in the past. "
            "Match reminders can only be set for future times."
        )

    return parsed_utc


def parse_offsets(text: str | None) -> list:
    """
    Parse a comma separated offsets string (minutes before match)
    e.g. "60, 15, 5" -> [60, 15, 5] (descending, unique).
    Falls back to DEFAULT_OFFSETS when empty.
    """
    if not text or not text.strip():
        return list(DEFAULT_OFFSETS)

    offsets = set()
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.isdigit():
            raise ValueError(
                f"Invalid reminder offset: `{chunk}`. "
                "Offsets must be positive whole minutes, e.g. `60,15,5`."
            )
        val = int(chunk)
        if val < 1 or val > 10080:  # max 7 days
            raise ValueError(
                f"Offset `{val}` out of range (1 - 10080 minutes)."
            )
        offsets.add(val)

    if not offsets:
        return list(DEFAULT_OFFSETS)

    if len(offsets) > MAX_OFFSETS:
        raise ValueError(f"Too many reminder offsets (max {MAX_OFFSETS}).")

    return sorted(offsets, reverse=True)


def compute_remind_times(match_time_utc: datetime, offsets: list) -> list:
    """
    Build (offset_minutes, remind_at_utc) pairs, skipping times already past.
    """
    now = datetime.now(timezone.utc)
    out = []
    for off in offsets:
        remind_at = match_time_utc - timedelta(minutes=off)
        if remind_at > now:
            out.append((off, remind_at))
    return out


def iso(dt: datetime) -> str:
    """Normalize datetime to ISO string (UTC, second precision)."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


# ==========================================================
# Database operations
# ==========================================================

async def schedule_match_reminders(
    db,
    match_id: int,
    tournament_id: int,
    channel_id: int,
    created_by: int,
    match_time_utc: datetime,
    offsets: list
):
    """
    Replace any pending reminders for the match with a fresh set.
    Returns list of (offset, remind_at) actually scheduled.
    """
    await db.execute(
        "DELETE FROM reminders WHERE match_id=? AND status='pending'",
        (match_id,)
    )

    pairs = compute_remind_times(match_time_utc, offsets)

    for off, remind_at in pairs:
        await db.execute(
            """
            INSERT OR REPLACE INTO reminders
            (match_id, tournament_id, channel_id, match_time,
             remind_at, offset_minutes, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                match_id,
                tournament_id,
                channel_id,
                iso(match_time_utc),
                iso(remind_at),
                off,
                created_by,
            )
        )

    await db.commit()
    return pairs


async def due_reminders(db, now: datetime | None = None):
    """Fetch all pending reminders whose remind_at has arrived."""
    now_iso = iso(now or datetime.now(timezone.utc))
    cur = await db.execute(
        """
        SELECT r.id, r.match_id, r.tournament_id, r.channel_id,
               r.match_time, r.remind_at, r.offset_minutes,
               m.match_no, m.map, m.scheduled_at,
               t.name AS tournament_name
        FROM reminders r
        JOIN matches m ON m.id = r.match_id
        JOIN tournaments t ON t.id = r.tournament_id
        WHERE r.status = 'pending'
        AND r.remind_at <= ?
        ORDER BY r.remind_at ASC
        """,
        (now_iso,)
    )
    return await cur.fetchall()


async def pending_reminders(db, tournament_id: int | None = None):
    """List upcoming (pending) reminders, optionally filtered by tournament."""
    query = """
        SELECT r.id, r.match_id, r.tournament_id, r.channel_id,
               r.match_time, r.remind_at, r.offset_minutes,
               m.match_no, m.map,
               t.name AS tournament_name
        FROM reminders r
        JOIN matches m ON m.id = r.match_id
        JOIN tournaments t ON t.id = r.tournament_id
        WHERE r.status = 'pending'
    """
    params = []
    if tournament_id:
        query += " AND r.tournament_id = ?"
        params.append(tournament_id)
    query += " ORDER BY r.remind_at ASC LIMIT 25"

    cur = await db.execute(query, params)
    return await cur.fetchall()


async def mark_reminder(db, reminder_id: int, status: str):
    """Update a reminder's status ('sent' / 'cancelled' / 'failed')."""
    await db.execute(
        "UPDATE reminders SET status=? WHERE id=?",
        (status, reminder_id)
    )
    await db.commit()


async def cancel_match_reminders(db, match_id: int) -> int:
    """Cancel every pending reminder for a match. Returns affected count."""
    cur = await db.execute(
        "UPDATE reminders SET status='cancelled' "
        "WHERE match_id=? AND status='pending'",
        (match_id,)
    )
    await db.commit()
    return cur.rowcount
