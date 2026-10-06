# 🐺 Root LU — Free Fire Esports Tournament Bot (Leading University Edition)

A high-end, production-grade Free Fire esports tournament Discord management bot customized for Leading University's **Root LU** community. Features CSE batch & section rankings, official student ID verification, individual fragger tracking & MVP rankings, match fixtures with official 5-map rotation, dynamic tournament banners, automated match dispatch DMs, custom room credential delivery, interactive registration panels, and real-time verified leaderboards.

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
Python 3.11+ is recommended.

```bash
pip install -r requirements.txt
```

Configure environment variables in `.env`:
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

### 🏛️ Section & Student Commands
- `/section leaderboard [tournament_id]` — Show CSE Batch & Section point tables and rankings.
- `/student verify <student_id> <name> <batch> <section> [department]` — Verify official Student ID.
- `/student profile [member]` — View verified student profile and team affiliations.

### 🏆 Tournament Commands
- `/tournament create <name> <max_teams> [entry_fee] [prize_pool] [description]` — Create and publish tournament panel.
- `/tournament fixtures <tournament_id>` — View match fixtures and 5-map rotation schedule.
- `/tournament list` — List all active tournaments.
- `/tournament slots <tournament_id> [page]` — Show registered lobby slots.
- `/tournament rules` — Display tournament rulebook.
- `/tournament close <tournament_id>` — Close registration.

### 🛡️ Team Commands
- `/team create <tournament_id> <name> <tag> <captain_ign> <captain_uid> [batch] [section] ...` — Register full 4+1 squad with batch & section.
- `/team roster <team_id>` — View squad roster, roles, UIDs, batch & section.
- `/team addplayer <team_id> <ign> <uid> [role] [member] [is_substitute]` — Add starter or substitute.

### 🎮 Match Commands
- `/match create <tournament_id> <match_no> <map_name> [scheduled_at]` — Create match & dispatch DMs.
- `/match room <match_id> <room_id> <password>` — Release room credentials to captains.
- `/match stream <match_id> <stream_url> <platform>` — Start a live broadcast announcement and notify all registered players.
- `/admin notifychannel <channel>` — Set the server's persistent live-notification channel (staff only).

### 📊 Result Commands
- `/result submit <match_id> <team_id> <placement> <kills>` — Submit squad match result.
- `/result verify <result_id>` — Verify match score.
- `/result leaderboard <tournament_id>` — Show verified squad leaderboard.
- `/result topfraggers [tournament_id] [limit]` — Show top individual kill fraggers & MVP.
- `/result table <tournament_id> [page]` — Generate 1200x880 graphical points table.
- `/result booyah <tournament_id>` — Generate golden Booyah winner card.
- `/result mvp <tournament_id>` — Generate cyberpunk MVP card.
