"""Security & integrity scanning slash commands."""
import discord
from discord import app_commands
from discord.ext import commands

from config import SERVER_NAME, DEVELOPER
from database.db import audit
from services.security import run_security_scan, recent_scans
from utils.embeds import base
from utils.permissions import require_staff


class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    security = app_commands.Group(
        name="security",
        description="Server security & integrity scanning"
    )

    @security.command(
        name="scan",
        description="Staff: run a full security & integrity scan of the tournament database"
    )
    @app_commands.describe(scope="Scan scope label (default: full)")
    async def security_scan(
        self,
        interaction: discord.Interaction,
        scope: str = "full"
    ):
        if not await require_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        scope = (scope or "full").strip()[:40] or "full"
        summary = await run_security_scan(interaction.user.id, scope)

        await audit(
            interaction.user.id,
            "security_scan",
            f"{scope}:{summary['findings_count']} findings"
        )

        if summary["findings_count"] == 0:
            embed = base(
                "🛡️ SECURITY SCAN COMPLETE — ALL CLEAR",
                f"Scope: `{summary['scope']}` • Scanned at `{summary['scanned_at']}` UTC\n\n"
                "✅ No integrity issues detected.",
                color=discord.Color.from_rgb(16, 185, 129)
            )
        else:
            embed = base(
                f"🛡️ SECURITY SCAN — {summary['findings_count']} FINDING(S)",
                f"Scope: `{summary['scope']}` • Scanned at `{summary['scanned_at']}` UTC",
                color=discord.Color.from_rgb(245, 158, 11)
            )
            findings_text = "\n".join(summary["findings"][:15])
            embed.add_field(
                name="🔍 Findings",
                value=findings_text[:1024],
                inline=False
            )
            if summary["findings_count"] > 15:
                embed.add_field(
                    name="…",
                    value=f"+{summary['findings_count'] - 15} more findings.",
                    inline=False
                )

        embed.add_field(
            name="🔎 Checks performed",
            value=(
                "▸ Incomplete 4-man squad rosters\n"
                "▸ Duplicate Free Fire UIDs across accounts\n"
                "▸ Duplicate squad names per tournament\n"
                "▸ Unverified squad captains\n"
                "▸ Negative coin balances\n"
                "▸ Open dispute reports\n"
                "▸ Stale open match rooms"
            ),
            inline=False
        )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Security Center • Developed by {DEVELOPER}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @security.command(
        name="history",
        description="Staff: view recent security scan reports"
    )
    async def security_history(self, interaction: discord.Interaction):
        if not await require_staff(interaction):
            return

        scans = await recent_scans(10)
        embed = base(
            "🛡️ SECURITY SCAN HISTORY",
            "Most recent integrity scans.",
            color=discord.Color.from_rgb(59, 130, 246)
        )
        if not scans:
            embed.description += "\n\n⚠️ *No scans recorded yet — run `/security scan`.*"
        else:
            lines = [
                f"`#{s['id']}` `{s['scope']}` — **{s['findings_count']}** finding(s) "
                f"by <@{s['scanner_id']}> at `{s['created_at']}` UTC"
                for s in scans
            ]
            embed.add_field(
                name="📜 Recent Scans",
                value="\n".join(lines)[:1024],
                inline=False
            )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Security Center • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Security(bot))
