import discord
from discord.ext import commands
from discord import app_commands

from database.db import connect, audit
from services.scoring import calculate
from services.leaderboard import leaderboard
from utils.embeds import base, ok, err
from utils.permissions import require_staff
from views.panels import TournamentPanel


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

    # =========================================================
    # TOURNAMENT CREATE
    # =========================================================

    @tournament.command(
        name="create",
        description="Create and publish a tournament panel"
    )
    @app_commands.describe(
        name="Tournament name",
        max_teams="Maximum number of teams",
        entry_fee="Entry fee",
        prize_pool="Prize pool",
        description="Tournament description"
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        max_teams: int,
        entry_fee: float = 0.0,
        prize_pool: float = 0.0,
        description: str = "Official FF esports tournament."
    ):
        if not await require_staff(interaction):
            return

        # Validation
        name = name.strip()
        description = description.strip()

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
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    max_teams,
                    entry_fee,
                    prize_pool,
                    interaction.user.id
                )
            )

            tournament_id = cur.lastrowid

            await db.commit()

        except Exception as e:
            await db.rollback()

            return await interaction.response.send_message(
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

        embed = base(
            "🔥 " + name,
            description
        )

        embed.add_field(
            name="🏆 Tournament ID",
            value=f"`{tournament_id}`",
            inline=True
        )

        embed.add_field(
            name="👥 Slots",
            value=f"`{max_teams}` Teams",
            inline=True
        )

        embed.add_field(
            name="💳 Entry",
            value=f"৳{entry_fee:g}",
            inline=True
        )

        embed.add_field(
            name="💰 Prize Pool",
            value=f"৳{prize_pool:g}",
            inline=True
        )

        embed.add_field(
            name="📌 Status",
            value="🟢 OPEN",
            inline=True
        )

        embed.add_field(
            name="👤 Created By",
            value=interaction.user.mention,
            inline=True
        )

        embed.set_footer(
            text="FF Esports Management • Tournament System"
        )

        await interaction.response.send_message(
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
                    embed=err("This tournament is already closed."),
                    ephemeral=True
                )

            await db.execute(
                """
                UPDATE tournaments
                SET status='closed'
                WHERE id=?
                """,
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

        await interaction.response.send_message(
            embed=ok(
                f"🏆 Tournament **#{tournament_id} — {tournament['name']}**\n"
                f"Registration has been **closed**."
            )
        )

    # =========================================================
    # TOURNAMENT LIST
    # =========================================================

    @tournament.command(
        name="list",
        description="List tournaments"
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
                    "🏆 Tournament Hub",
                    "No tournaments have been created yet."
                )
            )

        embed = base(
            "🏆 Tournament Hub",
            "Latest FF Esports tournaments"
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
                    f"👥 Slots: **{row['max_teams']}**\n"
                    f"💳 Entry: **৳{row['entry_fee']:g}**\n"
                    f"💰 Prize: **৳{row['prize_pool']:g}**"
                ),
                inline=False
            )

        embed.set_footer(
            text="FF Esports Management"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # TEAM CREATE
    # =========================================================

    @team.command(
        name="create",
        description="Create a tournament team"
    )
    @app_commands.describe(
        tournament_id="Tournament ID",
        name="Team name",
        tag="Team tag",
        ign="Captain in-game name",
        uid="Captain Free Fire UID",
        logo_url="Optional team logo URL"
    )
    async def team_create(
        self,
        interaction: discord.Interaction,
        tournament_id: int,
        name: str,
        tag: str,
        ign: str,
        uid: str,
        logo_url: str = ""
    ):
        name = name.strip()
        tag = tag.strip().upper()
        ign = ign.strip()
        uid = uid.strip()
        logo_url = logo_url.strip()

        if tournament_id < 1:
            return await interaction.response.send_message(
                embed=err("Invalid tournament ID."),
                ephemeral=True
            )

        if not name or not tag or not ign or not uid:
            return await interaction.response.send_message(
                embed=err(
                    "Team name, tag, IGN and UID are required."
                ),
                ephemeral=True
            )

        if len(tag) > 10:
            return await interaction.response.send_message(
                embed=err("Team tag must be 10 characters or less."),
                ephemeral=True
            )

        db = await connect()

        try:
            # Check tournament
            cur = await db.execute(
                """
                SELECT *
                FROM tournaments
                WHERE id=?
                """,
                (tournament_id,)
            )

            tournament = await cur.fetchone()

            if not tournament:
                await db.close()

                return await interaction.response.send_message(
                    embed=err("Tournament not found."),
                    ephemeral=True
                )

            if tournament["status"] != "open":
                await db.close()

                return await interaction.response.send_message(
                    embed=err(
                        "Registration for this tournament is closed."
                    ),
                    ephemeral=True
                )

            # Check existing team by captain
            cur = await db.execute(
                """
                SELECT id
                FROM teams
                WHERE tournament_id=?
                AND captain_id=?
                """,
                (
                    tournament_id,
                    interaction.user.id
                )
            )

            existing = await cur.fetchone()

            if existing:
                await db.close()

                return await interaction.response.send_message(
                    embed=err(
                        f"You already created team **#{existing['id']}** "
                        f"for this tournament."
                    ),
                    ephemeral=True
                )

            # Check team count
            cur = await db.execute(
                """
                SELECT COUNT(*) AS count
                FROM teams
                WHERE tournament_id=?
                """,
                (tournament_id,)
            )

            count_row = await cur.fetchone()
            team_count = count_row["count"]

            if team_count >= tournament["max_teams"]:
                await db.close()

                return await interaction.response.send_message(
                    embed=err(
                        "This tournament is already full."
                    ),
                    ephemeral=True
                )

            # Create team
            cur = await db.execute(
                """
                INSERT INTO teams
                (
                    tournament_id,
                    name,
                    tag,
                    captain_id,
                    logo_url
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    name,
                    tag,
                    interaction.user.id,
                    logo_url
                )
            )

            team_id = cur.lastrowid

            # Add captain
            await db.execute(
                """
                INSERT INTO team_members
                (
                    team_id,
                    user_id,
                    ign,
                    uid,
                    role
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    interaction.user.id,
                    ign,
                    uid,
                    "Captain"
                )
            )

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    f"Failed to create team.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        embed = ok(
            f"🎉 Team successfully created!\n\n"
            f"🏆 Tournament: **{tournament['name']}**\n"
            f"👥 Team: **{name} [{tag}]**\n"
            f"🆔 Team ID: **{team_id}**\n"
            f"👑 Captain: {interaction.user.mention}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # TEAM ROSTER
    # =========================================================

    @team.command(
        name="roster",
        description="Show team roster"
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
                tm.user_id,
                tm.ign,
                tm.uid,
                tm.role
            FROM teams t
            LEFT JOIN team_members tm
                ON tm.team_id=t.id
            WHERE t.id=?
            """,
            (team_id,)
        )

        rows = await cur.fetchall()
        await db.close()

        if not rows:
            return await interaction.response.send_message(
                embed=err("Team not found."),
                ephemeral=True
            )

        team = rows[0]

        embed = base(
            f"👥 {team['name']} [{team['tag']}]",
            "Team roster"
        )

        embed.add_field(
            name="🏆 Tournament ID",
            value=f"`{team['tournament_id']}`",
            inline=True
        )

        embed.add_field(
            name="👑 Captain",
            value=f"<@{team['captain_id']}>",
            inline=True
        )

        players = []

        for row in rows:
            if row["user_id"]:
                players.append(
                    f"<@{row['user_id']}> • "
                    f"`{row['ign']}` • "
                    f"`{row['uid']}` • "
                    f"**{row['role']}**"
                )

        embed.add_field(
            name=f"🎮 Players ({len(players)})",
            value="\n".join(players) if players else "No players",
            inline=False
        )

        if team["logo_url"]:
            embed.set_thumbnail(
                url=team["logo_url"]
            )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # TEAM ADD PLAYER
    # =========================================================

    @team.command(
        name="addplayer",
        description="Add player to team"
    )
    @app_commands.describe(
        team_id="Team ID",
        member="Discord member",
        ign="Player in-game name",
        uid="Player Free Fire UID"
    )
    async def addplayer(
        self,
        interaction: discord.Interaction,
        team_id: int,
        member: discord.Member,
        ign: str,
        uid: str
    ):
        ign = ign.strip()
        uid = uid.strip()

        db = await connect()

        cur = await db.execute(
            """
            SELECT *
            FROM teams
            WHERE id=?
            AND captain_id=?
            """,
            (
                team_id,
                interaction.user.id
            )
        )

        team = await cur.fetchone()

        if not team:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "Only the team captain can add players."
                ),
                ephemeral=True
            )

        # Check if already in team
        cur = await db.execute(
            """
            SELECT id
            FROM team_members
            WHERE team_id=?
            AND user_id=?
            """,
            (
                team_id,
                member.id
            )
        )

        existing = await cur.fetchone()

        if existing:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    f"{member.mention} is already in this team."
                ),
                ephemeral=True
            )

        # Maximum roster size
        cur = await db.execute(
            """
            SELECT COUNT(*) AS count
            FROM team_members
            WHERE team_id=?
            """,
            (team_id,)
        )

        count_row = await cur.fetchone()

        if count_row["count"] >= 4:
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    "Team roster is full. Maximum **4 players**."
                ),
                ephemeral=True
            )

        await db.execute(
            """
            INSERT INTO team_members
            (
                team_id,
                user_id,
                ign,
                uid,
                role
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                team_id,
                member.id,
                ign,
                uid,
                "Player"
            )
        )

        await db.commit()
        await db.close()

        await interaction.response.send_message(
            embed=ok(
                f"🎮 {member.mention} added to "
                f"**{team['name']}**.\n\n"
                f"IGN: `{ign}`\n"
                f"UID: `{uid}`"
            )
        )

    # =========================================================
    # MATCH CREATE
    # =========================================================

    @match.command(
        name="create",
        description="Create match"
    )
    @app_commands.describe(
        tournament_id="Tournament ID",
        match_no="Match number",
        map_name="Map name",
        scheduled_at="Scheduled time"
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
                    "Tournament ID and Match number must be positive."
                ),
                ephemeral=True
            )

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

                return await interaction.response.send_message(
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

                return await interaction.response.send_message(
                    embed=err(
                        f"Match #{match_no} already exists."
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

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    f"Failed to create match.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        await interaction.response.send_message(
            embed=ok(
                f"🎮 Match **#{match_no}** created.\n\n"
                f"🏆 Tournament: **{tournament['name']}**\n"
                f"🆔 Match ID: `{match_id}`\n"
                f"🗺️ Map: **{map_name}**\n"
                f"⏰ Schedule: **{scheduled_at}**"
            )
        )

    # =========================================================
    # MATCH ROOM
    # =========================================================

    @match.command(
        name="room",
        description="Release room details and DM captains"
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

        db = await connect()

        try:
            cur = await db.execute(
                """
                SELECT
                    m.id,
                    m.match_no,
                    m.tournament_id
                FROM matches m
                WHERE m.id=?
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
                SELECT DISTINCT captain_id
                FROM teams
                WHERE tournament_id=?
                """,
                (match["tournament_id"],)
            )

            captains = await cur.fetchall()

            await db.commit()

        except Exception as e:
            await db.rollback()
            await db.close()

            return await interaction.response.send_message(
                embed=err(
                    f"Failed to release room.\n```{e}```"
                ),
                ephemeral=True
            )

        await db.close()

        sent = 0

        for captain in captains:

            member = interaction.guild.get_member(
                captain["captain_id"]
            )

            if member:

                try:
                    await member.send(
                        f"🎮 **ROOM RELEASED**\n\n"
                        f"🏆 Match: **#{match['match_no']}**\n"
                        f"🆔 Match ID: `{match_id}`\n"
                        f"🔑 Room ID: `{room_id}`\n"
                        f"🔐 Password: `{password}`"
                    )

                    sent += 1

                except discord.Forbidden:
                    pass

        await interaction.response.send_message(
            embed=ok(
                f"🎮 Room released successfully.\n\n"
                f"🆔 Match: `{match_id}`\n"
                f"📨 Captain DMs sent: **{sent}**"
            )
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
                    "This team does not belong to the tournament "
                    "of this match."
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
                f"📊 Result submitted successfully!\n\n"
                f"👥 Team: **{team['name']}**\n"
                f"🏁 Placement: **#{placement}**\n"
                f"🔫 Kills: **{kills}**\n"
                f"🏆 Placement Points: **{pp}**\n"
                f"🎯 Kill Points: **{kp}**\n"
                f"💎 Total: **{total} PTS**\n\n"
                f"⏳ Awaiting admin verification."
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
                f"The result is now included in the leaderboard."
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
            "🏆 LIVE LEADERBOARD",
            "Verified results only."
        )

        if not rows:
            embed.description = (
                "No verified results yet."
            )

        else:

            for index, row in enumerate(rows, 1):

                embed.add_field(
                    name=(
                        f"{index}. "
                        f"{row['name']} "
                        f"[{row['tag']}]"
                    ),
                    value=(
                        f"💎 **{row['pts']} PTS**\n"
                        f"🔫 {row['kills']} Kills\n"
                        f"🎮 {row['matches']} Matches"
                    ),
                    inline=False
                )

        embed.set_footer(
            text="FF Esports • Verified Leaderboard"
        )

        await interaction.response.send_message(
            embed=embed
        )


# =============================================================
# SETUP
# =============================================================

async def setup(bot):
    await bot.add_cog(
        Esports(bot)
    )