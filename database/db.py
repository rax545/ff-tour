import aiosqlite
from pathlib import Path

from config import DATABASE_PATH


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    max_teams INTEGER DEFAULT 12,
    entry_fee REAL DEFAULT 0,
    prize_pool REAL DEFAULT 0,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    tag TEXT NOT NULL,
    captain_id INTEGER NOT NULL,
    logo_url TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS registrations (
    tournament_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    status TEXT DEFAULT 'registered',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (tournament_id, team_id),

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON DELETE CASCADE,

    FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS team_members (
    team_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ign TEXT,
    uid TEXT,
    role TEXT DEFAULT 'Player',

    PRIMARY KEY (team_id, user_id),

    FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    match_no INTEGER NOT NULL,
    map TEXT,
    scheduled_at TEXT DEFAULT 'TBA',
    room_id TEXT DEFAULT '',
    room_password TEXT DEFAULT '',
    status TEXT DEFAULT 'scheduled',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tournament_id, match_no),

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    placement INTEGER NOT NULL,
    kills INTEGER DEFAULT 0,
    placement_points INTEGER DEFAULT 0,
    kill_points INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,
    submitted_by INTEGER,

    UNIQUE(match_id, team_id),

    FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON DELETE CASCADE,

    FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER,
    team_id INTEGER,
    user_id INTEGER,
    amount REAL,
    method TEXT,
    trx_id TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,
    target_id INTEGER,
    reason TEXT,
    evidence TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    opener_id INTEGER,
    type TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT,
    details TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


async def connect():
    """
    Create/connect to SQLite database.
    """

    database_path = Path(DATABASE_PATH)

    # Create database directory automatically
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    db = await aiosqlite.connect(
        DATABASE_PATH
    )

    db.row_factory = aiosqlite.Row

    # Enable foreign keys
    await db.execute(
        "PRAGMA foreign_keys = ON"
    )

    return db


async def init_db():
    """
    Initialize all database tables.
    """

    db = await connect()

    try:
        await db.executescript(
            SCHEMA
        )

        await db.commit()

    finally:
        await db.close()


async def audit(
    actor_id,
    action,
    details=""
):
    """
    Add an entry to audit logs.
    """

    db = await connect()

    try:
        await db.execute(
            """
            INSERT INTO audit_logs
            (
                actor_id,
                action,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                actor_id,
                action,
                details
            )
        )

        await db.commit()

    finally:
        await db.close()