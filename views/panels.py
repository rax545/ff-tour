import discord
from config import SERVER_NAME
from database.db import connect
from utils.embeds import base, ok, err


class RegistrationModal(discord.ui.Modal, title="Squad Tournament Registration"):
    team_id_input = discord.ui.TextInput(
        label="Enter Your Team ID",
        placeholder="Example: 1 (Use /team create to get your Team ID)",
        required=True,
        max_length=10
    )

    def __init__(self, view_ref):
        super().__init__()
        self.view_ref = view_ref

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.team_id_input.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                embed=err("Invalid Team ID. Please enter numbers only (e.g., `1`, `12`)."),
                ephemeral=True
            )
        await self.view_ref.register(interaction, val)


class TournamentPanel(discord.ui.View):
    def __init__(self, tournament_id: int):
        super().__init__(timeout=None)
        self.tournament_id = tournament_id

    @discord.ui.button(
        label="🏆 Register Squad",
        style=discord.ButtonStyle.success,
        custom_id="ff:register"
    )
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RegistrationModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="📋 Tournament Info",
        style=discord.ButtonStyle.primary,
        custom_id="ff:info"
    )
    async def info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = await connect()
        try:
            cur = await db.execute("SELECT * FROM tournaments WHERE id=?", (self.tournament_id,))
            t = await cur.fetchone()

            cur = await db.execute(
                """
                SELECT COUNT(DISTINCT team_id) AS c
                FROM (
                    SELECT id AS team_id FROM teams WHERE tournament_id=?
                    UNION
                    SELECT team_id FROM registrations WHERE tournament_id=?
                )
                """,
                (self.tournament_id, self.tournament_id)
            )
            count_row = await cur.fetchone()
            reg_count = count_row["c"] if count_row else 0
        finally:
            await db.close()

        if not t:
            return await interaction.response.send_message(
                embed=err("Tournament not found."),
                ephemeral=True
            )

        max_t = t["max_teams"] or 12
        pct = min(1.0, max(0.0, reg_count / max_t))
        filled_bars = int(pct * 10)
        progress = "█" * filled_bars + "░" * (10 - filled_bars)

        embed = base(
            f"🏆 {t['name']}",
            t["description"] or "Official competitive Free Fire tournament hosted by **" + SERVER_NAME + "**.",
            color=discord.Color.from_rgb(124, 58, 237)
        )
        embed.add_field(name="🆔 Tournament ID", value=f"`#{self.tournament_id}`", inline=True)
        embed.add_field(name="🎮 Game Mode", value="`Squad Battle Royale`", inline=True)
        embed.add_field(name="📌 Status", value=f"**{str(t['status']).upper()}**", inline=True)
        embed.add_field(name="💳 Entry Fee", value=f"৳{t['entry_fee']:g}" if t["entry_fee"] > 0 else "FREE", inline=True)
        embed.add_field(name="💰 Prize Pool", value=f"৳{t['prize_pool']:g}", inline=True)
        embed.add_field(name="👥 Filled Slots", value=f"`[{progress}]` {reg_count}/{max_t} Squads", inline=True)
        embed.add_field(
            name="🐺 Hosted By",
            value=f"**{SERVER_NAME}**",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="⚔️ Registered Squads",
        style=discord.ButtonStyle.secondary,
        custom_id="ff:squads"
    )
    async def squads_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = await connect()
        try:
            cur = await db.execute(
                """
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id,
                       (SELECT COUNT(*) FROM team_members WHERE team_id=t.id) AS m_count
                FROM teams t
                WHERE t.tournament_id=?
                UNION
                SELECT DISTINCT t.id, t.name, t.tag, t.captain_id,
                       (SELECT COUNT(*) FROM team_members WHERE team_id=t.id) AS m_count
                FROM teams t
                JOIN registrations r ON t.id = r.team_id
                WHERE r.tournament_id=?
                ORDER BY id ASC
                """,
                (self.tournament_id, self.tournament_id)
            )
            teams = await cur.fetchall()
        finally:
            await db.close()

        if not teams:
            return await interaction.response.send_message(
                embed=base(
                    "⚔️ Registered Squads",
                    "No squads have registered for this tournament yet.\nClick **Register Squad** to claim the first slot!",
                    color=discord.Color.from_rgb(59, 130, 246)
                ),
                ephemeral=True
            )

        team_lines = []
        for i, team in enumerate(teams, start=1):
            count_str = f"`{team['m_count']}/5 Players`" if team["m_count"] else "`Lineup Pending`"
            team_lines.append(
                f"`#{i:02d}` **{team['name']}** `[{team['tag']}]` • {count_str} • Captain: <@{team['captain_id']}>"
            )

        embed = base(
            f"⚔️ Registered Squads ({len(teams)})",
            "\n".join(team_lines[:25]),
            color=discord.Color.from_rgb(59, 130, 246)
        )
        if len(team_lines) > 25:
            embed.set_footer(text=f"Showing 25 of {len(team_lines)} squads • {SERVER_NAME}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def register(self, interaction: discord.Interaction, team_id: int):
        db = await connect()
        try:
            cur = await db.execute("SELECT * FROM tournaments WHERE id=?", (self.tournament_id,))
            t = await cur.fetchone()

            cur = await db.execute(
                "SELECT * FROM teams WHERE id=? AND captain_id=?",
                (team_id, interaction.user.id)
            )
            team = await cur.fetchone()

            if not t or not team:
                await db.close()
                return await interaction.response.send_message(
                    embed=err(
                        "Tournament or team not found, or you are not the captain of this team.\n"
                        "Use `/team create` first if you haven't created your team yet!"
                    ),
                    ephemeral=True
                )

            if t["status"] != "open":
                await db.close()
                return await interaction.response.send_message(
                    embed=err("Registration for this tournament is currently **closed**."),
                    ephemeral=True
                )

            cur = await db.execute(
                """
                SELECT COUNT(DISTINCT team_id) AS c
                FROM (
                    SELECT id AS team_id FROM teams WHERE tournament_id=?
                    UNION
                    SELECT team_id FROM registrations WHERE tournament_id=?
                )
                """,
                (self.tournament_id, self.tournament_id)
            )
            count = (await cur.fetchone())["c"]

            if count >= t["max_teams"]:
                await db.close()
                return await interaction.response.send_message(
                    embed=err("This tournament is full! No more slots available."),
                    ephemeral=True
                )

            # Insert registration
            await db.execute(
                "INSERT INTO registrations(tournament_id, team_id, status) VALUES(?, ?, 'registered')",
                (self.tournament_id, team_id)
            )
            # Ensure team.tournament_id is consistent
            await db.execute(
                "UPDATE teams SET tournament_id=? WHERE id=?",
                (self.tournament_id, team_id)
            )
            await db.commit()

        except Exception:
            await db.close()
            return await interaction.response.send_message(
                embed=err(f"Team **{team['name']}** is already registered for this tournament."),
                ephemeral=True
            )

        await db.close()

        success_embed = ok(
            f"🎉 **Registration Confirmed!**\n\n"
            f"🛡️ Squad: **{team['name']}** `[{team['tag']}]`\n"
            f"🏆 Tournament: **{t['name']}** (ID: `#{self.tournament_id}`)\n"
            f"👑 Captain: {interaction.user.mention}\n\n"
            f"🐺 **{SERVER_NAME}** esports staff will dispatch match announcements & room access directly to your DM!"
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)
