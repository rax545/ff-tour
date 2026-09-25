# 🐺 WHITE WOLF GLOBAL — Free Fire Esports Tournament Bot (Premium Edition)

A high-end, production-grade Free Fire esports tournament Discord management bot designed for **𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥**. Features dynamic PIL tournament banner generation, automated OG battle dispatch DMs to team captains and squads, custom room credentials delivery, interactive registration panels with buttons and modals, result verification, and verified live leaderboards.

## ✨ Premium Features
- 🐺 **Dynamic Tournament Banners:** Beautiful, high-resolution esports banners auto-generated via Pillow (PIL) featuring server branding (**𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥**), tournament title, prize pool, squad slots, entry fee, and custom low-poly wolf emblems.
- 👥 **Full 4+1 Squad Lineups & Roles:** Register complete 4-player active rosters + 1 optional 5th player (Extra Substitute) in a single command (`/team create`) or add them individually (`/team addplayer`). Supports official Free Fire roles:
  - 👑 **IGL** (In-Game Leader / Captain)
  - ⚡ **Rusher** (Entry Fragger)
  - 🎯 **Sniper** (Marksman)
  - 💥 **Assaulter** (Main Damage Dealer)
  - 🛡️ **Support** (Utility / Medic)
  - 🔄 **Substitute** (5th Player / Extra)
- ⚡ **OG Squad Match Dispatches:** Creating a match via `/match create` automatically delivers a personalized, ultra-sleek OG battle dispatch message and embed to the DMs of all registered squads, including their specific team name, complete 4+1 roster breakdown with roles & UIDs, tournament name, map, and scheduled time.
- 🔑 **OG Room Credentials Release:** Releasing room credentials via `/match room` sends an OG access pass directly to team captains' DMs with copy-friendly Room ID and Password codeblocks.
- 🏆 **Interactive Tournament Panels:** Sleek Discord Views featuring **Register Squad** modal, **Tournament Info** with live progress bars, and **Registered Squads** list with live lineup status.
- 📊 **Scoring & Verification:** Captains submit match placements and kills, staff verifies results, and live point tables update in real time.
- 🛡️ **Admin Command Center:** Real-time database statistics, quick actions, payment approval/rejection workflows, and audit logging.
- 🎫 **Private Esports Support Tickets:** Automated ticket channel creation with strict permission overwrites.

## 🚀 Installation & Setup
Python 3.11+ is recommended.

```bash
pip install -r requirements.txt
```

Configure your environment variables in `.env`:
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
ADMIN_ROLE_ID=your_admin_role_id_here
MANAGER_ROLE_ID=your_manager_role_id_here
SERVER_NAME=𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥
BRAND=𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥
DATABASE_PATH=data/esports.sqlite3
```

Start the bot:
```bash
python bot.py
```

## 📋 Esports Tournament Workflow
1. **Staff:** Run `/tournament create` — Generates a dynamic branded banner and publishes the interactive squad registration panel.
2. **Captains:** Run `/team create` and `/team addplayer` to build their 4-man roster.
3. **Captains:** Click **🏆 Register Squad** on the tournament panel and input their Team ID.
4. **Staff:** Run `/match create` — Generates a match banner and blasts personalized OG match notice DMs to all registered squad captains/members with their team name and **𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥** branding!
5. **Staff:** Run `/match room` — Automatically delivers copyable Room ID & Password to captains via OG DM.
6. **Captains:** Run `/result submit` after the match.
7. **Staff:** Run `/result verify` to approve points.
8. **Everyone:** Run `/result leaderboard` to view verified standings.
