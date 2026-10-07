"""Additive arena schema. Identity/award snapshots deliberately survive roster edits."""

ARENA_SCHEMA = """
CREATE TABLE IF NOT EXISTS brackets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    size INTEGER NOT NULL CHECK(size IN (2, 4, 8, 16, 32)),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'finished')),
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, tournament_id)
);
CREATE TABLE IF NOT EXISTS bracket_entries (
    bracket_id INTEGER NOT NULL REFERENCES brackets(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    name TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY(bracket_id, team_id),
    UNIQUE(bracket_id, seed)
);
CREATE TABLE IF NOT EXISTS bracket_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bracket_id INTEGER NOT NULL REFERENCES brackets(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL,
    position INTEGER NOT NULL,
    team_a INTEGER,
    team_b INTEGER,
    winner_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'ready', 'bye', 'finished')),
    score_a INTEGER,
    score_b INTEGER,
    match_id INTEGER UNIQUE REFERENCES matches(id) ON DELETE SET NULL,
    resolved_by INTEGER,
    resolved_at TEXT,
    UNIQUE(bracket_id, round_no, position)
);
CREATE TABLE IF NOT EXISTS hall_of_fame (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    tournament_name TEXT NOT NULL,
    format TEXT NOT NULL CHECK(format IN ('battle_royale', 'knockout')),
    podium_json TEXT NOT NULL,
    mvp_json TEXT NOT NULL DEFAULT '{}',
    inducted_by INTEGER NOT NULL,
    inducted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT '',
    UNIQUE(guild_id, tournament_id)
);
CREATE TABLE IF NOT EXISTS prediction_pools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    closes_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'locked', 'settled', 'cancelled')),
    winner_team_id INTEGER,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_by INTEGER,
    settled_at TEXT,
    UNIQUE(guild_id, match_id)
);
CREATE TABLE IF NOT EXISTS prediction_entries (
    pool_id INTEGER NOT NULL REFERENCES prediction_pools(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY(pool_id, team_id)
);
CREATE TABLE IF NOT EXISTS prediction_picks (
    pool_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    awarded_points INTEGER NOT NULL DEFAULT 0 CHECK(awarded_points IN (0, 10)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(pool_id, user_id),
    FOREIGN KEY(pool_id, team_id) REFERENCES prediction_entries(pool_id, team_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS radar_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('low', 'medium', 'high')),
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'cleared', 'confirmed')),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    reviewed_by INTEGER,
    review_note TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, tournament_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS squad_plans (
    guild_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    map_name TEXT NOT NULL,
    drop_zone TEXT NOT NULL,
    strategy TEXT NOT NULL,
    updated_by INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(guild_id, team_id)
);
CREATE TABLE IF NOT EXISTS squad_ready_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    opened_by INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, team_id, match_id)
);
CREATE TABLE IF NOT EXISTS squad_ready_responses (
    check_id INTEGER NOT NULL REFERENCES squad_ready_checks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    ready INTEGER NOT NULL CHECK(ready IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(check_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_team_members_uid ON team_members(uid);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_members_normalized_uid ON team_members(LOWER(TRIM(uid)), user_id, team_id);
CREATE INDEX IF NOT EXISTS idx_player_uid_match ON player_results(match_id, LOWER(TRIM(uid)));
CREATE INDEX IF NOT EXISTS idx_prediction_vote_totals ON prediction_picks(pool_id, team_id);
CREATE INDEX IF NOT EXISTS idx_player_results_match_team ON player_results(match_id, team_id);
CREATE INDEX IF NOT EXISTS idx_results_match_verified ON results(match_id, verified);
CREATE INDEX IF NOT EXISTS idx_radar_scope ON radar_findings(guild_id, tournament_id, active, status);
CREATE INDEX IF NOT EXISTS idx_predictions_scope ON prediction_pools(guild_id, status);
"""

STREAM_COLUMNS = {
    "stream_started_at": "TEXT",
    "stream_ended_at": "TEXT",
    "stream_revision": "INTEGER NOT NULL DEFAULT 0",
    "stream_channel_id": "INTEGER NOT NULL DEFAULT 0",
    "stream_message_id": "INTEGER NOT NULL DEFAULT 0",
}


async def migrate_arena(db):
    """Idempotent upgrade of existing databases, without deleting legacy data."""
    cur = await db.execute("PRAGMA table_info(matches)")
    columns = {row[1] for row in await cur.fetchall()}
    for name, definition in STREAM_COLUMNS.items():
        if name not in columns:
            await db.execute(f"ALTER TABLE matches ADD COLUMN {name} {definition}")
    await db.executescript(ARENA_SCHEMA)
