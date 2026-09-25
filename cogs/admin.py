import discord
from discord.ext import commands
from discord import app_commands

from config import SERVER_NAME
from database.db import connect, audit
from utils.embeds import base, ok, err
from utils.permissions import require_staff


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Esports administration")

    @admin.command(name="dashboard", description="Show live admin dashboard")
    async def dashboard(self, interaction: discord.Interaction):
        if not await require_staff(interaction):
            return

        db = await connect()
        stats = {}
        for table in ("tournaments", "teams", "matches", "results", "payments", "reports", "tickets"):
            cur = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
            stats[table] = (await cur.fetchone())["c"]
        await db.close()

        e = base(
            f"🛡️ {SERVER_NAME} • ADMIN COMMAND CENTER",
            "Live esports database & tournament operations overview.",
            color=discord.Color.from_rgb(124, 58, 237)
        )
        for k, v in stats.items():
            e.add_field(name=k.title(), value=f"`{v}`", inline=True)

        e.add_field(
            name="⚡ Quick Actions",
            value=(
                "• `/tournament create` - Publish tournament with dynamic banner\n"
                "• `/match create` - Schedule match & blast OG squad DMs\n"
                "• `/match room` - Release custom room credentials\n"
                "• `/result verify` - Verify submitted squad match score\n"
                "• `/admin payment` - Approve/reject registration payments"
            ),
            inline=False
        )
        e.set_footer(text=f"🐺 {SERVER_NAME} • Elite Operations")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @admin.command(name="payment", description="Approve or reject team registration payment")
    @app_commands.describe(
        payment_id="Payment ID",
        decision="approve or reject"
    )
    async def payment(self, interaction: discord.Interaction, payment_id: int, decision: str):
        if not await require_staff(interaction):
            return

        decision = decision.lower().strip()
        if decision not in ("approve", "reject"):
            return await interaction.response.send_message(
                embed=err("Decision must be either `approve` or `reject`."),
                ephemeral=True
            )

        status_val = "approved" if decision == "approve" else "rejected"
        db = await connect()
        cur = await db.execute(
            "UPDATE payments SET status=? WHERE id=?",
            (status_val, payment_id)
        )
        await db.commit()
        await db.close()

        if not cur.rowcount:
            return await interaction.response.send_message(
                embed=err("Payment ID not found."),
                ephemeral=True
            )

        await audit(interaction.user.id, "payment_review", f"{payment_id}:{decision}")
        await interaction.response.send_message(
            embed=ok(f"Payment **#{payment_id}** set to **{decision.upper()}**.")
        )

    @admin.command(name="close", description="Close tournament registration")
    @app_commands.describe(tournament_id="Tournament ID")
    async def close(self, interaction: discord.Interaction, tournament_id: int):
        if not await require_staff(interaction):
            return

        db = await connect()
        cur = await db.execute("UPDATE tournaments SET status='closed' WHERE id=?", (tournament_id,))
        await db.commit()
        await db.close()

        if not cur.rowcount:
            return await interaction.response.send_message(
                embed=err("Tournament not found."),
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=ok(f"🏆 Tournament **#{tournament_id}** is now **CLOSED**.")
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
