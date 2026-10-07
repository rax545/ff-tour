"""Root LU coin economy & WANTED bounty board slash commands."""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import SERVER_NAME, DEVELOPER
from database.db import audit
from services.economy import (
    EconomyError,
    MIN_BOUNTY,
    get_balance,
    claim_daily,
    tip,
    coin_leaderboard,
    place_bounty,
    bounty_board,
    claim_bounty,
    cancel_bounty,
)
from utils.banner import generate_bounty_poster
from utils.embeds import base, ok, err
from utils.permissions import staff


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    coin = app_commands.Group(
        name="coin",
        description="Root LU coin economy — balance, daily rewards, tips & leaderboard"
    )

    bounty = app_commands.Group(
        name="bounty",
        description="WANTED bounty board — place bounties, hunt targets, claim rewards"
    )

    # =========================================================
    # /coin balance
    # =========================================================

    @coin.command(
        name="balance",
        description="Check your (or another member's) coin balance"
    )
    @app_commands.describe(member="Member to check (defaults to yourself)")
    async def coin_balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        target = member or interaction.user
        balance = await get_balance(target.id)
        embed = base(
            "💰 COIN BALANCE",
            f"{target.mention} has **{balance}** coins.",
            color=discord.Color.from_rgb(245, 158, 11)
        )
        embed.add_field(
            name="💡 Earn more",
            value=(
                "▸ `/coin daily` — claim your daily reward\n"
                "▸ `/match predict` — stake coins on matches\n"
                "▸ `/bounty claim` — hunt wanted targets"
            ),
            inline=False
        )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Coin Economy • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /coin daily
    # =========================================================

    @coin.command(
        name="daily",
        description="Claim your daily coin reward"
    )
    async def coin_daily(self, interaction: discord.Interaction):
        try:
            reward, next_available = await claim_daily(interaction.user.id)
        except EconomyError as exc:
            return await interaction.response.send_message(
                embed=err(str(exc)),
                ephemeral=True
            )

        ts = int(next_available.timestamp())
        embed = ok(
            f"🪙 Daily reward claimed!\n\n"
            f"You received **+{reward}** coins.\n"
            f"💰 New balance: **{await get_balance(interaction.user.id)}** coins\n"
            f"⏰ Next claim <t:{ts}:R>"
        )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Coin Economy • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /coin tip
    # =========================================================

    @coin.command(
        name="tip",
        description="Tip another member some of your coins"
    )
    @app_commands.describe(
        member="Member to tip",
        amount="Amount of coins to tip"
    )
    async def coin_tip(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int
    ):
        if amount < 1:
            return await interaction.response.send_message(
                embed=err("Tip amount must be at least **1** coin."),
                ephemeral=True
            )

        try:
            await tip(interaction.user.id, member.id, amount)
        except EconomyError as exc:
            return await interaction.response.send_message(
                embed=err(str(exc)),
                ephemeral=True
            )

        embed = ok(
            f"💸 Tip sent!\n\n"
            f"{interaction.user.mention} tipped **{amount}** coins to {member.mention}.\n"
            f"💰 Your balance: **{await get_balance(interaction.user.id)}** coins"
        )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Coin Economy • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /coin leaderboard
    # =========================================================

    @coin.command(
        name="leaderboard",
        description="Show the top coin holders"
    )
    async def coin_leaderboard_cmd(self, interaction: discord.Interaction):
        rows = await coin_leaderboard(10)

        embed = base(
            "🤑 ROOT LU • COIN LEADERBOARD",
            "Top coin holders in the server.",
            color=discord.Color.from_rgb(245, 158, 11)
        )
        if not rows:
            embed.description += "\n\n⚠️ *Nobody has earned coins yet — use `/coin daily`!*"
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for idx, row in enumerate(rows, 1):
                medal = medals.get(idx, f"`#{idx:02d}`")
                embed.add_field(
                    name=f"{medal} <@{row['user_id']}>",
                    value=f"💰 **{row['balance']}** coins • earned {row['earned']}",
                    inline=False
                )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Coin Economy • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /bounty place
    # =========================================================

    @bounty.command(
        name="place",
        description="Place a bounty on a player — locks coins and posts a WANTED poster"
    )
    @app_commands.describe(
        target="The player to put a bounty on",
        amount=f"Bounty amount in coins (minimum {MIN_BOUNTY})",
        reason="Optional reason for the bounty"
    )
    async def bounty_place(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        amount: int,
        reason: str = ""
    ):
        if amount < 1:
            return await interaction.response.send_message(
                embed=err("Bounty amount must be positive."),
                ephemeral=True
            )

        await interaction.response.defer()

        try:
            bounty_id = await place_bounty(
                interaction.user.id,
                target.id,
                amount,
                reason
            )
        except EconomyError as exc:
            return await interaction.followup.send(
                embed=err(str(exc)),
                ephemeral=True
            )

        await audit(
            interaction.user.id,
            "bounty_place",
            f"#{bounty_id}:{target.id}:{amount}"
        )

        poster = await asyncio.to_thread(
            generate_bounty_poster,
            target.display_name,
            amount,
            interaction.user.display_name,
            reason,
            SERVER_NAME
        )

        embed = base(
            "🚨 WANTED — BOUNTY PLACED",
            (
                f"A bounty of **{amount}** coins has been placed on {target.mention}!\n"
                f"Bounty ID: `#{bounty_id}`\n\n"
                f"Eliminate them in a verified match and claim the reward with `/bounty claim`."
            ),
            color=discord.Color.from_rgb(239, 68, 68)
        )
        embed.set_image(url="attachment://bounty_poster.png")
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Bounty Board • Developed by {DEVELOPER}"
        )
        await interaction.followup.send(
            embed=embed,
            file=discord.File(poster, filename="bounty_poster.png")
        )

    # =========================================================
    # /bounty board
    # =========================================================

    @bounty.command(
        name="board",
        description="Bounty board rules & active targets"
    )
    async def bounty_board_cmd(self, interaction: discord.Interaction):
        rows = await bounty_board("active", 20)

        embed = base(
            "🚨 ROOT LU • BOUNTY BOARD",
            (
                "**Rules:**\n"
                f"▸ `/bounty place` locks **{MIN_BOUNTY}**+ coins on a target's head\n"
                "▸ When the target's squad is **eliminated** (placement > #1) in a verified match, "
                "any hunter can `/bounty claim` with that match ID\n"
                "▸ The hunter receives the full locked amount\n"
                "▸ Winning the match voids the hunt — the bounty survives\n"
                "▸ The placer (or staff) can `/bounty cancel` for a full refund"
            ),
            color=discord.Color.from_rgb(239, 68, 68)
        )

        if not rows:
            embed.add_field(
                name="🎯 Active Targets",
                value="*No active bounties. Place one with `/bounty place`!*",
                inline=False
            )
        else:
            lines = [
                f"`#{b['id']}` {b['amount']} coins on <@{b['target_id']}> "
                f"— placed by <@{b['placer_id']}>"
                + (f"\n   📝 {b['reason']}" if b["reason"] else "")
                for b in rows
            ]
            embed.add_field(
                name=f"🎯 Active Targets ({len(rows)})",
                value="\n".join(lines)[:1024],
                inline=False
            )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Bounty Board • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /bounty claim
    # =========================================================

    @bounty.command(
        name="claim",
        description="Claim a bounty — provide the verified match where the target was eliminated"
    )
    @app_commands.describe(
        bounty_id="Bounty ID (from /bounty board)",
        match_id="Verified match ID where the target's squad was eliminated"
    )
    async def bounty_claim(
        self,
        interaction: discord.Interaction,
        bounty_id: int,
        match_id: int
    ):
        try:
            result = await claim_bounty(bounty_id, interaction.user.id, match_id)
        except EconomyError as exc:
            return await interaction.response.send_message(
                embed=err(str(exc)),
                ephemeral=True
            )

        await audit(
            interaction.user.id,
            "bounty_claim",
            f"#{bounty_id}:match={match_id}:+{result['payout']}"
        )

        embed = ok(
            f"🎯 Bounty claimed!\n\n"
            f"You eliminated the target of bounty `#{bounty_id}` in match `#{match_id}`.\n"
            f"💰 Payout: **+{result['payout']}** coins\n"
            f"💰 New balance: **{await get_balance(interaction.user.id)}** coins"
        )
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Bounty Board • Developed by {DEVELOPER}"
        )
        await interaction.response.send_message(embed=embed)

    # =========================================================
    # /bounty cancel
    # =========================================================

    @bounty.command(
        name="cancel",
        description="Cancel an active bounty you placed (full refund) — staff can cancel any"
    )
    @app_commands.describe(bounty_id="Bounty ID to cancel")
    async def bounty_cancel(
        self,
        interaction: discord.Interaction,
        bounty_id: int
    ):
        try:
            bounty = await cancel_bounty(
                bounty_id,
                interaction.user.id,
                staff=staff(interaction.user)
            )
        except EconomyError as exc:
            return await interaction.response.send_message(
                embed=err(str(exc)),
                ephemeral=True
            )

        await audit(interaction.user.id, "bounty_cancel", f"#{bounty_id}")
        await interaction.response.send_message(
            embed=ok(
                f"Bounty `#{bounty_id}` cancelled — **{bounty['amount']}** coins refunded "
                f"to <@{bounty['placer_id']}>."
            )
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))
