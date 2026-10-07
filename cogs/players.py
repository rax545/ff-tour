"""Player identity cards: cyberpunk gamer passport & FUT-style Ultimate card."""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import SERVER_NAME, DEVELOPER
from services.arena import player_passport
from services.players import player_card_profile
from utils.banner import generate_player_passport_card, generate_ultimate_player_card
from utils.embeds import err


class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    player = app_commands.Group(
        name="player",
        description="Player identity — cyberpunk passport & FUT Ultimate trading card"
    )

    @player.command(
        name="passport",
        description="Generate your cyberpunk gamer passport ID card"
    )
    @app_commands.describe(member="Member to inspect (defaults to yourself)")
    async def player_passport_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        target = member or interaction.user
        await interaction.response.defer(ephemeral=True)

        rosters, stats, student = await player_passport(target.id)
        if not rosters:
            return await interaction.followup.send(
                embed=err(
                    "No linked player roster found. "
                    "Ask your captain to link your Discord account via `/team addplayer`."
                ),
                ephemeral=True
            )

        primary = rosters[0]
        batch = primary.get("batch") or (student["batch"] if student else "")
        section = primary.get("section") or (student["section"] if student else "")

        image = await asyncio.to_thread(
            generate_player_passport_card,
            target.display_name,
            primary["ign"],
            primary["uid"],
            primary["role"],
            batch,
            section,
            stats["kills"],
            stats["matches"],
            SERVER_NAME
        )
        await interaction.followup.send(
            file=discord.File(image, filename="gamer_passport.png"),
            content=(
                "🛂 Your **Root LU Gamer Passport** — private identity card. "
                "Student ID is never included."
            ),
            ephemeral=True
        )

    @player.command(
        name="card",
        description="Generate your FUT-style Ultimate Player trading card (OVR + 6 attributes)"
    )
    @app_commands.describe(member="Member to inspect (defaults to yourself)")
    async def player_card_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        target = member or interaction.user
        await interaction.response.defer(ephemeral=True)

        profile = await player_card_profile(target.id)
        if not profile:
            return await interaction.followup.send(
                embed=err(
                    "No linked player roster found. "
                    "Ask your captain to link your Discord account via `/team addplayer`."
                ),
                ephemeral=True
            )

        image = await asyncio.to_thread(
            generate_ultimate_player_card,
            profile["ign"],
            profile["team_tag"],
            profile["role"],
            profile["ovr"],
            profile["attributes"],
            profile["kills"],
            profile["matches"],
            profile["wins"],
            SERVER_NAME
        )
        embed = discord.Embed(
            title=f"⚡ {profile['ign']} — ULTIMATE PLAYER CARD",
            description=(
                f"OVR **{profile['ovr']}** • {profile['role']} • "
                f"{profile['team_name']} `[{profile['team_tag']}]`"
                + (f"\n🏛️ CSE Batch {profile['batch']} (Sec {profile['section']})"
                   if profile["batch"] or profile["section"] else "")
            ),
            color=discord.Color.from_rgb(0, 230, 255),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="attachment://ultimate_player_card.png")
        embed.set_footer(
            text=f"🐺 {SERVER_NAME} • Ultimate Team • Developed by {DEVELOPER}"
        )
        await interaction.followup.send(
            embed=embed,
            file=discord.File(image, filename="ultimate_player_card.png"),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Players(bot))
