import io
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from config import SERVER_NAME, BRAND
from database.db import connect, audit, get_setting
from services.arena import validate_stream_url, stream_status
from services.scoring import calculate
from services.leaderboard import leaderboard, section_leaderboard, top_fraggers
from utils.banner import generate_tournament_banner, generate_match_banner
from utils.embeds import base, ok, err, og_match_dm_embed, og_room_dm_embed, stream_live_dm_embed
from utils.permissions import require_staff
from utils.cards import room_pass, points_table, booyah, mvp, live_broadcast, slot_grid
from views.panels import TournamentPanel

OFFICIAL_5_MAP_ROTATION = [
    (1, "Bermuda", "🏝️", "Classic Battle Royale & Close-Quarter Combat"),
    (2, "Purgatory", "🌋", "High-Ground Elevation & Long-Range Sniping"),
    (3, "Kalahari", "🏜️", "Fast-Paced Desert War & Tactical Drops"),
    (4, "Alpine", "❄️", "Multi-Tier Snow Terrain & Heavy Assault Combat"),
    (5, "NexTerra", "⚡", "Futuristic Cyberpunk Battlefield & Anti-Gravity Zones"),
]

ROLE_CHOICES = [
    app_commands.Choice(name="👑 IGL (In-Game Leader / Captain)", value="IGL"),
    app_commands.Choice(name="⚡ Rusher (Entry Fragger)", value="Rusher"),
    app_commands.Choice(name="🎯 Sniper (Long Range Marksman)", value="Sniper"),
    app_commands.Choice(name="💥 Assaulter (Main Damage Dealer)", value="Assaulter"),
    app_commands.Choice(name="🛡️ Support (Utility / Grenadier)", value="Support"),
    app_commands.Choice(name="🔄 Substitute (5th / Extra Player)", value="Substitute"),
]

def stream_link_view(stream_url, platform):
    """Build a stateless Discord link view for public announcements and DMs."""
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label=f"📺 Watch Live on {platform}"[:80],
        style=discord.ButtonStyle.link,
        url=stream_url
    ))
    return view


ROLE_BADGES = {
    "IGL": "👑 IGL",
    "Rusher": "⚡ Rusher",
    "Sniper": "🎯 Sniper",
    "Assaulter": "💥 Assaulter",
    "Support": "🛡️ Support",
    "Substitute": "🔄 Sub / 5th",
    "Captain": "👑 IGL / Captain",
    "Player": "🎮 Player",
}


class Esports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    tournament = app_commands.Group(
        name="tournament",
        description="Tournament commands"
    )

    team = app_commands.Group(
        name="team",
        description="Team commands"
    )

    match = app_commands.Group(
        name="match",
        description="Match commands"
    )

    result = app_commands.Group(
        name="result",
        description="Result commands"
    )

    section = app_commands.Group(
        name="section",
        description="CSE Batch & Section standings"
    )

    student = app_commands.Group(
        name="student",
        description="Student verification commands"
    )

    # =========================================================
    # TOURNAMENT CREATE
    # =========================================================

    @tournament.command(
        name="create",
        description="Create and publish a tournament panel with premium banner"
    )
    @app_commands.describe(
        name="Tournament name",
        max_teams="Maximum number of teams",
        entry_fee="Entry fee in BDT/৳",
        prize_pool="Prize pool in BDT/৳",
        description="Tournament description",
        banner_url="Optional custom banner image URL"
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        max_teams: int,
        entry_fee: float = 0.0,
        prize_pool: float = 0.0,
        description: str = "Official FF esports tournament.",
        banner_url: str = ""
    ):
        if not await require_staff(interaction):
            return

        name = name.strip()
        description = description.strip()
        banner_url = banner_url.strip()

        if not name:
            return await interaction.response.send_message(
                embed=err("Tournament name cannot be empty."),
                ephemeral=True
            )

        if max_teams < 1:
            return await interaction.response.send_message(
                embed=err("Maximum teams must be at least **1**."),
                ephemeral=True
            )

        if entry_fee < 0:
            return await interaction.response.send_message(
                embed=err("Entry fee cannot be negative."),
                ephemeral=True
            )

        if prize_pool < 0:
            return await interaction.response.send_message(
                embed=err("Prize pool cannot be negative."),
                ephemeral=True
            )

        # Defer interaction to avoid 3-second timeout during banner generation and DB write
        await interaction.response.defer()

        db = await connect()

        try:
            cur = await db.execute(
                """
                INSERT INTO tournaments
                (
                    name,
                    description,
                    max_teams,
                    entry_fee,
                    prize_pool,
                    banner_url,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    max_teams,
                    entry_fee,
                    prize_pool,
                    banner_url,
                    interaction.user.id
                )
            )

            tournament_id = cur.lastrowid
            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.followup.send(
                embed=err(f"Failed to create tournament.\n```{e}```"),
                ephemeral=True
            )

        finally:
            await db.close()

        await audit(
            interaction.user.id,
            "tournament_create",
            str(tournament_id)
        )

        file = None
        if not banner_url:
            banner_buf = generate_tournament_banner(
                tournament_name=name,
                server_name=SERVER_NAME,
                max_teams=max_teams,
                prize_pool=prize_pool,
                entry_fee=entry_fee,
                tournament_id=tournament_id,
                status="OPEN"
            )
            file = discord.File(banner_buf, filename="tournament_banner.png")

        embed = discord.Embed(
            title=f"🔥 {name}",
            description=(
                f"```fix\n"
                f"🐺 {SERVER_NAME} • FREE FIRE ESPORTS 🐺\n"
                f"```\n"
                f"{description}\n\n"
                f"⚔️ **Registration is officially OPEN!** Click **Register Squad** below to claim your spot in the arena."
            ),
            color=discord.Color.from_rgb(124, 58, 237),
            timestamp=discord.utils.utcnow()
        )

        if file:
            embed.set_image(url="attachment://tournament_banner.png")
        elif banner_url:
            embed.set_image(url=banner_url)

        embed.add_field(
            name="🏆 Tournament ID",
            value=f"`#{tournament_id}`",
            inline=True
        )

        embed.add_field(
            name="👥 Squad Slots",
            value=f"`{max_teams}` Squads",
            inline=True
        )

        embed.add_field(
            name="🎮 Format",
            value="`Squad Battle Royale`",
            inline=True
        )

        embed.add_field(
            name="💳 Entry Fee",
            value=f"৳{entry_fee:g}" if entry_fee > 0 else "`FREE ENTRY`",
            inline=True
        )

        embed.add_field(
            name="💰 Prize Pool",
            value=f"৳{prize_pool:g}" if prize_pool > 0 else "`GLORY & HONOR`",
            inline=True
        )

        embed.add_field(
            name="📌 Status",
            value="🟢 **REGISTRATION OPEN**",
            inline=True
        )

        embed.add_field(
            name="🐺 Organized By",
            value=f"**{SERVER_NAME}**",
            inline=True
        )

        embed.add_field(
            name="👑 Host Staff",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="🛡️ Platform",
            value="`Free Fire Mobile`",
            inline=True
        )

        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Tournament System"
        )

        if file:
            await interaction.followup.send(
                embed=embed,
                file=file,
                view=TournamentPanel(tournament_id)
            )
        else:
            await interaction.followup.send(
                embed=embed,
                view=TournamentPanel(tournament_id)
            )

    # =========================================================
    # TOURNAMENT CLOSE
    # =========================================================

    @tournament.command(
        name="close",
        description="Close tournament registration"
    )
    @app_commands.describe(
        tournament_id="Tournament ID"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        tournament_id: int
    ):
        if not await require_staff(interaction):
            return

        if tournament_id < 1:
            return await interaction.response.send_message(
                embed=err("Invalid tournament ID."),
                ephemeral=True
            )

        db = await connect()

        try:
            cur = await db.execute(
                "SELECT id, name, status FROM tournaments WHERE id=?",
                (tournament_id,)
            )

            tournament = await cur.fetchone()

            if not tournament:
                await db.close()

                return await interaction.response.send_message(
                    embed=err("Tournament not found."),
                    ephemeral=True
                )

            if tournament["status"] == "closed":
                await db.close()

                return await interaction.response.send_message(
                    embed=err("Tournament registration is already closed."),
                    ephemeral=True
                )

            await db.execute(
                "UPDATE tournaments SET status='closed' WHERE id=?",
                (tournament_id,)
            )

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.response.send_message(
                embed=err(f"Failed to close tournament.\n```{e}```"),
                ephemeral=True
            )

        await db.close()

        await audit(
            interaction.user.id,
            "tournament_close",
            str(tournament_id)
        )

        embed = base(
            "🔒 Registration Closed",
            (
                f"🏆 Tournament **#{tournament_id} — {tournament['name']}**\n\n"
                f"Registration has been officially **closed**.\n"
                f"Brackets and matches will be announced shortly by **{SERVER_NAME}** staff."
            ),
            color=discord.Color.from_rgb(239, 68, 68)
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # TOURNAMENT LIST
    # =========================================================

    @tournament.command(
        name="list",
        description="List active and recent tournaments"
    )
    async def list_(
        self,
        interaction: discord.Interaction
    ):
        db = await connect()

        try:
            cur = await db.execute(
                """
                SELECT
                    id,
                    name,
                    status,
                    max_teams,
                    entry_fee,
                    prize_pool
                FROM tournaments
                ORDER BY id DESC
                LIMIT 15
                """
            )

            rows = await cur.fetchall()

        finally:
            await db.close()

        if not rows:
            return await interaction.response.send_message(
                embed=base(
                    f"🏆 {SERVER_NAME} • Tournament Hub",
                    "No tournaments have been created yet.\nStaff can create one using `/tournament create`."
                )
            )

        embed = base(
            f"🏆 {SERVER_NAME} • Tournament Hub",
            "Latest competitive Free Fire tournaments"
        )

        for row in rows:
            status = str(row["status"]).upper()

            if status == "OPEN":
                status_icon = "🟢"
            elif status == "CLOSED":
                status_icon = "🔴"
            else:
                status_icon = "🟡"

            embed.add_field(
                name=f"#{row['id']} • {row['name']}",
                value=(
                    f"{status_icon} Status: **{status}**\n"
                    f"👥 Slots: **{row['max_teams']} Squads**\n"
                    f"💳 Entry: **৳{row['entry_fee']:g}**\n"
                    f"💰 Prize: **৳{row['prize_pool']:g}**"
                ),
                inline=False
            )

        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Esports Management"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # TEAM CREATE (4 Starters + 1 Extra Substitute Player with Roles & Batch/Section)
    # =========================================================

    @team.command(
        name="create",
        description="Register a full 4-player squad + optional 5th player (substitute) with roles and batch/section"
    )
    @app_commands.describe(
        tournament_id="Tournament ID",
        name="Team name",
        tag="Team tag (e.g., WW, ALPHA)",
        captain_ign="Captain (P1) Free Fire IGN",
        captain_uid="Captain (P1) Free Fire UID",
        batch="CSE Batch (e.g. 60, 59, 58)",
        section="Section (e.g. A, B, C, D)",
        captain_role="Captain's role (IGL, Rusher, etc.)",
        p2_ign="Player 2 Free Fire IGN",
        p2_uid="Player 2 Free Fire UID",
        p2_role="Player 2 role",
        p2_member="Optional Discord member for Player 2",
        p3_ign="Player 3 Free Fire IGN",
        p3_uid="Player 3 Free Fire UID",
        p3_role="Player 3 role",
        p3_member="Optional Discord member for Player 3",
        p4_ign="Player 4 Free Fire IGN",
        p4_uid="Player 4 Free Fire UID",
        p4_role="Player 4 role",
        p4_member="Optional Discord member for Player 4",
        sub_ign="Optional 5th Player (Extra Substitute) Free Fire IGN",
        sub_uid="Optional 5th Player (Extra Substitute) Free Fire UID",
        sub_role="Optional 5th Player role",
        sub_member="Optional Discord member for 5th Player",
        logo_url="Optional team logo URL"
    )
    @app_commands.choices(
        captain_role=ROLE_CHOICES,
        p2_role=ROLE_CHOICES,
        p3_role=ROLE_CHOICES,
        p4_role=ROLE_CHOICES,
        sub_role=ROLE_CHOICES,
    )
    async def team_create(
        self,
        interaction: discord.Interaction,
        tournament_id: int,
        name: str,
        tag: str,
        captain_ign: str,
        captain_uid: str,
        batch: str = "",
        section: str = "",
        captain_role: app_commands.Choice[str] = None,
        p2_ign: str = "",
        p2_uid: str = "",
        p2_role: app_commands.Choice[str] = None,
        p2_member: discord.Member = None,
        p3_ign: str = "",
        p3_uid: str = "",
        p3_role: app_commands.Choice[str] = None,
        p3_member: discord.Member = None,
        p4_ign: str = "",
        p4_uid: str = "",
        p4_role: app_commands.Choice[str] = None,
        p4_member: discord.Member = None,
        sub_ign: str = "",
        sub_uid: str = "",
        sub_role: app_commands.Choice[str] = None,
        sub_member: discord.Member = None,
        logo_url: str = ""
    ):
        name = name.strip()
        tag = tag.strip().upper()
        captain_ign = captain_ign.strip()
        captain_uid = captain_uid.strip()
        batch = batch.strip()
        section = section.strip().upper()
        logo_url = logo_url.strip()

        if tournament_id < 1:
            return await interaction.response.send_message(
                embed=err("Invalid tournament ID."),
                ephemeral=True
            )

        if not name or not tag or not captain_ign or not captain_uid:
            return await interaction.response.send_message(
                embed=err(
                    "Team name, tag, Captain IGN, and Captain UID are required."
                ),
                ephemeral=True
            )

        if len(tag) > 10:
            return await interaction.response.send_message(
                embed=err("Team tag must be 10 characters or less."),
                ephemeral=True
            )

        # Defer in case many players are being processed
        await interaction.response.defer()

        # Parse roles
        c_role = captain_role.value if captain_role else "IGL"
        r2 = p2_role.value if p2_role else "Rusher"
        r3 = p3_role.value if p3_role else "Sniper"
        r4 = p4_role.value if p4_role else "Assaulter"
        r_sub = sub_role.value if sub_role else "Substitute"

        # Prepare lineup array
        players_to_add = []
        # Slot 1: Captain (Starter)
        players_to_add.append({
            "slot": 1,
            "user_id": interaction.user.id,
            "ign": captain_ign,
            "uid": captain_uid,
            "role": c_role,
            "is_sub": 0,
            "mention": interaction.user.mention
        })

        # Slot 2 (Starter)
        if p2_ign.strip() and p2_uid.strip():
            players_to_add.append({
                "slot": 2,
                "user_id": p2_member.id if p2_member else 0,
                "ign": p2_ign.strip(),
                "uid": p2_uid.strip(),
                "role": r2,
                "is_sub": 0,
                "mention": p2_member.mention if p2_member else ""
            })

        # Slot 3 (Starter)
        if p3_ign.strip() and p3_uid.strip():
            players_to_add.append({
                "slot": 3,
                "user_id": p3_member.id if p3_member else 0,
                "ign": p3_ign.strip(),
                "uid": p3_uid.strip(),
                "role": r3,
                "is_sub": 0,
                "mention": p3_member.mention if p3_member else ""
            })

        # Slot 4 (Starter)
        if p4_ign.strip() and p4_uid.strip():
            players_to_add.append({
                "slot": 4,
                "user_id": p4_member.id if p4_member else 0,
                "ign": p4_ign.strip(),
                "uid": p4_uid.strip(),
                "role": r4,
                "is_sub": 0,
                "mention": p4_member.mention if p4_member else ""
            })

        # Slot 5 (Extra Substitute)
        if sub_ign.strip() and sub_uid.strip():
            players_to_add.append({
                "slot": 5,
                "user_id": sub_member.id if sub_member else 0,
                "ign": sub_ign.strip(),
                "uid": sub_uid.strip(),
                "role": r_sub,
                "is_sub": 1,
                "mention": sub_member.mention if sub_member else ""
            })

        db = await connect()

        try:
            # Check if user is verified to auto-fill batch/section if omitted
            if not batch or not section:
                cur = await db.execute(
                    "SELECT batch, section FROM student_verifications WHERE user_id=?",
                    (interaction.user.id,)
                )
                student_row = await cur.fetchone()
                if student_row:
                    if not batch:
                        batch = student_row["batch"]
                    if not section:
                        section = student_row["section"]

            # Check tournament
            cur = await db.execute(
                "SELECT * FROM tournaments WHERE id=?",
                (tournament_id,)
            )
            tournament = await cur.fetchone()

            if not tournament:
                await db.close()
                return await interaction.followup.send(
                    embed=err("Tournament not found."),
                    ephemeral=True
                )

            if tournament["status"] != "open":
                await db.close()
                return await interaction.followup.send(
                    embed=err("Registration for this tournament is closed."),
                    ephemeral=True
                )

            # Check if captain already created a team for this tournament
            cur = await db.execute(
                "SELECT id FROM teams WHERE tournament_id=? AND captain_id=?",
                (tournament_id, interaction.user.id)
            )
            existing = await cur.fetchone()

            if existing:
                await db.close()
                return await interaction.followup.send(
                    embed=err(
                        f"You already created team **#{existing['id']}** for this tournament."
                    ),
                    ephemeral=True
                )

            # Check tournament slot capacity
            cur = await db.execute(
                """
                SELECT COUNT(DISTINCT team_id) AS count
                FROM (
                    SELECT id AS team_id FROM teams WHERE tournament_id=?
                    UNION
                    SELECT team_id FROM registrations WHERE tournament_id=?
                )
                """,
                (tournament_id, tournament_id)
            )
            count_row = await cur.fetchone()
            if count_row["count"] >= tournament["max_teams"]:
                await db.close()
                return await interaction.followup.send(
                    embed=err("This tournament is already full."),
                    ephemeral=True
                )

            # Insert Team
            cur = await db.execute(
                """
                INSERT INTO teams
                (
                    tournament_id,
                    name,
                    tag,
                    captain_id,
                    logo_url,
                    batch,
                    section
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    name,
                    tag,
                    interaction.user.id,
                    logo_url,
                    batch,
                    section
                )
            )
            team_id = cur.lastrowid

            # Insert Lineup Players
            for p in players_to_add:
                await db.execute(
                    """
                    INSERT INTO team_members
                    (
                        team_id,
                        user_id,
                        ign,
                        uid,
                        role,
                        is_sub
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        team_id,
                        p["user_id"],
                        p["ign"],
                        p["uid"],
                        p["role"],
                        p["is_sub"]
                    )
                )

            # Auto-register into registrations table
            await db.execute(
                """
                INSERT OR IGNORE INTO registrations
                (
                    tournament_id,
                    team_id,
                    status
                )
                VALUES (?, ?, 'registered')
                """,
                (
                    tournament_id,
                    team_id
                )
            )

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()
            return await interaction.followup.send(
                embed=err(f"Failed to create team.\n```{e}```"),
                ephemeral=True
            )

        await db.close()

        # Build Lineup Embed Fields
        starters_lines = []
        subs_lines = []
        for p in players_to_add:
            badge = ROLE_BADGES.get(p["role"], f"🎮 {p['role']}")
            mention_str = f" • {p['mention']}" if p["mention"] else ""
            line = f"`Slot {p['slot']}` **{badge}:** `{p['ign']}` (UID: `{p['uid']}`){mention_str}"
            if p["is_sub"]:
                subs_lines.append(line)
            else:
                starters_lines.append(line)

        # Pad missing starter slots info
        num_starters = len(starters_lines)
        if num_starters < 4:
            for s in range(num_starters + 1, 5):
                starters_lines.append(f"`Slot {s}` ⚠️ *[Empty Slot]* — Use `/team addplayer` to fill")

        if not subs_lines:
            subs_lines.append("🔄 *[No 5th Substitute]* — Use `/team addplayer is_substitute:True` to add")

        embed = base(
            "🎉 Squad Successfully Created & Registered!",
            (
                f"```fix\n"
                f"🐺 {SERVER_NAME} • OFFICIAL SQUAD ROSTER 🐺\n"
                f"```\n"
                f"Your 4-player squad (+ optional substitute) is locked in for **{tournament['name']}**!\n"
                f"When matches are created, battle dispatches will be sent to all squad members."
            ),
            color=discord.Color.from_rgb(16, 185, 129)
        )

        embed.add_field(name="🛡️ Squad", value=f"**{name}** `[{tag}]`", inline=True)
        embed.add_field(name="🆔 Team ID", value=f"`#{team_id}`", inline=True)
        embed.add_field(name="🏆 Tournament", value=f"**{tournament['name']}** (`#{tournament_id}`)", inline=True)
        embed.add_field(name="👑 Captain", value=interaction.user.mention, inline=True)
        embed.add_field(name="👥 Squad Size", value=f"`{len(players_to_add)}/5 Players`", inline=True)
        embed.add_field(
            name="🏛️ CSE Batch & Sec",
            value=f"`Batch {batch} (Sec {section})`" if batch and section else (f"`Batch {batch}`" if batch else (f"`Sec {section}`" if section else "`General`")),
            inline=True
        )
        embed.add_field(name="🐺 Hosted By", value=f"**{SERVER_NAME}**", inline=True)

        embed.add_field(
            name="⚔️ 4-Man Main Active Lineup",
            value="\n".join(starters_lines),
            inline=False
        )

        embed.add_field(
            name="🔄 5th Player (Extra Substitute)",
            value="\n".join(subs_lines),
            inline=False
        )

        if logo_url:
            embed.set_thumbnail(url=logo_url)

        embed.set_footer(text=f"🐺 {SERVER_NAME} • Free Fire Esports")

        await interaction.followup.send(embed=embed)

    # =========================================================
    # TEAM ROSTER
    # =========================================================

    @team.command(
        name="roster",
        description="Show full squad lineup, UIDs, and assigned roles"
    )
    @app_commands.describe(
        team_id="Team ID"
    )
    async def roster(
        self,
        interaction: discord.Interaction,
        team_id: int
    ):
        db = await connect()

        cur = await db.execute(
            """
            SELECT
                t.*,
                tour.name AS tournament_name
            FROM teams t
            JOIN tournaments tour ON t.tournament_id = tour.id
            WHERE t.id=?
            """,
            (team_id,)
        )
        team = await cur.fetchone()

        if not team:
            await db.close()
            return await interaction.response.send_message(
                embed=err("Team not found."),
                ephemeral=True
            )

        cur = await db.execute(
            """
            SELECT *
            FROM team_members
            WHERE team_id=?
            ORDER BY is_sub ASC, id ASC
            """,
            (team_id,)
        )
        members = await cur.fetchall()
        await db.close()

        starters = []
        subs = []

        slot_idx = 1
        for m in members:
            badge = ROLE_BADGES.get(m["role"], f"🎮 {m['role']}")
            mention_str = f" • <@{m['user_id']}>" if m["user_id"] and m["user_id"] > 0 else ""
            line = f"`Slot {slot_idx}` **{badge}:** `{m['ign']}` • UID: `{m['uid']}`{mention_str}"

            if m["is_sub"]:
                subs.append(line)
            else:
                starters.append(line)
            slot_idx += 1

        # Pad vacant slots
        if len(starters) < 4:
            for s in range(len(starters) + 1, 5):
                starters.append(f"`Slot {s}` ⚠️ *[Empty Slot]* — Fill via `/team addplayer`")

        if not subs:
            subs.append("🔄 *[Empty Sub Slot]* — Add 5th player via `/team addplayer is_substitute:True`")

        embed = base(
            f"🛡️ {team['name']} [{team['tag']}]",
            (
                f"```fix\n"
                f"🐺 {SERVER_NAME} • OFFICIAL SQUAD ROSTER 🐺\n"
                f"```\n"
                f"Official Free Fire competitive lineup for **{team['tournament_name']}**."
            )
        )

        embed.add_field(name="🏆 Tournament", value=f"**{team['tournament_name']}** (`#{team['tournament_id']}`)", inline=True)
        embed.add_field(name="👑 Captain", value=f"<@{team['captain_id']}>", inline=True)
        embed.add_field(name="🆔 Team ID", value=f"`#{team['id']}`", inline=True)
        batch_val = f"Batch {team['batch']} • Sec {team['section']}" if team['batch'] or team['section'] else "General"
        embed.add_field(name="🏛️ CSE Batch & Sec", value=f"`{batch_val}`", inline=True)

        embed.add_field(
            name=f"⚔️ 4-Man Active Lineup ({min(4, len(members) - len([m for m in members if m['is_sub']]))}/4)",
            value="\n".join(starters),
            inline=False
        )

        embed.add_field(
            name=f"🔄 5th Player (Extra Substitute) ({len([m for m in members if m['is_sub']] )}/1)",
            value="\n".join(subs),
            inline=False
        )

        if team["logo_url"]:
            embed.set_thumbnail(url=team["logo_url"])

        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Squad Roster Management"
        )

        await interaction.response.send_message(embed=embed)

    # =========================================================
    # TEAM ADD PLAYER
    # =========================================================

    @team.command(
        name="addplayer",
        description="Add a starter or 5th extra player (substitute) with role to squad"
    )
    @app_commands.describe(
        team_id="Team ID",
        ign="Player Free Fire in-game name",
        uid="Player Free Fire UID",
        role="Player's tactical role (IGL, Rusher, Sniper, Assaulter, Support, Substitute)",
        member="Optional Discord member to mention & receive DMs",
        is_substitute="Set to True if this player is the 5th extra substitute player"
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def addplayer(
        self,
        interaction: discord.Interaction,
        team_id: int,
        ign: str,
        uid: str,
        role: app_commands.Choice[str] = None,
        member: discord.Member = None,
        is_substitute: bool = False
    ):
        ign = ign.strip()
        uid = uid.strip()

        if not ign or not uid:
            return await interaction.response.send_message(
                embed=err("Player IGN and UID cannot be empty."),
                ephemeral=True
            )

        role_val = role.value if role else ("Substitute" if is_substitute else "Assaulter")
        if role_val == "Substitute":
            is_substitute = True

        db = await connect()

        cur = await db.execute("SELECT * FROM teams WHERE id=?", (team_id,))
        team = await cur.fetchone()

        if not team:
            await db.close()
            return await interaction.response.send_message(
                embed=err("Team not found."),
                ephemeral=True
            )

        if team["captain_id"] != interaction.user.id:
            await db.close()
            return await interaction.response.send_message(
                embed=err("Only the team captain can add players to this squad."),
                ephemeral=True
            )

        # Check existing member if discord member provided
        if member:
            cur = await db.execute(
                "SELECT id FROM team_members WHERE team_id=? AND user_id=?",
                (team_id, member.id)
            )
            existing = await cur.fetchone()
            if existing:
                await db.close()
                return await interaction.response.send_message(
                    embed=err(f"{member.mention} is already in this team."),
                    ephemeral=True
                )

        # Check total roster count: Maximum 5 players (4 Starters + 1 Sub)
        cur = await db.execute(
            "SELECT COUNT(*) AS count FROM team_members WHERE team_id=?",
            (team_id,)
        )
        count_row = await cur.fetchone()
        if count_row["count"] >= 5:
            await db.close()
            return await interaction.response.send_message(
                embed=err("Squad roster is completely full. Maximum **5 players** (4 Starters + 1 Substitute)."),
                ephemeral=True
            )

        # Check substitute capacity: Maximum 1 substitute
        if is_substitute:
            cur = await db.execute(
                "SELECT COUNT(*) AS sub_count FROM team_members WHERE team_id=? AND is_sub=1",
                (team_id,)
            )
            sub_count = (await cur.fetchone())["sub_count"]
            if sub_count >= 1:
                await db.close()
                return await interaction.response.send_message(
                    embed=err("This squad already has a registered 5th player (substitute). Maximum **1 substitute** allowed."),
                    ephemeral=True
                )
        else:
            # Check starters capacity: Maximum 4 starters
            cur = await db.execute(
                "SELECT COUNT(*) AS starter_count FROM team_members WHERE team_id=? AND is_sub=0",
                (team_id,)
            )
            starter_count = (await cur.fetchone())["starter_count"]
            if starter_count >= 4:
                await db.close()
                return await interaction.response.send_message(
                    embed=err(
                        "4 Main Starters are already filled! If this player is your 5th extra player, "
                        "set `is_substitute: True` or role `Substitute`."
                    ),
                    ephemeral=True
                )

        # Insert new player
        await db.execute(
            """
            INSERT INTO team_members
            (
                team_id,
                user_id,
                ign,
                uid,
                role,
                is_sub
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                team_id,
                member.id if member else 0,
                ign,
                uid,
                role_val,
                1 if is_substitute else 0
            )
        )

        await db.commit()

        # Get updated count
        cur = await db.execute(
            "SELECT COUNT(*) AS count FROM team_members WHERE team_id=?",
            (team_id,)
        )
        new_count = (await cur.fetchone())["count"]
        await db.close()

        badge = ROLE_BADGES.get(role_val, f"🎮 {role_val}")
        player_type = "🔄 5th Player (Extra Substitute)" if is_substitute else "⚔️ Active Starter"

        mention_text = f" ({member.mention})" if member else ""
        await interaction.response.send_message(
            embed=ok(
                f"🎮 Player successfully added to **{team['name']}**!\n\n"
                f"👤 IGN: `{ign}`{mention_text}\n"
                f"🆔 Free Fire UID: `{uid}`\n"
                f"🎖️ Role: **{badge}**\n"
                f"📌 Slot Type: **{player_type}**\n"
                f"👥 Total Squad Lineup: **{new_count}/5 Players**\n\n"
                f"🐺 Official Roster • **{SERVER_NAME}**"
            )
        )

    # =========================================================
    # MATCH CREATE
    # =========================================================

    @match.command(
        name="create",
        description="Create match and send OG battle dispatch DMs to all registered squads"
    )
    @app_commands.describe(
        tournament_id="Tournament ID",
        match_no="Match number",
        map_name="Map name (e.g., Bermuda, Purgatory, Kalahari)",
        scheduled_at="Scheduled time (e.g., Tonight 9:00 PM / 21:00 UTC)"
    )
    async def match_create(
        self,
        interaction: discord.Interaction,
        tournament_id: int,
        match_no: int,
        map_name: str,
        scheduled_at: str = "TBA"
    ):
        if not await require_staff(interaction):
            return

        if tournament_id < 1 or match_no < 1:
            return await interaction.response.send_message(
                embed=err(
                    "Tournament ID and Match number must be positive integers."
                ),
                ephemeral=True
            )

        map_name = map_name.strip()
        scheduled_at = scheduled_at.strip()

        # Defer interaction to provide ample time for DM dispatches and graphic generation
        await interaction.response.defer()

        db = await connect()

        try:
            # Tournament check
            cur = await db.execute(
                "SELECT id, name FROM tournaments WHERE id=?",
                (tournament_id,)
            )

            tournament = await cur.fetchone()

            if not tournament:
                await db.close()

                return await interaction.followup.send(
                    embed=err("Tournament not found."),
                    ephemeral=True
                )

            # Duplicate match check
            cur = await db.execute(
                """
                SELECT id
                FROM matches
                WHERE tournament_id=?
                AND match_no=?
                """,
                (
                    tournament_id,
                    match_no
                )
            )

            existing = await cur.fetchone()

            if existing:
                await db.close()

                return await interaction.followup.send(
                    embed=err(
                        f"Match #{match_no} already exists for tournament #{tournament_id}."
                    ),
                    ephemeral=True
                )

            cur = await db.execute(
                """
                INSERT INTO matches
                (
                    tournament_id,
                    match_no,
                    map,
                    scheduled_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    match_no,
                    map_name,
                    scheduled_at
                )
            )

            match_id = cur.lastrowid
            await db.commit()

            # Query all registered teams in this tournament
            cur = await db.execute(
                """
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id, t.logo_url
                FROM teams t
                WHERE t.tournament_id=?
                UNION
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id, t.logo_url
                FROM teams t
                JOIN registrations r ON t.id = r.team_id
                WHERE r.tournament_id=?
                """,
                (tournament_id, tournament_id)
            )
            teams = await cur.fetchall()

            # Query team members (4 Starters + 1 Sub) for each team
            team_recipients = {}
            for tm in teams:
                cur = await db.execute(
                    """
                    SELECT user_id, ign, uid, role, is_sub
                    FROM team_members
                    WHERE team_id=?
                    ORDER BY is_sub ASC, id ASC
                    """,
                    (tm["id"],)
                )
                m_rows = await cur.fetchall()
                uids = {tm["captain_id"]}
                lineup_list = []
                for mr in m_rows:
                    if mr["user_id"] and mr["user_id"] > 0:
                        uids.add(mr["user_id"])
                    lineup_list.append({
                        "user_id": mr["user_id"],
                        "ign": mr["ign"],
                        "uid": mr["uid"],
                        "role": mr["role"],
                        "is_sub": mr["is_sub"]
                    })
                team_recipients[tm["id"]] = (tm, uids, lineup_list)

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.followup.send(
                embed=err(
                    f"Failed to create match.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        # Send OG DMs to squad members
        banner_bytes = generate_match_banner(tournament["name"], match_no, map_name, scheduled_at, SERVER_NAME).getvalue()
        dms_sent = 0
        dms_failed = 0

        for t_id, (team_info, uids, lineup_list) in team_recipients.items():
            dm_embed = og_match_dm_embed(
                team_name=team_info["name"],
                team_tag=team_info["tag"],
                tournament_name=tournament["name"],
                tournament_id=tournament_id,
                match_no=match_no,
                match_id=match_id,
                map_name=map_name,
                scheduled_at=scheduled_at,
                lineup_details=lineup_list,
                server_name=SERVER_NAME
            )

            for uid in uids:
                user = interaction.guild.get_member(uid)
                if not user:
                    try:
                        user = await self.bot.fetch_user(uid)
                    except Exception:
                        user = None

                if user:
                    try:
                        await user.send(
                            content=(
                                f"⚡ **[ {SERVER_NAME} • BATTLE DISPATCH ]** ⚡\n"
                                f"⚔️ Attention Warriors of **{team_info['name']} [{team_info['tag']}]**! "
                                f"**Match #{match_no}** has been scheduled."
                            ),
                            embed=dm_embed,
                            files=[discord.File(__import__('io').BytesIO(banner_bytes), filename="match_banner.png"),
                                   discord.File(room_pass(team_info['name'], tournament['name'], match_no, map_name), filename="vip_pass.png")]
                        )
                        dms_sent += 1
                    except discord.Forbidden:
                        dms_failed += 1
                    except Exception:
                        dms_failed += 1

        # Generate custom match banner
        banner_buf = generate_match_banner(
            tournament_name=tournament["name"],
            match_no=match_no,
            map_name=map_name,
            scheduled_at=scheduled_at,
            server_name=SERVER_NAME
        )
        match_file = discord.File(banner_buf, filename="match_banner.png")

        embed = discord.Embed(
            title=f"🎮 MATCH #{match_no} CREATED & OG DMs DISPATCHED!",
            description=(
                f"```fix\n"
                f"🐺 {SERVER_NAME} • MATCH NOTICE 🐺\n"
                f"```\n"
                f"Match **#{match_no}** has been successfully created for **{tournament['name']}**.\n"
                f"Official OG Battle Notifications with 4+1 roster details have been dispatched to registered squads!"
            ),
            color=discord.Color.from_rgb(16, 185, 129),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="attachment://match_banner.png")
        embed.add_field(name="🏆 Tournament", value=f"**{tournament['name']}** (`#{tournament_id}`)", inline=True)
        embed.add_field(name="🆔 Match ID", value=f"`#{match_id}`", inline=True)
        embed.add_field(name="🎮 Round", value=f"**Match #{match_no}**", inline=True)
        embed.add_field(name="🗺️ Battleground", value=f"**{map_name}**", inline=True)
        embed.add_field(name="⏰ Schedule", value=f"**{scheduled_at}**", inline=True)
        embed.add_field(name="🐺 Host Server", value=f"**{SERVER_NAME}**", inline=True)
        embed.add_field(
            name="📨 OG Squad DMs Dispatched",
            value=(
                f"👥 Registered Squads: **{len(teams)}**\n"
                f"✅ DMs Sent: **{dms_sent}**"
                + (f"\n⚠️ DMs Closed/Failed: **{dms_failed}**" if dms_failed > 0 else "")
            ),
            inline=False
        )
        embed.set_footer(text=f"🐺 {SERVER_NAME} • Esports Management")

        await interaction.followup.send(
            embed=embed,
            file=match_file
        )

    # =========================================================
    # MATCH ROOM
    # =========================================================

    @match.command(
        name="room",
        description="Release room credentials and DM captains with OG access pass"
    )
    @app_commands.describe(
        match_id="Match ID",
        room_id="Free Fire room ID",
        password="Room password"
    )
    async def room(
        self,
        interaction: discord.Interaction,
        match_id: int,
        room_id: str,
        password: str
    ):
        if not await require_staff(interaction):
            return

        room_id = room_id.strip()
        password = password.strip()

        if not room_id or not password:
            return await interaction.response.send_message(
                embed=err("Room ID and password cannot be empty."),
                ephemeral=True
            )

        await interaction.response.defer()

        db = await connect()

        try:
            cur = await db.execute(
                """
                SELECT
                    m.id,
                    m.match_no,
                    m.map,
                    m.tournament_id,
                    t.name AS tournament_name
                FROM matches m
                JOIN tournaments t ON m.tournament_id = t.id
                WHERE m.id=?
                """,
                (match_id,)
            )

            match = await cur.fetchone()

            if not match:
                await db.close()

                return await interaction.followup.send(
                    embed=err("Match not found."),
                    ephemeral=True
                )

            await db.execute(
                """
                UPDATE matches
                SET
                    room_id=?,
                    room_password=?,
                    status='room_open'
                WHERE id=?
                """,
                (
                    room_id,
                    password,
                    match_id
                )
            )

            cur = await db.execute(
                """
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id
                FROM teams t
                WHERE t.tournament_id=?
                UNION
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id
                FROM teams t
                JOIN registrations r ON t.id = r.team_id
                WHERE r.tournament_id=?
                """,
                (match["tournament_id"], match["tournament_id"])
            )

            teams = await cur.fetchall()

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.followup.send(
                embed=err(
                    f"Failed to release room.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        sent = 0
        failed = 0

        for tm in teams:
            member = interaction.guild.get_member(tm["captain_id"])
            if not member:
                try:
                    member = await self.bot.fetch_user(tm["captain_id"])
                except Exception:
                    member = None

            if member:
                dm_embed = og_room_dm_embed(
                    team_name=tm["name"],
                    team_tag=tm["tag"],
                    tournament_name=match["tournament_name"],
                    match_no=match["match_no"],
                    match_id=match_id,
                    room_id=room_id,
                    password=password,
                    map_name=match["map"] or "Battlefield",
                    server_name=SERVER_NAME
                )

                try:
                    await member.send(
                        content=(
                            f"🚨 **[ {SERVER_NAME} • ROOM PASS ]** 🚨\n"
                            f"Squad **{tm['name']} [{tm['tag']}]**, custom room credentials released!"
                        ),
                        embed=dm_embed,
                        files=[discord.File(generate_match_banner(match['tournament_name'], match['match_no'], match['map'] or 'TBA', 'ROOM OPEN', SERVER_NAME), filename="match_banner.png"),
                               discord.File(room_pass(tm['name'], match['tournament_name'], match['match_no'], match['map'] or 'TBA'), filename="vip_pass.png")]
                    )
                    sent += 1
                except discord.Forbidden:
                    failed += 1
                except Exception:
                    failed += 1

        embed = base(
            "🎮 ROOM CREDENTIALS RELEASED!",
            (
                f"```diff\n"
                f"+ ROOM ACCESS LIVE • MATCH #{match['match_no']} +\n"
                f"```\n"
                f"Custom room credentials have been dispatched to captains via OG DM."
            ),
            color=discord.Color.from_rgb(16, 185, 129)
        )
        embed.add_field(name="🏆 Tournament", value=f"**{match['tournament_name']}**", inline=True)
        embed.add_field(name="🎮 Match Round", value=f"**Match #{match['match_no']}**", inline=True)
        embed.add_field(name="🗺️ Map", value=f"**{match['map'] or 'TBA'}**", inline=True)
        embed.add_field(name="🔐 Access", value="Credentials sent privately to captains.", inline=False)
        embed.add_field(name="🐺 Host", value=f"**{SERVER_NAME}**", inline=True)
        embed.add_field(
            name="📨 Delivery Report",
            value=(
                f"👑 Captains Reached: **{sent}** / **{len(teams)}**"
                + (f"\n⚠️ DMs Closed: **{failed}**" if failed > 0 else "")
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed)

    @match.command(name="streamstop", description="Staff: end a live stream while retaining its replay link")
    async def streamstop(self, interaction: discord.Interaction, match_id: int):
        if not await require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        row = await stream_status(match_id, stop=True)
        if not row:
            return await interaction.followup.send(embed=err("Match not found."), ephemeral=True)
        await audit(interaction.user.id, "stream_stop", str(match_id))
        await interaction.followup.send(embed=ok("Stream marked offline. Replay link retained."), ephemeral=True)

    @match.command(name="streamstatus", description="View a match's live status or replay link")
    async def streamstatus(self, interaction: discord.Interaction, match_id: int):
        await interaction.response.defer()
        row = await stream_status(match_id)
        if not row:
            return await interaction.followup.send(embed=err("Match not found."), ephemeral=True)
        embed = base(f"Match #{row['match_no']} • {'LIVE' if row['stream_live'] else 'OFFLINE'}",
                     row['tournament_name'])
        view = discord.ui.View()
        if row['stream_url']:
            try:
                url = validate_stream_url(row['stream_url'])
                view.add_item(discord.ui.Button(label="Watch Live" if row['stream_live'] else "Watch Replay",
                                                url=url))
            except ValueError:
                pass
        await interaction.followup.send(embed=embed, view=view)

    # =========================================================
    # MATCH LIVE STREAM BROADCAST
    # =========================================================

    @match.command(
        name="stream",
        description="Go live! Broadcast a stream link, generate an HD card, and DM all registered squads"
    )
    @app_commands.describe(
        match_id="Match ID",
        stream_url="Live stream URL (YouTube / Facebook / Twitch)",
        platform="Streaming platform name (e.g. YouTube, Facebook, Twitch)"
    )
    async def stream(
        self,
        interaction: discord.Interaction,
        match_id: int,
        stream_url: str,
        platform: str = "YouTube"
    ):
        if not await require_staff(interaction):
            return

        stream_url = stream_url.strip()
        platform = platform.strip() or "YouTube"

        try:
            stream_url = validate_stream_url(stream_url)
        except ValueError as exc:
            return await interaction.response.send_message(embed=err(str(exc)), ephemeral=True)
        if len(platform) > 40:
            return await interaction.response.send_message(embed=err("Platform must be 40 characters or fewer."), ephemeral=True)

        await interaction.response.defer()

        db = await connect()

        try:
            cur = await db.execute(
                """
                SELECT
                    m.id,
                    m.match_no,
                    m.map,
                    m.tournament_id,
                    t.name AS tournament_name
                FROM matches m
                JOIN tournaments t ON m.tournament_id = t.id
                WHERE m.id=?
                """,
                (match_id,)
            )

            match = await cur.fetchone()

            if not match:
                await db.close()

                return await interaction.followup.send(
                    embed=err("Match not found."),
                    ephemeral=True
                )

            await db.execute(
                """
                UPDATE matches
                SET
                    stream_url=?,
                    stream_platform=?,
                    stream_live=1
                WHERE id=?
                """,
                (
                    stream_url,
                    platform,
                    match_id
                )
            )

            cur = await db.execute(
                """
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id
                FROM teams t
                WHERE t.tournament_id=?
                UNION
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id
                FROM teams t
                JOIN registrations r ON t.id = r.team_id
                WHERE r.tournament_id=?
                """,
                (match["tournament_id"], match["tournament_id"])
            )

            teams = await cur.fetchall()

            # Collect all squad members too (not just captains) for the broadcast
            team_recipients = {}
            for tm in teams:
                cur = await db.execute(
                    "SELECT user_id FROM team_members WHERE team_id=?",
                    (tm["id"],)
                )
                m_rows = await cur.fetchall()
                uids = {tm["captain_id"]}
                for mr in m_rows:
                    if mr["user_id"] and mr["user_id"] > 0:
                        uids.add(mr["user_id"])
                team_recipients[tm["id"]] = (tm, uids)

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.followup.send(
                embed=err(
                    f"Failed to start live broadcast.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        map_name = match["map"] or "TBA"

        # Generate the HD (1280x720) LIVE NOW broadcast card
        broadcast_card_bytes = live_broadcast(
            match["tournament_name"],
            match["match_no"],
            map_name,
            platform
        ).getvalue()

        sent = 0
        failed = 0

        for t_id, (team_info, uids) in team_recipients.items():
            dm_embed = stream_live_dm_embed(
                team_name=team_info["name"],
                team_tag=team_info["tag"],
                tournament_name=match["tournament_name"],
                match_no=match["match_no"],
                match_id=match_id,
                map_name=map_name,
                platform=platform,
                stream_url=stream_url,
                server_name=SERVER_NAME
            )

            for uid in uids:
                user = interaction.guild.get_member(uid)
                if not user:
                    try:
                        user = await self.bot.fetch_user(uid)
                    except Exception:
                        user = None

                if user:
                    try:
                        await user.send(
                            content=(
                                f"🔴 **[ {SERVER_NAME} • WE ARE LIVE ]** 🔴\n"
                                f"📡 **{team_info['name']} [{team_info['tag']}]**, Match #{match['match_no']} is streaming now!"
                            ),
                            embed=dm_embed,
                            files=[discord.File(io.BytesIO(broadcast_card_bytes), filename="live_broadcast.png")],
                            view=stream_link_view(stream_url, platform)
                        )
                        sent += 1
                    except discord.Forbidden:
                        failed += 1
                    except Exception:
                        failed += 1

        broadcast_file = discord.File(
            io.BytesIO(broadcast_card_bytes),
            filename="live_broadcast.png"
        )

        embed = discord.Embed(
            title=f"🔴 LIVE NOW — MATCH #{match['match_no']} IS STREAMING!",
            description=(
                f"```diff\n"
                f"+ 🐺 {SERVER_NAME} • LIVE BROADCAST ACTIVE +\n"
                f"```\n"
                f"**{match['tournament_name']}** — Match **#{match['match_no']}** is now LIVE on **{platform}**!\n"
                f"🔗 **[Watch the stream here]({stream_url})**"
            ),
            color=discord.Color.from_rgb(239, 68, 68),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="attachment://live_broadcast.png")
        embed.add_field(name="🏆 Tournament", value=f"**{match['tournament_name']}**", inline=True)
        embed.add_field(name="🎮 Match Round", value=f"**Match #{match['match_no']}**", inline=True)
        embed.add_field(name="🗺️ Map", value=f"**{map_name}**", inline=True)
        embed.add_field(name="📡 Platform", value=f"**{platform}**", inline=True)
        embed.add_field(name="🐺 Host", value=f"**{SERVER_NAME}**", inline=True)
        embed.add_field(
            name="📨 Broadcast Notification Report",
            value=(
                f"👥 Registered Squads: **{len(teams)}**\n"
                f"✅ DMs Sent: **{sent}**"
                + (f"\n⚠️ DMs Closed/Failed: **{failed}**" if failed > 0 else "")
            ),
            inline=False
        )
        embed.set_footer(text=f"🐺 {SERVER_NAME} • Live Broadcast Center")

        # Prefer the server's configured announcement channel. If it is unset,
        # deleted, or inaccessible, post where the command was invoked.
        target_channel = interaction.channel
        configured_channel_id = await get_setting("notification_channel_id")
        if configured_channel_id and interaction.guild:
            try:
                target_channel = interaction.guild.get_channel(int(configured_channel_id))
                if target_channel is None:
                    target_channel = await interaction.guild.fetch_channel(int(configured_channel_id))
            except (ValueError, discord.HTTPException, discord.Forbidden):
                target_channel = interaction.channel

        view = stream_link_view(stream_url, platform)
        if target_channel and target_channel.id != interaction.channel_id:
            await target_channel.send(embed=embed, file=broadcast_file, view=view)
            await interaction.followup.send(
                embed=ok(
                    f"Live broadcast posted in {target_channel.mention}. "
                    f"Sent **{sent}** member DM(s); **{failed}** failed."
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=embed,
                file=broadcast_file,
                view=view
            )

    # =========================================================
    # RESULT SUBMIT
    # =========================================================

    @result.command(
        name="submit",
        description="Submit team match result"
    )
    @app_commands.describe(
        match_id="Match ID",
        team_id="Team ID",
        placement="Final placement",
        kills="Total kills"
    )
    async def submit(
        self,
        interaction: discord.Interaction,
        match_id: int,
        team_id: int,
        placement: int,
        kills: int
    ):
        if placement < 1:
            return await interaction.response.send_message(
                embed=err("Placement must be at least **1**."),
                ephemeral=True
            )

        if kills < 0:
            return await interaction.response.send_message(
                embed=err("Kills cannot be negative."),
                ephemeral=True
            )

        db = await connect()

        cur = await db.execute(
            """
            SELECT
                id,
                captain_id,
                name,
                tournament_id
            FROM teams
            WHERE id=?
            """,
            (team_id,)
        )

        team = await cur.fetchone()

        if not team:
            await db.close()

            return await interaction.response.send_message(
                embed=err("Team not found."),
                ephemeral=True
            )

        if team["captain_id"] != interaction.user.id:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "Only the team captain can submit this result."
                ),
                ephemeral=True
            )

        # Check match
        cur = await db.execute(
            """
            SELECT *
            FROM matches
            WHERE id=?
            """,
            (match_id,)
        )

        match = await cur.fetchone()

        if not match:
            await db.close()

            return await interaction.response.send_message(
                embed=err("Match not found."),
                ephemeral=True
            )

        if match["tournament_id"] != team["tournament_id"]:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "This team does not belong to the tournament of this match."
                ),
                ephemeral=True
            )

        pp, kp, total = calculate(
            placement,
            kills
        )

        try:
            await db.execute(
                """
                INSERT INTO results
                (
                    match_id,
                    team_id,
                    placement,
                    kills,
                    placement_points,
                    kill_points,
                    total_points,
                    submitted_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    team_id,
                    placement,
                    kills,
                    pp,
                    kp,
                    total,
                    interaction.user.id
                )
            )

            await db.commit()

        except Exception:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "Result already submitted for this team/match."
                ),
                ephemeral=True
            )

        await db.close()

        await interaction.response.send_message(
            embed=ok(
                f"📊 **Result Submitted Successfully!**\n\n"
                f"👥 Squad: **{team['name']}**\n"
                f"🏁 Placement: **#{placement}**\n"
                f"🔫 Kills: **{kills}**\n"
                f"🏆 Placement Points: **{pp}**\n"
                f"🎯 Kill Points: **{kp}**\n"
                f"💎 Total Points: **{total} PTS**\n\n"
                f"⏳ Verification pending by **{SERVER_NAME}** staff."
            )
        )

    # =========================================================
    # RESULT VERIFY
    # =========================================================

    @result.command(
        name="verify",
        description="Verify submitted result"
    )
    @app_commands.describe(
        result_id="Result ID"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        result_id: int
    ):
        if not await require_staff(interaction):
            return

        db = await connect()

        cur = await db.execute(
            """
            SELECT *
            FROM results
            WHERE id=?
            """,
            (result_id,)
        )

        result = await cur.fetchone()

        if not result:
            await db.close()

            return await interaction.response.send_message(
                embed=err("Result not found."),
                ephemeral=True
            )

        if result["verified"]:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "This result has already been verified."
                ),
                ephemeral=True
            )

        await db.execute(
            """
            UPDATE results
            SET verified=1
            WHERE id=?
            """,
            (result_id,)
        )

        await db.commit()
        await db.close()

        await interaction.response.send_message(
            embed=ok(
                f"✅ Result **#{result_id}** verified.\n"
                f"Points are now updated on the official **{SERVER_NAME}** leaderboard."
            )
        )

    # =========================================================
    # LEADERBOARD
    # =========================================================

    @result.command(
        name="leaderboard",
        description="Show verified tournament leaderboard"
    )
    @app_commands.describe(
        tournament_id="Tournament ID"
    )
    async def lb(
        self,
        interaction: discord.Interaction,
        tournament_id: int
    ):
        if tournament_id < 1:
            return await interaction.response.send_message(
                embed=err("Invalid tournament ID."),
                ephemeral=True
            )

        rows = await leaderboard(
            tournament_id
        )

        embed = base(
            f"🏆 {SERVER_NAME} • LIVE LEADERBOARD",
            "Official verified tournament standings."
        )

        if not rows:
            embed.description = "No verified results recorded yet."
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for index, row in enumerate(rows, 1):
                medal = medals.get(index, f"`#{index:02d}`")
                embed.add_field(
                    name=f"{medal} {row['name']} [{row['tag']}]",
                    value=(
                        f"💎 **{row['pts']} PTS** • "
                        f"🔫 **{row['kills']} Kills** • "
                        f"🎮 **{row['matches']} Matches**"
                    ),
                    inline=False
                )

        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Verified Leaderboard"
        )

        await interaction.response.send_message(
            embed=embed
        )


    @tournament.command(
        name="fixtures",
        description="Show tournament match fixtures & 5-map rotation schedule"
    )
    @app_commands.describe(
        tournament_id="Tournament ID"
    )
    async def fixtures(
        self,
        interaction: discord.Interaction,
        tournament_id: int
    ):
        if tournament_id < 1:
            return await interaction.response.send_message(
                embed=err("Invalid tournament ID."),
                ephemeral=True
            )

        db = await connect()
        try:
            cur = await db.execute("SELECT * FROM tournaments WHERE id=?", (tournament_id,))
            tourn = await cur.fetchone()

            if not tourn:
                await db.close()
                return await interaction.response.send_message(
                    embed=err("Tournament not found."),
                    ephemeral=True
                )

            cur = await db.execute(
                """
                SELECT *
                FROM matches
                WHERE tournament_id=?
                ORDER BY match_no ASC
                """,
                (tournament_id,)
            )
            scheduled_matches = await cur.fetchall()

            cur = await db.execute(
                """
                SELECT COUNT(DISTINCT team_id) AS c
                FROM (
                    SELECT id AS team_id FROM teams WHERE tournament_id=?
                    UNION
                    SELECT team_id FROM registrations WHERE tournament_id=?
                )
                """,
                (tournament_id, tournament_id)
            )
            reg_count = (await cur.fetchone())["c"]
        finally:
            await db.close()

        embed = discord.Embed(
            title=f"🗓️ {tourn['name']} • MATCH FIXTURES & MAP ROTATION",
            description=(
                f"```fix\n"
                f"🐺 Root LU • OFFICIAL COMPETITIVE SCHEDULE 🐺\n"
                f"```\n"
                f"Official match schedule & 5-map Battle Royale rotation for **{tourn['name']}**.\n"
                f"👥 Registered Squads: **{reg_count}/{tourn['max_teams']}** | 📌 Status: **{str(tourn['status']).upper()}**"
            ),
            color=discord.Color.from_rgb(59, 130, 246),
            timestamp=discord.utils.utcnow()
        )

        # 1. Official 5-Map Rotation
        rotation_lines = []
        for m_no, map_name, emoji, desc in OFFICIAL_5_MAP_ROTATION:
            rotation_lines.append(f"`Match {m_no}` {emoji} **{map_name}:** *{desc}*")
        embed.add_field(
            name="🗺️ Official 5-Map Rotation Schedule",
            value="\n".join(rotation_lines),
            inline=False
        )

        # 2. Scheduled Matches
        if scheduled_matches:
            match_lines = []
            for m in scheduled_matches:
                status_badge = "⏳ Scheduled"
                if m["status"] == "room_open":
                    status_badge = "🔴 ROOM LIVE"
                elif m["status"] == "completed":
                    status_badge = "🟢 Completed"

                map_display = m["map"] or f"Map #{m['match_no']}"
                stream_line = ""
                try:
                    if m["stream_live"]:
                        platform = m["stream_platform"] or "Stream"
                        stream_line = f"\n▸ 📡 **LIVE NOW on {platform}:** [Watch here]({m['stream_url']})"
                except (IndexError, KeyError):
                    pass

                match_lines.append(
                    f"🎮 **Match #{m['match_no']}** (ID: `#{m['id']}`)\n"
                    f"▸ 🗺️ Map: **{map_display}** • ⏰ Drop Time: `{m['scheduled_at']}`\n"
                    f"▸ 📊 Status: **{status_badge}**{stream_line}"
                )
            embed.add_field(
                name=f"⚔️ Scheduled Matches ({len(scheduled_matches)})",
                value="\n\n".join(match_lines[:10]),
                inline=False
            )
        else:
            embed.add_field(
                name="⚔️ Scheduled Matches",
                value="⚠️ *No matches scheduled in database yet. Staff can publish matches with `/match create`.*",
                inline=False
            )

        # 3. Match Day Rules
        embed.add_field(
            name="📜 Match Day Protocols",
            value=(
                "▸ ⏱️ **Lobby Assembly:** Be in Discord voice/standby lobby **15 minutes** before scheduled match.\n"
                "▸ 🔑 **Credentials Delivery:** Room ID & Password dispatched to Captain DMs via `/match room`.\n"
                "▸ 📸 **Result Proof:** Captains must screenshot scoreboard and submit with `/result submit`."
            ),
            inline=False
        )

        embed.set_footer(text="🐺 Root LU • Leading University Tournament Center")
        await interaction.response.send_message(embed=embed)

    @result.command(
        name="topfraggers",
        description="Show tournament top-kill fraggers & MVP leaderboard"
    )
    @app_commands.describe(
        tournament_id="Tournament ID (optional, leave 0 for all/active tournament)",
        limit="Number of top fraggers to display (default: 10, max: 25)"
    )
    async def topfraggers(
        self,
        interaction: discord.Interaction,
        tournament_id: int = 0,
        limit: int = 10
    ):
        if tournament_id < 0:
            return await interaction.response.send_message(
                embed=err("Tournament ID must be a non-negative number."),
                ephemeral=True
            )

        limit = max(1, min(25, limit))
        await interaction.response.defer()

        tourn_name = "Overall Championship"
        if tournament_id > 0:
            db = await connect()
            cur = await db.execute("SELECT name FROM tournaments WHERE id=?", (tournament_id,))
            t = await cur.fetchone()
            await db.close()
            if not t:
                return await interaction.followup.send(
                    embed=err(f"Tournament `#{tournament_id}` not found."),
                    ephemeral=True
                )
            tourn_name = t["name"]

        fraggers = await top_fraggers(tournament_id, limit)

        embed = discord.Embed(
            title="🔥 Root LU • TOURNAMENT TOP FRAGGERS (KILL LEADERBOARD)",
            description=(
                f"```fix\n"
                f"👑 MOST LETHAL PLAYERS • {tourn_name.upper()} 👑\n"
                f"```\n"
                f"Official ranking of highest individual kill performers across verified matches."
            ),
            color=discord.Color.from_rgb(239, 68, 68),
            timestamp=discord.utils.utcnow()
        )

        if not fraggers or (len(fraggers) == 1 and fraggers[0]["kills"] == 0):
            embed.description += "\n\n⚠️ *No verified kills or match results recorded yet.*"
        else:
            medals = {1: "👑", 2: "🥈", 3: "🥉"}
            total_kills_sum = 0
            for idx, f in enumerate(fraggers, start=1):
                total_kills_sum += f["kills"]
                medal = medals.get(idx, f"`#{idx:02d}`")
                role_badge = ROLE_BADGES.get(f.get("role"), f"🎮 {f.get('role', 'Player')}")
                batch_info = f" • CSE {f['batch']}-{f['section']}" if f.get("batch") and f.get("section") else ""

                if idx == 1:
                    title_line = f"{medal} **TOP FRAGGER / MVP: `{f['ign']}`** `[{f['team_tag']}]`"
                    val_line = (
                        f"💀 **{f['kills']} KILLS** • 🎖️ **{role_badge}**\n"
                        f"🛡️ Squad: **{f['team_name']}**{batch_info} • 🎮 Matches: **{f['matches']}**"
                    )
                else:
                    title_line = f"{medal} `{f['ign']}` `[{f['team_tag']}]`"
                    val_line = (
                        f"🔫 **{f['kills']} Kills** • {role_badge} • **{f['team_name']}**{batch_info}"
                    )
                embed.add_field(name=title_line, value=val_line, inline=False)

            embed.add_field(
                name="📊 Fragger Statistics",
                value=f"🔥 Top Fraggers Tracked: **{len(fraggers)}** | 💀 Combined Kills: **{total_kills_sum}**",
                inline=False
            )

        embed.set_footer(text="🐺 Root LU • Free Fire Esports Statistics")
        await interaction.followup.send(embed=embed)

    @section.command(
        name="leaderboard",
        description="Show CSE Batch & Section points table and rankings"
    )
    @app_commands.describe(
        tournament_id="Tournament ID (optional, leave 0 for all/active tournament)"
    )
    async def section_leaderboard_cmd(
        self,
        interaction: discord.Interaction,
        tournament_id: int = 0
    ):
        if tournament_id < 0:
            return await interaction.response.send_message(
                embed=err("Tournament ID must be a non-negative number."),
                ephemeral=True
            )

        await interaction.response.defer()

        tourn_name = "Overall Championship"
        if tournament_id > 0:
            db = await connect()
            cur = await db.execute("SELECT name FROM tournaments WHERE id=?", (tournament_id,))
            t = await cur.fetchone()
            await db.close()
            if not t:
                return await interaction.followup.send(
                    embed=err(f"Tournament `#{tournament_id}` not found."),
                    ephemeral=True
                )
            tourn_name = t["name"]

        sections = await section_leaderboard(tournament_id)

        embed = discord.Embed(
            title="🏆 Root LU • CSE BATCH & SECTION LEADERBOARD",
            description=(
                f"```fix\n"
                f"🏛️ LEADING UNIVERSITY • CSE ESPORTS STANDINGS 🏛️\n"
                f"```\n"
                f"Official section points and standings for **{tourn_name}**."
            ),
            color=discord.Color.from_rgb(124, 58, 237),
            timestamp=discord.utils.utcnow()
        )

        if not sections:
            embed.description += "\n\n⚠️ *No verified match results recorded for CSE sections yet.*"
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for idx, sec in enumerate(sections, start=1):
                medal = medals.get(idx, f"`#{idx:02d}`")
                batch_str = f"Batch {sec['batch']}" if sec['batch'].lower() != 'general' and sec['batch'].lower() != 'unassigned' else "General Batch"
                sec_str = f"Section {sec['section']}" if sec['section'].lower() != 'open' and sec['section'].lower() != 'general' else "Open Section"
                title_line = f"{medal} **{batch_str} — {sec_str}**"

                value_line = (
                    f"💎 **{sec['pts']} PTS** • 🔫 **{sec['kills']} Kills** • 👥 **{sec['teams_count']} Squads** • 🎮 **{sec['matches']} Matches**\n"
                    f"👑 Top Squad: **{sec['top_team_name']}** `[{sec['top_team_tag']}]` ({sec['top_team_pts']} PTS)"
                )
                embed.add_field(name=title_line, value=value_line, inline=False)

        embed.set_footer(text="🐺 Root LU • Leading University CSE Free Fire League")
        await interaction.followup.send(embed=embed)

    @student.command(
        name="verify",
        description="Verify official Leading University Student ID"
    )
    @app_commands.describe(
        student_id="Official Leading University Student ID (e.g., 2012020123)",
        name="Full Name (as per Student ID)",
        batch="CSE Batch (e.g., 60, 59, 58)",
        section="Section (e.g., A, B, C, D)",
        department="Department (default: CSE)"
    )
    async def student_verify_cmd(
        self,
        interaction: discord.Interaction,
        student_id: str,
        name: str,
        batch: str,
        section: str,
        department: str = "CSE"
    ):
        student_id = student_id.strip()
        name = name.strip()
        batch = batch.strip()
        section = section.strip().upper()
        department = department.strip().upper() if department else "CSE"

        if len(student_id) < 3:
            return await interaction.response.send_message(
                embed=err("Please enter a valid Student ID."),
                ephemeral=True
            )

        if len(name) < 2:
            return await interaction.response.send_message(
                embed=err("Please enter your full name."),
                ephemeral=True
            )

        if not batch or not section:
            return await interaction.response.send_message(
                embed=err("Batch and Section are required for verification."),
                ephemeral=True
            )

        db = await connect()
        try:
            # Check if user already verified
            cur = await db.execute(
                "SELECT * FROM student_verifications WHERE user_id=?",
                (interaction.user.id,)
            )
            existing_user = await cur.fetchone()
            if existing_user:
                await db.close()
                return await interaction.response.send_message(
                    embed=base(
                        "🎓 Already Verified",
                        (
                            f"You are already verified as a Leading University student!\n\n"
                            f"👤 **Name:** {existing_user['full_name']}\n"
                            f"🆔 **Student ID:** `{existing_user['student_id']}`\n"
                            f"🏛️ **Department:** {existing_user['department']}\n"
                            f"📚 **Batch & Section:** Batch {existing_user['batch']} (Sec {existing_user['section']})\n"
                            f"🛡️ **Status:** 🟢 **VERIFIED**"
                        ),
                        color=discord.Color.from_rgb(16, 185, 129)
                    ),
                    ephemeral=True
                )

            # Check if student ID already registered by someone else
            cur = await db.execute(
                "SELECT * FROM student_verifications WHERE student_id=?",
                (student_id,)
            )
            existing_id = await cur.fetchone()
            if existing_id:
                await db.close()
                return await interaction.response.send_message(
                    embed=err(
                        f"Student ID `{student_id}` is already registered to another Discord account.\n"
                        "If you believe this is an error, please contact staff via `/ticket`."
                    ),
                    ephemeral=True
                )

            # Insert verification
            await db.execute(
                """
                INSERT INTO student_verifications
                (user_id, student_id, full_name, department, batch, section, status)
                VALUES (?, ?, ?, ?, ?, ?, 'verified')
                """,
                (interaction.user.id, student_id, name, department, batch, section)
            )
            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()
            return await interaction.response.send_message(
                embed=err(f"Verification failed.\n```{e}```"),
                ephemeral=True
            )

        await db.close()

        await audit(interaction.user.id, "student_verify", f"{student_id}:{department}-{batch}-{section}")

        # Attempt to assign verified student role if present
        if interaction.guild:
            for r_name in ("Verified Student", "Student", "Root LU", "Verified"):
                role = discord.utils.get(interaction.guild.roles, name=r_name)
                if role:
                    try:
                        await interaction.user.add_roles(role, reason="Student ID verified")
                        break
                    except Exception:
                        pass

        embed = discord.Embed(
            title="🎓 Root LU • STUDENT VERIFICATION SUCCESSFUL",
            description=(
                f"```fix\n"
                f"🏛️ LEADING UNIVERSITY • ROOT LU VERIFIED 🏛️\n"
                f"```\n"
                f"Congratulations {interaction.user.mention}! Your Leading University student identity has been verified."
            ),
            color=discord.Color.from_rgb(16, 185, 129),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="👤 Student Name", value=f"**{name}**", inline=True)
        embed.add_field(name="🆔 Student ID", value=f"`{student_id}`", inline=True)
        embed.add_field(name="🏛️ Department", value=f"`{department}`", inline=True)
        embed.add_field(name="📚 Batch & Section", value=f"**Batch {batch} (Sec {section})**", inline=True)
        embed.add_field(name="🛡️ Status", value="🟢 **VERIFIED STUDENT**", inline=True)
        embed.add_field(name="🐺 Community", value="**Root LU • Leading University**", inline=True)
        embed.set_footer(text="🐺 Root LU • Official Student Verification System")

        await interaction.response.send_message(embed=embed)

    @student.command(
        name="profile",
        description="View student verification profile"
    )
    @app_commands.describe(
        member="Discord member to check (defaults to yourself)"
    )
    async def student_profile_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        target = member or interaction.user
        db = await connect()
        cur = await db.execute("SELECT * FROM student_verifications WHERE user_id=?", (target.id,))
        v = await cur.fetchone()

        # Query target's teams
        cur = await db.execute(
            """
            SELECT t.id, t.name, t.tag, t.batch, t.section, tour.name AS tour_name
            FROM teams t
            JOIN tournaments tour ON tour.id = t.tournament_id
            WHERE t.captain_id = ?
            UNION
            SELECT t.id, t.name, t.tag, t.batch, t.section, tour.name AS tour_name
            FROM team_members tm
            JOIN teams t ON t.id = tm.team_id
            JOIN tournaments tour ON tour.id = t.tournament_id
            WHERE tm.user_id = ?
            """,
            (target.id, target.id)
        )
        teams = await cur.fetchall()
        await db.close()

        if not v:
            return await interaction.response.send_message(
                embed=err(
                    f"{target.mention} is not verified yet.\n"
                    f"Use `/student verify` to verify your Leading University Student ID."
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"🎓 Student Profile • {v['full_name']}",
            description=f"Official verified student profile on **Root LU**.",
            color=discord.Color.from_rgb(59, 130, 246),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Full Name", value=f"**{v['full_name']}**", inline=True)
        embed.add_field(name="🆔 Student ID", value=f"`{v['student_id']}`", inline=True)
        embed.add_field(name="🏛️ Department", value=f"`{v['department']}`", inline=True)
        embed.add_field(name="📚 Batch & Section", value=f"**Batch {v['batch']} (Sec {v['section']})**", inline=True)
        embed.add_field(name="🛡️ Verification Status", value="🟢 **VERIFIED**", inline=True)
        embed.add_field(name="📅 Verified At", value=f"`{v['created_at'][:10]}`", inline=True)

        if teams:
            team_lines = [f"• **{tm['name']}** `[{tm['tag']}]` ({tm['tour_name']})" for tm in teams[:5]]
            embed.add_field(name="🎮 Esports Teams", value="\n".join(team_lines), inline=False)

        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="🐺 Root LU • Leading University")
        await interaction.response.send_message(embed=embed)


    @tournament.command(name="slots", description="Show registered lobby slots")
    async def slots(self, interaction: discord.Interaction, tournament_id: int, page: int = 1, graphical: bool = False):
        if page < 1 or tournament_id < 1:
            return await interaction.response.send_message(embed=err("Invalid tournament or page."), ephemeral=True)
        await interaction.response.defer()
        db = await connect()
        try:
            cur = await db.execute("SELECT name, max_teams FROM tournaments WHERE id=?", (tournament_id,))
            tournament = await cur.fetchone()
            if not tournament:
                return await interaction.followup.send(embed=err("Tournament not found."), ephemeral=True)
            cur = await db.execute("""SELECT DISTINCT id, name, tag FROM teams WHERE tournament_id=?
                UNION SELECT DISTINCT t.id, t.name, t.tag FROM teams t
                JOIN registrations r ON r.team_id=t.id WHERE r.tournament_id=? ORDER BY id""",
                (tournament_id, tournament_id))
            teams = await cur.fetchall()
        finally:
            await db.close()
        if graphical:
            try:
                image = await asyncio.to_thread(slot_grid, tournament["name"], teams, tournament["max_teams"], page)
            except ValueError as exc:
                return await interaction.followup.send(embed=err(str(exc)), ephemeral=True)
            return await interaction.followup.send(file=discord.File(image, filename="slot-grid.png"))
        start = (page - 1) * 40 + 1
        end = min(page * 40, tournament["max_teams"])
        if start > tournament["max_teams"]:
            return await interaction.followup.send(embed=err("Page has no slots."), ephemeral=True)
        lines = [f"`{i:02d}` {teams[i-1]['name']} [{teams[i-1]['tag']}]" if i <= len(teams) else f"`{i:02d}` — OPEN —" for i in range(start, end + 1)]
        embed = base(f"Lobby Slots • {tournament['name']}", "\n".join(lines)[:3900] or "No slots available.")
        await interaction.followup.send(embed=embed)

    @tournament.command(name="rules", description="Show tournament rulebook")
    async def rules(self, interaction: discord.Interaction):
        embed = base("Tournament Rulebook", "1. Register one squad per tournament; use your registered roster.\n"
                     "2. Join before the scheduled start; follow host announcements.\n"
                     "3. No cheats, exploits, teaming or abusive behavior.\n"
                     "4. Submit accurate results; only verified results count.\n"
                     "5. Staff resolve disputes; provide evidence when reporting.")
        await interaction.response.send_message(embed=embed)

    @result.command(name="table", description="Generate a 1200x880 verified points table")
    async def table(self, interaction: discord.Interaction, tournament_id: int, page: int = 1):
        if page < 1 or tournament_id < 1:
            return await interaction.response.send_message(embed=err("Invalid tournament or page."), ephemeral=True)
        await interaction.response.defer()
        db = await connect()
        try:
            cur = await db.execute("SELECT name FROM tournaments WHERE id=?", (tournament_id,))
            tournament = await cur.fetchone()
        finally:
            await db.close()
        if not tournament:
            return await interaction.followup.send(embed=err("Tournament not found."), ephemeral=True)
        rows = await leaderboard(tournament_id)
        if not rows:
            return await interaction.followup.send(embed=err("No teams registered."), ephemeral=True)
        if (page - 1) * 12 >= len(rows):
            return await interaction.followup.send(embed=err("Page has no teams."), ephemeral=True)
        await interaction.followup.send(file=discord.File(points_table(tournament['name'], rows[(page-1)*12:page*12], page), filename="points_table.png"))

    @result.command(name="booyah", description="Generate a golden winner card from verified standings")
    async def winner_card(self, interaction: discord.Interaction, tournament_id: int):
        if tournament_id < 1:
            return await interaction.response.send_message(embed=err("Invalid tournament ID."), ephemeral=True)
        await interaction.response.defer()
        db = await connect()
        try:
            cur = await db.execute("SELECT name FROM tournaments WHERE id=?", (tournament_id,))
            tournament = await cur.fetchone()
        finally:
            await db.close()
        if not tournament:
            return await interaction.followup.send(embed=err("Tournament not found."), ephemeral=True)
        rows = await leaderboard(tournament_id)
        ranked = [r for r in rows if r['matches'] > 0]
        if not ranked:
            return await interaction.followup.send(embed=err("No verified results yet."), ephemeral=True)
        top = ranked[0]
        await interaction.followup.send(file=discord.File(booyah(top['name'], tournament['name'], top['pts']), filename="booyah.png"))

    @result.command(name="mvp", description="Generate a cyberpunk MVP card from verified kills")
    async def mvp_card(self, interaction: discord.Interaction, tournament_id: int):
        if tournament_id < 1:
            return await interaction.response.send_message(embed=err("Invalid tournament ID."), ephemeral=True)
        await interaction.response.defer()
        db = await connect()
        try:
            cur = await db.execute("""SELECT tm.ign, t.name AS team, SUM(r.kills) AS kills
                FROM results r JOIN matches m ON m.id=r.match_id
                JOIN teams t ON t.id=r.team_id
                JOIN team_members tm ON tm.team_id=t.id AND tm.is_sub=0
                WHERE m.tournament_id=? AND r.verified=1
                GROUP BY tm.id ORDER BY kills DESC, tm.ign ASC LIMIT 1""", (tournament_id,))
            player = await cur.fetchone()
        finally:
            await db.close()
        if not player:
            return await interaction.followup.send(embed=err("No verified results yet."), ephemeral=True)
        # Results track team kills, not individual kills; label the value accordingly.
        await interaction.followup.send(file=discord.File(mvp(player['ign'], player['team'], player['kills']), filename="mvp.png"),
                                        content="Featured player from the top-kill team; individual kills are not tracked.")


# =============================================================
# SETUP
# =============================================================

async def setup(bot):
    await bot.add_cog(
        Esports(bot)
    )
