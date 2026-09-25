# FF ESPORTS BOT V2 — Premium Edition

A production-oriented Free Fire esports Discord management bot with premium panels, buttons/modals, automated room release, result verification and admin controls.

## Features
- 🏆 Tournament creation, open/close registration and interactive tournament panels
- 🎛️ Buttons + modal team registration
- 👥 Team creation, roster and player management
- 🎮 Match creation and room release
- 📩 Automatic DM room ID/password to registered team captains
- 📝 Captain result submission
- ✅ Staff result verification
- 🏆 Verified live leaderboard with placement + kill points
- 💳 Payment review workflow
- 🎫 Private support tickets
- 🛡️ Admin dashboard/statistics
- 📜 Audit logging
- 💾 SQLite persistence

## Install
Python 3.11+

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill the bot token/server ID/role IDs, then:

```bash
python bot.py
```

## Discord permissions/intents
Invite with `bot` + `applications.commands`. The bot needs Manage Channels for tickets, Send Messages, Embed Links, Read Message History, and Manage Messages if you add moderation. Enable Server Members Intent if member lookups are required.

## Important scoring note
The default placement table is in `config.py`. Replace it with the client's official tournament scoring rules before production use.

## Workflow
1. Staff: `/tournament create`
2. Captains: `/team create` and `/team addplayer`
3. Captains click **Register Team** on the tournament panel
4. Staff: `/match create`
5. Staff: `/match room` → captains automatically receive room credentials by DM
6. Captains: `/result submit`
7. Staff: `/result verify`
8. Everyone: `/result leaderboard`

Payment commands can be added around the existing database workflow; the bot does not move money.
