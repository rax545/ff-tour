# 🐺 Root LU — Free Fire Esports Tournament Bot (Leading University Edition)

A high-end, production-grade Free Fire esports tournament Discord management bot customized for Leading University's **Root LU** community. Features CSE batch & section rankings, official student ID verification, individual fragger tracking & MVP rankings, match fixtures with official 5-map rotation, dynamic tournament banners, automated match dispatch DMs, custom room credential delivery, interactive registration panels, and real-time verified leaderboards.

## 🆕 Complete Arena expansion

Eight integrated Discord features are available now: **live stream lifecycle,
Hall of Fame, bracket tree, private player passport, squad clash posters,
free prediction arena, staff-only anti-smurf review radar, and squad war rooms**
with tactical notes and persistent ready-check buttons.

| Feature | Main commands |
| --- | --- |
| Live streams & replay | `/match stream`, `/match streamstop`, `/live list` |
| Champions gallery | `/halloffame induct`, `/halloffame show` |
| Knockout bracket | `/bracket create`, `/bracket tree`, `/bracket bind`, `/bracket resolve` |
| Player passport & stats | `/passport`, `/result player`, `/result mvp` |
| Versus poster | `/clash poster` |
| Free prediction arena | `/prediction open`, `/prediction arena`, `/prediction settle` |
| Private anti-smurf review | `/radar scan`, `/radar list`, `/radar review` |
| Squad war room | `/squad warroom`, `/squad plan`, `/squad briefing`, `/squad readycheck` |

**[Complete command guide, বাংলা quickstart, deployment and smoke tests →](docs/arena.md)**

Prediction points have no monetary value. Radar findings are human-review leads,
not proof of smurfing, and never cause automatic bans. Passport identity is
roster-linked, not official Garena verification. Run one bot/database per server,
set `GUILD_ID`, and back up SQLite before upgrading. Existing data is migrated
additively; generated images and runtime databases are not part of this change.

## ✨ Features & Capabilities

### 🎓 Leading University & CSE Features
- 🏆 **`/section leaderboard [tournament_id]` — CSE Batch & Section Points Table:** Real-time point tables and rankings aggregated across CSE batches (e.g. Batch 60, 59, 58) and sections (A, B, C, D) with total points, kills, squad counts, and top squad highlights.
- 🎓 **`/student verify` & `/student profile` — Student ID Verification:** Official Leading University Student ID verification system with department, batch, and section validation, uniqueness constraints, and verified role assignment.
- 🔥 **`/result topfraggers [tournament_id] [limit]` — Tournament Top Fraggers & MVP:** Comprehensive individual kill rankings showcasing the most lethal fraggers across verified matches, highlighting the tournament MVP / Terminator.
- 🗓️ **`/tournament fixtures <tournament_id>` — Match Fixtures & 5-Map Rotation:** Complete match schedule and official 5-map Battle Royale rotation order:
  1. 🏝️ **Bermuda** (Classic Battle Royale)
  2. 🌋 **Purgatory** (High-Ground Elevation & Sniping)
  3. 🏜️ **Kalahari** (Desert Tactical Combat)
  4. ❄️ **Alpine** (Snow Terrain & Multi-Elevation)
  5. ⚡ **NexTerra** (Futuristic Battlefield & Anti-Gravity Zones)
- 👥 **`/team create` with Batch & Section Support:** Register squads with `batch` and `section` metadata (with automatic autofill from verified student profiles).

### ⏰ Match Reminders & Schedule Notifications
- ⏰ **`/reminder set <match_id> <when> [offsets] [channel]` — Automated Match Reminders:** Staff lock in a match time (`2026-10-07 21:00`, `today 9:00 PM`, `tomorrow 20:30`, or just `21:00`) and the bot automatically fires countdown reminders at configurable offsets (default **60, 15 & 5 minutes** before the match) — both as channel announcements and personal DMs to every registered squad captain & member.
- 📋 **`/reminder list [tournament_id]` — Upcoming Reminder Schedule:** View all pending reminders with live Discord relative timestamps (`in 42 minutes`).
- 🚫 **`/reminder cancel <match_id>` — Cancel Reminders:** Instantly cancel every pending reminder for a match when schedules change.
- 🌏 **Timezone Aware:** Times are interpreted in your configured local timezone (`TIMEZONE_UTC_OFFSET`, default `+06:00` Asia/Dhaka) and rendered with Discord `<t:...>` timestamps so every member sees their own local time.
- 🔁 **Reliable Background Dispatcher:** A 30-second background loop delivers due reminders, survives bot restarts (reminders persist in SQLite), auto-skips past offsets, and cascades clean-up when matches are deleted.

### 🎨 God-Tier Broadcast Graphics & Esports Economy
- 🖼️ **17 Pillow-generated cyberpunk/esports cards** in `utils/banner.py` (tournament/match banners, VIP room pass, 12-team points table, Booyah, MVP, live stream, gamer passport, certificate, 12-slot dropmap, VERSUS clash poster, Hall of Fame, knockout bracket, kill feed, broadcast lower-third, FUT Ultimate player card, WANTED bounty poster) — all branded **Root LU • Leading University CSE • Developed by Joy**.
- 💰 **Coin economy:** `/coin balance|daily|tip|leaderboard` with an atomic audited ledger.
- 🚨 **Bounty board:** `/bounty place|board|claim|cancel` — lock coins on a target, post a WANTED poster, claim the reward when they are eliminated.
- 🎯 **Match predictions:** `/match predict` stakes coins; `/match end` crowns the winner with a Booyah card and pays out 2x.
- 🧩 **Knockout brackets:** `/tournament bracket` — seeded single-elimination tree with byes.
- 🏛️ **Hall of Fame:** `/tournament halloffame` — auto-inducts champions on tournament close.
- 🛡️ **Security center:** `/security scan|history` — integrity scans persisted to SQLite.
- 👤 **Player identity:** `/player passport|card` — cyberpunk passport + FUT Ultimate card (OVR & 6 attributes).
- 🎓 **Student directory:** `/student list` + `/student info`; **`/section stats`** aggregates.
- 🛰️ **Hosting:** built-in aiohttp keep-alive server on `$PORT` (default 10000) for Render free-tier 24/7 uptime.

### 🐺 Tournament & Esports Core Features
- 🐺 **Dynamic Tournament Banners:** High-resolution banners auto-generated via Pillow (PIL) featuring server branding (**Root LU**), tournament title, prize pool, squad slots, entry fee, and wolf crests.
- 👥 **Full 4+1 Squad Lineups & Roles:** Register complete 4-player active rosters + 1 optional 5th player (Extra Substitute) with official Free Fire roles (IGL, Rusher, Sniper, Assaulter, Support, Substitute).
- ⚡ **OG Squad Match Dispatches:** `/match create` automatically delivers personalized OG battle notice DMs to all registered squad captains and members with team names, 4+1 roster breakdown, map, and schedule.
- 🔑 **OG Room Credentials Release:** `/match room` sends copyable Room ID & Password directly to captains' DMs with access passes.
- 🔴 **Live Stream Broadcast Notifications:** `/match stream <match_id> <stream_url> <platform>` instantly generates a red-accented HD (1280x720) "LIVE NOW" card, posts it with a **Watch Live** link button in the configured notification channel, and DMs every registered squad captain **and member** with the card, embed, and clickable link. `/tournament fixtures` also surfaces the live status and stream link.
- 📢 **Configurable Notification Channel:** Staff can run `/admin notifychannel <channel>` to persist the broadcast destination in SQLite. If none is configured (or the saved channel is unavailable), broadcasts fall back to the channel where `/match stream` was run.
- 📊 **Scoring & Verification:** Captains submit match placements and kills (`/result submit`), staff verifies scores (`/result verify`), and standings update live.
- 🛡️ **Admin Command Center:** `/admin dashboard`, payment approval/rejection workflows, and audit logging.
- 🎫 **Support Tickets:** `/ticket` creates private text channels for tournament inquiries and dispute resolution.

## 🚀 Installation & Setup
Python 3.11+ is required.

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then configure environment variables locally (never commit your token):
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
ADMIN_ROLE_ID=your_admin_role_id_here
MANAGER_ROLE_ID=your_manager_role_id_here
SERVER_NAME=Root LU
BRAND=Root LU
DATABASE_PATH=data/esports.sqlite3
# Optional: local timezone for /reminder set times (default +06:00 Asia/Dhaka)
TIMEZONE_UTC_OFFSET=+06:00
```

Start the bot:
```bash
python bot.py
```

## 📋 Slash Commands Overview

### 🏆 Tournament Commands (`/tournament`)
- `/tournament create <name> <max_teams> [entry_fee] [prize_pool] [description]` — Create and publish a tournament panel with a premium banner.
- `/tournament close <tournament_id>` — Close registration and auto-induct the verified champion into the Hall of Fame.
- `/tournament leaderboard <tournament_id>` — Verified standings embed + 12-team points table graphic.
- `/tournament slotlist <tournament_id>` — 12-slot lobby dropmap & grid graphic.
- `/tournament bracket <tournament_id> [regenerate]` — Single-elimination knockout bracket tree graphic.
- `/tournament halloffame [tournament_id]` — All-Time Hall of Fame & trophy cabinet graphic.
- `/tournament list` / `/tournament fixtures` / `/tournament slots` / `/tournament rules` — Hub, schedule, slot list & rulebook.

### 🛡️ Team Commands (`/team`) — 4+1 Squad Lineup System
- `/team register <tournament_id> <name> <tag> <captain_ign> <captain_uid> [batch] [section] ...` — Register a full **4 active starters + 1 substitute (5th player)** squad. Collects Free Fire UID, IGN and Combat Role (**Rusher, Sniper, IGL, Assaulter, Support, Substitute**) for every player, plus CSE Batch & Section (autofilled from verified student profiles). (`/team create` remains as an alias.)
- `/team info <team_id>` — Show a squad's full 4+1 lineup, UIDs, roles and batch/section. (`/team roster` remains as an alias.)
- `/team myteam` — Show every squad you captain or play for.
- `/team addplayer <team_id> <ign> <uid> [role] [member] [is_substitute]` — Add a starter or the 5th substitute (max 4 starters + 1 sub enforced).

### 🎮 Match Commands (`/match`) — Full Lifecycle
- `/match create <tournament_id> <match_no> <map_name> [scheduled_at]` — Create match, dispatch OG battle DMs with match banner + VIP room pass cards.
- `/match credentials <match_id> <room_id> <password>` — Release room credentials and DM captains a personalized VIP room pass. (`/match room` remains as an alias.)
- `/match start <match_id>` — Staff: mark a match LIVE and broadcast a lower-third news ticker graphic.
- `/match end <match_id> <winner_team_id>` — Staff: complete a match, post the Booyah winner card and resolve coin predictions.
- `/match dropmap <match_id>` — Post the 12-slot lobby dropmap & grid for the match's tournament.
- `/match warrooms <match_id>` — Staff: create/synchronize private war rooms for every squad.
- `/match cleanup_warrooms <match_id>` — Staff: delete all war rooms for the tournament's squads.
- `/match clash <match_id> <team_a_id> <team_b_id>` — Head-to-head VERSUS squad clash poster.
- `/match predict <match_id> <team_id> <amount>` — Stake coins on a squad (2x payout on win).
- `/match killfeed <match_id>` — Live combat kill feed graphic from verified match results.
- `/match countdown <match_id>` — Countdown to match start with Discord relative timestamps.
- `/match stream` / `/match streamstatus` / `/match streamstop` — Live stream broadcast lifecycle with HD LIVE card.

### 🛡️ Player Commands (`/player`)
- `/player passport [member]` — Cyberpunk gamer passport ID card (IGN, UID, role, batch/section, verified stats).
- `/player card [member]` — FUT-style Ultimate Player trading card with OVR & 6 attributes (PAC, SHO, PAS, DRI, DEF, PHY).

### 🚨 Bounty Commands (`/bounty`) — WANTED: DEAD OR ELIMINATED
- `/bounty place <target> <amount> [reason]` — Lock coins on a target's head and post a cyberpunk WANTED poster.
- `/bounty board` — Bounty rules & active targets.
- `/bounty claim <bounty_id> <match_id>` — Claim the reward when the target's squad is eliminated in a verified match.
- `/bounty cancel <bounty_id>` — Cancel a bounty you placed (full refund; staff can cancel any).

### 💰 Coin Commands (`/coin`) — Root LU Economy
- `/coin balance [member]` — Check a coin balance.
- `/coin daily` — Claim the daily reward (24h cooldown).
- `/coin tip <member> <amount>` — Tip another member.
- `/coin leaderboard` — Top coin holders.

### 🎓 Certificate Commands (`/certificate`)
- `/certificate generate <tournament_id> <team_id> [award]` — Generate your own Certificate of Esports Excellence card.
- `/certificate issue` / `/certificate verify` / `/certificate revoke` — Staff registry management.

### 🎓 Student Commands (`/student`)
- `/student verify <student_id> <name> <batch> <section> [department]` — Verify official Leading University Student ID.
- `/student info [member]` — View a verified student profile. (`/student profile` remains as an alias.)
- `/student list [batch] [limit]` — Verified student directory.

### 🏛️ Section Commands (`/section`)
- `/section leaderboard [tournament_id]` — CSE Batch & Section points table and rankings.
- `/section stats [tournament_id]` — Aggregate squads, players, kills & points per section.

### 🛡️ Security Commands (`/security`)
- `/security scan [scope]` — Staff: full integrity scan (incomplete rosters, duplicate UIDs, unverified captains, negative balances, open reports, stale rooms).
- `/security history` — Recent scan reports.

### 📊 Result Commands (`/result`)
- `/result submit` / `/result verify` / `/result leaderboard` / `/result topfraggers` / `/result table` / `/result booyah` / `/result mvp` — Scoring, verification, fragger MVP, and the points-table / Booyah / MVP graphics.

## 🎨 God-Tier Broadcast & Esports Pillow Graphics (`utils/banner.py`)

All graphics use a high-contrast cyberpunk/esports aesthetic and carry the **Root LU • Leading University CSE • Developed by Joy** footer on every card:

| # | Generator | Card |
|---|-----------|------|
| 1 | `generate_tournament_banner` | Tournament Banner (1200×520) |
| 2 | `generate_match_banner` | Match Announcement Banner (1200×460) |
| 3 | `generate_room_pass_card` | Personalized VIP Room Pass (1100×500) |
| 4 | `generate_points_table_graphic` | 12-Team Points Table Leaderboard (1200×880) |
| 5 | `generate_booyah_card` | Booyah Winner Celebration Card (1200×630) |
| 6 | `generate_mvp_card` | MVP Player of the Match Card (1200×630) |
| 7 | `generate_live_stream_card` | YouTube/Twitch Live Stream Card (1280×720) |
| 8 | `generate_player_passport_card` | Cyberpunk Gamer Passport ID Card (960×600) |
| 9 | `generate_certificate_card` | Certificate of Esports Excellence (1600×1000) |
| 10 | `generate_slotlist_card` | 12-Slot Lobby Dropmap & Grid (1280×840) |
| 11 | `generate_matchup_clash_card` | Head-to-Head VERSUS Squad Clash Poster (1200×700) |
| 12 | `generate_hall_of_fame_card` | All-Time Hall of Fame & Trophy Cabinet (1280×800) |
| 13 | `generate_tournament_bracket_card` | Knockout Tournament Bracket Tree (dynamic) |
| 14 | `generate_killfeed_card` | Live Combat Kill Feed Graphic (1280×640) |
| 15 | `generate_broadcast_lowerthird_card` | Broadcast Lower-Third News Ticker (1920×220) |
| 16 | `generate_ultimate_player_card` | FUT-Style Ultimate Player Trading Card with OVR & 6 attributes (600×900) |
| 17 | `generate_bounty_poster` | Cyberpunk "WANTED: DEAD OR ELIMINATED" Bounty Poster (900×1200) |

### 🖼️ Sample renders (`docs/demo/`)

Every generator above — plus the wolf crest icon — is committed as a rendered sample
PNG under `docs/demo/` so server staff and reviewers can preview the full card set
without starting the bot or Discord. The samples use **fake tournament data only**; no
real player, student or Garena identity appears in them. Regenerate them anytime with:

```bash
python scripts/render_demo_cards.py
```

| File | Preview |
|---|---|
| `docs/demo/01-tournament-banner.png` | Tournament banner: prize pool, slots, entry fee, status |
| `docs/demo/02-match-banner.png` | Match announcement with map & schedule |
| `docs/demo/03-room-pass.png` | Personalized VIP room pass for a squad |
| `docs/demo/04-points-table.png` | Full 12-team verified points table |
| `docs/demo/05-booyah.png` | Booyah winner celebration card |
| `docs/demo/06-mvp.png` | MVP of the match card |
| `docs/demo/07-live-stream.png` | 720p live broadcast card |
| `docs/demo/08-player-passport.png` | Cyberpunk gamer passport ID card |
| `docs/demo/09-certificate.png` | Certificate of Esports Excellence |
| `docs/demo/10-slotlist.png` | 12-slot lobby dropmap & grid |
| `docs/demo/11-matchup-clash.png` | Head-to-head VERSUS clash poster |
| `docs/demo/12-hall-of-fame.png` | All-time trophy cabinet |
| `docs/demo/13-bracket.png` | Knockout bracket tree |
| `docs/demo/14-killfeed.png` | Live combat kill feed ticker |
| `docs/demo/15-lowerthird.png` | Broadcast lower-third news ticker |
| `docs/demo/16-ultimate-player.png` | FUT-style ultimate player card (OVR + 6 attributes) |
| `docs/demo/17-bounty-poster.png` | "WANTED: DEAD OR ELIMINATED" bounty poster |
| `docs/demo/18-wolf-icon.png` | Wolf crest icon |

## 💰 Coin Economy, Bounties & Predictions

- **Atomic ledger:** every balance change writes a `coins` upsert + `coin_transactions` audit row in one transaction.
- **Daily rewards** (`/coin daily`) with a 24-hour cooldown tracked in `daily_claims`.
- **Tips** (`/coin tip`) move coins between members with balance validation.
- **Bounties** (`/bounty place`) lock coins on a target; hunters claim the full reward when the target's squad is eliminated (placement > #1) in a verified match. Winners void the hunt; placers/staff can cancel for a refund.
- **Match predictions** (`/match predict`) stake coins per user per match; `/match end` resolves them at 2x payout for winners.
- **Hall of Fame:** closing a tournament with verified results auto-inducts the champion (`/tournament halloffame` shows the trophy cabinet).
- **Knockout brackets:** `/tournament bracket` seeds squads into a single-elimination tree (standard 1-vs-last seeding with byes).
- **Security scans:** `/security scan` checks roster completeness, duplicate FF UIDs, duplicate squad names, unverified captains, negative balances, open reports and stale rooms — and persists every report.

## 🆕 Player Arena: passports, certificates, slot grid & squad rooms

These features ship as part of the existing Discord bot (no separate website or
stream-hosting service). Existing SQLite databases are upgraded automatically on
startup; back up `DATABASE_PATH` before upgrading. No extra dependencies are needed.

### Live stream lifecycle
- `/match stream <match_id> <stream_url> [platform]` — staff broadcasts an HD live
  card and Watch Live button using the existing announcement/DM workflow. Links
  now receive structural validation; this does not check whether a stream is
  actually online. Platform labels are limited to 40 characters. Identical live
  requests avoid duplicate announcements/DMs; `rebroadcast:true` explicitly resends.
  Announcements are posted before bounded, deduplicated DM fan-out.
- `/match streamstatus <match_id>` — display LIVE/OFFLINE and a live/replay button.
- `/match streamstop <match_id>` — staff marks a stream offline, retaining its URL
  for replay and refreshes the saved announcement best-effort. This does not finish
  the match or stop a stream on YouTube/Twitch. `/live list` shows current broadcasts.

### Private player passport
- `/passport` — generates a 1200×720 PNG visible only to the requesting player,
  with linked IGN/Free Fire UID, roles, recent squad affiliations and batch/section.
- Link a player's Discord account with `/team addplayer ... member:@player`.
- Only **verified individual `player_results`** matching the linked UID, squad and
  fixture contribute kills/damage. Conflicting owners and duplicate UID/match rows
  are excluded. Staff can record them with `/result player` (member IDs are shown
  by `/team roster`). Squad result kills are never attributed to individuals.
  Without individual result data the passport correctly shows zero recorded stats.
- Student IDs and room credentials are not included. The graphic shows up to five
  most recent roster entries; it is a roster summary, not identity authentication.

### Digital certificate registry
- `/certificate issue <tournament_id> <team_id> <recipient> <award>` — staff issues
  a 1600×1000 achievement certificate for a registered captain/linked member.
  Awards are staff attestations (e.g. `Champion`, `Participation`); standings do
  not automatically determine eligibility.
- The PNG and randomly generated registry code are returned privately to the
  issuer for delivery to the recipient. Repeating an identical issuance returns
  the same code, including under concurrent requests.
- `/certificate verify <code>` — privately verify the recipient, award, tournament
  and VALID/REVOKED status in the current server's SQLite registry.
- `/certificate revoke <code>` — staff permanently revokes an award. Revoked
  identical awards cannot be reissued; issue a distinct corrected award if needed.
- A PNG is not a cryptographic signature: the registry is authoritative. Issuance
  and revocation are audit-logged. Deleting a tournament/team cascades its registry
  records; retain these rows and database backups for long-term verification.

### Graphical slot grid
- `/tournament slots <tournament_id> [page] graphical:true` — renders a 1440×1000
  lobby grid, **24 slots/page**, showing occupied and open slots.
- `graphical:false` (default) preserves the existing **40 slots/page** text list.
- Positions are derived from ascending squad IDs, matching the text list. This is
  a visualization, not a persistent/custom slot assignment; removing teams shifts
  subsequent positions. Overflow registrations are not shown beyond max slots.

### Squad war room
- `/squad warroom <team_id>` — captain/staff creates private text **and** voice
  channels. Re-running reuses saved channels and synchronizes access to the
  current captain, linked roster members and configured staff roles. Removed
  players lose explicit access when this command is run again.
- `/squad close <team_id>` — captain/staff deletes both channels and saved IDs.
- Channels deny `@everyone` viewing/voice access; server administrators can always
  access channels. Bot permissions: **Manage Channels, View Channels, Send Messages,
  Read Message History, Attach Files, Embed Links, Connect and Speak**. Enable the
  existing Server Members intent in the Discord Developer Portal.
- Channel IDs survive restarts; deleted channels are recreated on the next run.
  Partial creation is rolled back, and repeated in-process requests are serialized.
  Run one bot instance per database; cross-process Discord creation is not locked.
- Close rooms before deleting a team/tournament: SQLite cascade cannot delete
  remote Discord channels automatically.

### Deployment and tests
This repository uses a shared tournament database, not guild-partitioned tournament
storage. Deploy to **one tournament server** and set `GUILD_ID` for guild-scoped
command synchronization. War room operations reject other guilds when `GUILD_ID`
is configured; certificate lookup is always scoped to its issuing guild. Staff
checks support all comma-separated `ADMIN_ROLE_ID` / `MANAGER_ROLE_ID` values.

```bash
python -m pytest tests/ -q          # or: python -m unittest discover -s tests -v
```

The suite covers graphics, migrations, certificate idempotency/revocation/guild
scope, verified player stats, stream lifecycle, URL validation, staff permissions,
mocked room creation/sync/close/rollback and offline extension registration.
Tests use temporary databases, not your runtime SQLite data. CI checks Python
3.11/3.12 with minimum and latest supported discord.py. Install developer tooling
with `pip install -r requirements-dev.txt` and run `python -m ruff check .`.
Discord delivery and channel permissions must additionally be smoke-tested in
an actual test server with a configured bot token; see [the checklist](docs/arena.md#required-real-server-smoke-test-not-simulated-by-unit-tests).
