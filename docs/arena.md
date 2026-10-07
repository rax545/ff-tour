# Arena expansion: eight integrated Discord features

This is an extension of the existing **Free Fire Discord bot**, not a web app or
an external streaming/identity service. No additional runtime dependency or API
key is required beyond the existing Discord bot setup. All graphics are rendered
locally with Pillow; user-provided URLs are never fetched.

## বাংলা দ্রুত নির্দেশিকা

| ফিচার | প্রধান কমান্ড | ব্যবহারকারী |
| --- | --- | --- |
| লাইভ স্ট্রিম | `/match stream`, `/live list`, `/match streamstop` | স্টাফ চালু/বন্ধ করবেন; সবাই দেখবেন |
| হল অফ ফেম | `/halloffame induct`, `/halloffame show` | স্টাফ চূড়ান্ত করবেন; সবাই দেখবেন |
| ব্র্যাকেট ট্রি | `/bracket create`, `/bracket tree`, `/bracket resolve` | স্টাফ ফল নিশ্চিত করবেন |
| প্লেয়ার পাসপোর্ট | `/passport`, `/result player` | নিজের পাসপোর্ট প্রাইভেট; স্টাফ ব্যক্তিগত স্কোর দেবেন |
| ক্ল্যাশ পোস্টার | `/clash poster` | সার্ভারের সবাই |
| প্রেডিকশন অ্যারেনা | `/prediction open`, `/prediction arena`, `/prediction pick` | স্টাফ খুলবেন; সবাই ভোট দেবেন |
| অ্যান্টি-স্মার্ফ রাডার | `/radar scan`, `/radar review` | শুধু স্টাফ, সব উত্তর প্রাইভেট |
| স্কোয়াড ওয়ার রুম | `/squad warroom`, `/squad plan`, `/squad readycheck` | ক্যাপ্টেন/স্টাফ পরিচালনা করবেন |

**গুরুত্বপূর্ণ:** প্রেডিকশনে টাকা, বাজি বা পুরস্কার পেআউট নেই। রাডারের সংকেত
চিটিং বা স্মার্ফিংয়ের প্রমাণ নয়; কোনো স্বয়ংক্রিয় ব্যান হয় না। পাসপোর্টের
পরিচয় রোস্টার-লিংক করা, Garena-যাচাইকৃত পরিচয় নয়।

## Setup, upgrade and access

1. Back up your SQLite database **while the bot is stopped**.
2. Install Python 3.11+ and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, fill in your token **locally**, and set the real
   `GUILD_ID`, `ADMIN_ROLE_ID` and `MANAGER_ROLE_ID`. The role variables accept
   comma-separated IDs. Do not commit `.env`.
4. Enable Server Members intent and the existing Message Content intent in the
   Discord Developer Portal. Invite the bot with `bot` and `applications.commands`.
5. For graphics/delivery: View Channels, Send Messages, Embed Links, Attach Files,
   Read Message History. For war rooms: also Manage Channels, Connect and Speak.
6. Run **one bot process per database/server** with `python bot.py`. Startup
   performs additive, idempotent migrations and registers the new cog and
   persistent component handlers. There is no destructive seed/reset step.

Tournament storage remains shared, as in the original bot. This is **not** a
multi-server deployment: set `GUILD_ID`. Arena, esports and persistent component
operations reject DMs and other guilds when it is configured. Private responses
are ephemeral, but users can download/share their own attachments. Server
administrators always retain access to Discord channels.

DejaVu Sans system fonts are recommended for graphics. The existing renderer has
a Pillow default-font fallback and normalizes unsupported characters. PNG labels
are primarily English; Discord messages retain player/team names. Public graphic queries/passports and radar
scans have a five-second per-user cooldown to limit accidental request spam.

## 1. Live stream lifecycle

```text
/admin notifychannel channel:#live
/match stream match_id:1 stream_url:https://youtu.be/your-stream platform:YouTube
/live list [tournament_id] [page]
/match streamstatus match_id:1
/match streamstop match_id:1
```

- Staff manually control LIVE/OFFLINE; the bot does **not** host video, check
  provider uptime, embed a player or stop a YouTube/Twitch/Facebook stream.
- Starting generates a 1280×720 PNG, posts a Watch Live button **before** DM fan-out,
  and sends bounded-concurrency DMs to current captains and linked players.
  A Discord account on multiple squads is contacted once. Bound knockout fixtures
  notify only their two opponents. Accounts no longer in the guild are not DMed.
- The configured channel falls back to the invoking channel when missing,
  inaccessible or unable to send. Failures are counted; counts are not read receipts.
  `notify_players:false` suppresses DMs, not the public announcement.
- Identical live requests are idempotent and do not resend. `rebroadcast:true`
  deliberately creates a new revision and re-announces; use this after fixing a
  failed announcement. Changed links also create a new revision. Old announcements
  are marked offline best-effort; deleted/inaccessible messages do not block state.
- Starting locks associated predictions. Stopping records an end timestamp,
  retains the replay URL, and removes the LIVE image from the saved announcement.
  A stopped/replaced revision skips queued DMs; already-sent/in-flight Discord
  requests cannot be recalled. This is not exactly-once remote delivery.
- Structural URL validation rejects credentials, IP literals, local host suffixes,
  control characters and unusual ports; it is not a phishing/reputation check.
  Only staff should publish trusted links. Finished fixtures cannot be marked live.

## 2. Hall of Fame

```text
/halloffame induct tournament_id:1
/halloffame show [tournament_id] [page]
/halloffame revoke archive_id:1 reason:"Score dispute upheld"
```

Staff finalization creates an immutable, guild-scoped champions/MVP snapshot,
sets the tournament to `finished`, and produces the champions gallery (four
archives per page). Repeating induction, including concurrently, returns the same
record; it does not recalculate an already archived championship.

- **Battle Royale:** every registered squad must have a verified result for every
  fixture, no pending scores may remain, placements must be a complete unique
  sequence, and live broadcasts must be stopped. Ranking: total points, kills,
  first-place finishes, then team ID (ascending). Top three are archived.
- **Knockout:** a bracket must have a staff-confirmed final. The final winner and
  loser determine champion/runner-up, not aggregate BR points. Node scores are
  staff attestations, not automated Garena match verification.
- MVP uses verified, roster-matched, unambiguous **individual** results only.
  Missing individual data means **no MVP**, never invented team-kill attribution.
- Team renames, score corrections and even deletion of source tournaments do not
  rewrite the archive. Revocation hides it publicly but preserves its snapshot,
  staff reason and audit entry. Revoked archives cannot silently be reissued.
  The tournament remains finalized; use a new tournament for a corrected event.

## 3. Bracket tree

```text
/bracket create tournament_id:1 [seeds:"3,1,2"]
/bracket tree tournament_id:1 [page]
/bracket bind node_id:2 match_id:1
/bracket resolve node_id:2 winner_team_id:3 score_a:0 score_b:2
```

- One single-elimination bracket per guild/tournament, **2–32 squads**. Default
  seed order is ascending team ID; optional seeds must list every registered team
  exactly once, best seed first. Creation closes registration and snapshots names.
- The next power-of-two lobby is seeded to separate high seeds. BYEs automatically
  advance; an unresolved predecessor is **TBD**, never a BYE. Draws are rejected.
- The PNG shows the whole connected tree; text pages show eight nodes with actual
  team IDs, A/B order and bound fixtures. Use **database node IDs**, not match numbers.
- Scores 0–99 are staff-confirmed series scores. Winner must be a current opponent
  and have the higher score. Identical retries are harmless; conflicting corrections
  are rejected because they would invalidate downstream opponents. No destructive
  reset command is provided: create a new tournament for a corrected bracket.
- Binding is optional: bind a READY node to an unused scheduled `/match create`
  fixture **before** stream/room/results/predictions. BR fixtures otherwise still use
  the full lobby. Binding restricts private room-credential DMs, posters, results, ready checks, streaming
  notifications and prediction options to the two opponents. Resolving a bound node
  finishes that fixture, locks predictions and marks its broadcast offline.
- Brackets are an additional knockout/Clash Squad workflow; they do not automatically
  create Discord match fixtures or reinterpret the original multi-squad BR scoring.
  Complete 4+1 rosters and individual results still use the existing tournament model.

## 4. Player passport and verified individual results

```text
/team roster team_id:1
/result player match_id:1 member_id:1 kills:7 damage:1800
/passport
/result topfraggers tournament_id:1
/result mvp tournament_id:1
```

The roster lists database **member IDs** for staff entry. `/result player` records
or corrects one verified individual result for that UID/match, with roster/fixture
validation and audit logging. Kills cannot exceed a verified squad total when that
squad total exists. Enter accurate team totals before individual results when
possible; staff must reconcile inconsistent legacy rows before retrying.

The private 1200×720 passport shows your linked IGNs/UIDs, recent squads, roles,
verified kills/damage/matches and verified batch/section (not student ID). Captains
link Discord accounts with `/team addplayer ... member:@player`. This is a roster
link, **not** proof of game-account ownership or official Garena identity checking.

Duplicate UID/match result rows, conflicting Discord owners, unverified records
and wrong-tournament results are excluded rather than choosing an arbitrary owner.
Duplicate roster joins do not multiply stats. Blank UIDs do not identify a player.
Top-fragger and MVP commands now use the same honest individual-result source;
**the old fallback assigning an entire squad's kills to each player is removed**.
Without recorded individual results, stats are zero and no MVP is invented.

## 5. Clash poster

```text
/clash poster match_id:1 team_a_id:1 team_b_id:2
```

Generates a local 1600×900 versus PNG with tournament, map/schedule, names/tags,
4+1 IGN/role lineups and verified squad statistics. Both squads must be distinct
fixture entrants. Bound brackets enforce their opponent pair. It never includes
Free Fire UIDs, student IDs, private tactics, room IDs/passwords, or fetched logos.
Discord `<t:…>` schedules are labels in graphics; Discord itself renders relative
timestamps in the accompanying commands, not inside the PNG.

## 6. Prediction arena

```text
/prediction open match_id:1 closes_at:"2026-10-07 21:00"
/prediction list [page]
/prediction arena pool_id:1 [page]
/prediction pick pool_id:1 team_id:2
/prediction mypick pool_id:1
/prediction lock pool_id:1
/prediction settle pool_id:1
/prediction cancel pool_id:1
/prediction leaderboard [page]
```

- Free bragging-rights predictions only: **10 points per correct pick**, no money,
  balances, stakes, purchases, odds, cash prizes, payouts or gambling integration.
- Staff open before the fixture starts, room release or any result submission.
  Cutoff is interpreted in `TIMEZONE_UTC_OFFSET` and must be in the next 30 days.
  Use absolute dates or `/reminder set` to make the match start unambiguous.
- The cutoff cannot exceed a known absolute match start. Every click/command checks
  the database time/state, even on stale messages. LIVE, room release or submitted
  results lock picks. Earlier reminder reschedules clamp cutoff/ready-check expiry;
  later reschedules never extend those deadlines. Arbitrary `TBA`/free-form schedules
  cannot provide a reliable automatic match start; staff must lock before actual play.
- One pick per Discord account, editable only before lock. Bots are rejected.
  Several separate Discord accounts belonging to one person cannot be proven or
  prevented by this bot; the radar offers review leads, not Sybil protection.
- Entrants are snapshotted at opening. The selector/PNG shows **12 teams per page**,
  remains routable after restarts, and checks authorization/valid entrants every time.
  Counts/status in an existing image are snapshots: refresh `/prediction arena`.
  Other users' individual picks stay private; public totals and opted-in ranks are shown.
- Settlement requires a locked arena and either complete, unique verified BR
  placements for all snapshotted entrants or a finished bound bracket node. Points
  are stored once transactionally, even under concurrent staff retries.
- Cancelled arenas award nothing and cannot reopen; settled arenas cannot be cancelled
  or award again. Staff corrections to source results do not silently change settled
  scores. Match/tournament deletion cascades arenas and their points, as with original
  result records: keep source data and backups for long-lived prediction ranks.

## 7. Anti-smurf radar (review only)

```text
/radar scan tournament_id:1 [page]
/radar list tournament_id:1 [page] [include_inactive:true]
/radar review finding_id:1 decision:cleared note:"Registration typo corrected"
```

Every response is **staff-only and ephemeral**. No data is scraped, no Garena API
is called, and no bans, public accusations, role changes or roster removals occur.

Signals with concrete evidence:
1. Normalized duplicate Free Fire UID in multiple slots in this tournament.
2. One linked Discord account/captain assigned to multiple squads in this tournament.
3. A young **Discord** account (snowflake creation time); game-account age is unknown.
4. Duplicate verified UID/match result rows that could inflate stats.
5. High recorded verified individual kills/match, with a minimum sample; high skill
   and scoring errors are possible, so this remains **low severity**, not proof.

Thresholds: `RADAR_NEW_ACCOUNT_DAYS=7`, `RADAR_MIN_MATCHES=3` (minimum 3),
`RADAR_KILLS_PER_MATCH=12`. Ordinary same-player reuse across different tournaments
is not a duplicate-roster signal. No findings does not mean identity clearance.

Findings are fingerprinted/upserted, with first/last seen, private evidence,
reviewer and required review note. Scans preserve reviews and mark disappeared
signals inactive, rather than deleting history or automatically reopening a review.
Re-review when evidence changes. `confirmed` means a human-confirmed **review
concern**, not an automated cheating determination. Only staff choose any separate
moderation action. Evidence contains roster UIDs/account IDs: restrict DB backups
and honor your community's privacy/deletion policy.

## 8. Squad war room

Existing `/squad warroom` and `/squad close` keep private text/voice channels,
stable saved channel IDs, explicit `@everyone` denies, configured staff access,
roster synchronization, creation rollback and in-process creation locks.

```text
/squad warroom team_id:1
/squad plan team_id:1 map_name:Bermuda drop_zone:"Clock Tower" strategy:"Rotate north after loot"
/squad briefing team_id:1
/squad readycheck team_id:1 match_id:1
/squad ready check_id:1 [ready:false]
/squad readiness check_id:1
/squad readyclose check_id:1
/squad close team_id:1
```

- Captain/staff edit notes; **current** roster/captain/staff can read private briefings.
  Official five-map choices, drop zone and strategy are persisted. Notes are not
  copied into public images or audit details.
- Captain/staff start a ready check and post its buttons only in the synchronized
  private war room. Checks expire after one hour or a known earlier match start;
  they can also be closed early. Same squad/fixture requests reuse the check ID
  (and can post another private status message), not duplicate responses.
- Each linked player/captain can mark only themselves ready/not-ready. Off-roster
  staff may inspect, but not pretend to be a ready player. Current roster membership
  is rechecked on each command/button; removed members' responses no longer count.
  Unlinked slots are explicitly reported, never silently counted as ready.
- Dynamic buttons work across restarts; stale/expired/closed buttons cannot update
  state. Old message counts can become stale on concurrent updates; `/squad readiness`
  is the authoritative current view. Closing channels does not erase notes/checks.
- Rerun `/squad warroom` after roster changes to reconcile Discord channel overwrites.
  Current-roster authorization protects notes/checks immediately, but old channel
  access lasts until synchronization. Close channels before deleting a squad/event;
  SQLite cascade cannot delete remote Discord channels automatically.

## Offline tests and CI

```bash
pip install -r requirements-dev.txt
python -m ruff check .
python -m compileall -q bot.py config.py cogs database services utils views tests
python -m unittest discover -s tests -v
```

All database tests use disposable temporary files; tests do not alter the shipped
SQLite database. Tests cover legacy-data upgrade, repeated migrations, rollback,
all supported bracket sizes/BYEs, concurrency/idempotency, complete verified
standings, private stats, frozen archives, voting cutoff/settlement, radar reviews,
roster/ready expiry, image dimensions/content and mocked Discord delivery/fallback.
CI runs Python 3.11/3.12 against both minimum discord.py 2.4.0 and latest supported
2.x, without a bot token.

### Required real-server smoke test (not simulated by unit tests)

- Install in a test guild, sync commands, and verify ordinary players cannot run
  staff operations or view other squads' tactics/radar output.
- Create two squads and complete rosters; start/stop a trusted stream. Check fallback
  announcement, member DMs, closed-DM counts and replay button/image cleanup.
- Create a three-team bracket to exercise one BYE; bind fixtures before room/stream/
  predictions, resolve each node, and verify final winner/archived gallery.
- Open predictions, cast/change picks, restart the bot and use old selector messages;
  lock, record/verify results, settle twice and check only one ten-point award.
- Record individual results and compare passport/MVP stats; confirm no student ID,
  private strategy or room password appears in public images.
- Create war rooms; check text/voice access as captain/member/outsider/admin, post
  ready checks, restart, remove a linked player and rerun room sync. Verify the old
  player cannot access notes/checks and loses channel access after sync.
- Scan a deliberate duplicate UID as staff; clear it and rescan. Check private review
  history remains and no player is automatically banned or removed.
