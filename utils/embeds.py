import discord
from config import BRAND, SERVER_NAME, SERVER_NAME_CLEAN


def base(
    title: str,
    description: str = "",
    color: discord.Color = discord.Color.from_rgb(124, 58, 237)
) -> discord.Embed:
    e = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    e.set_footer(text=f"🐺 {SERVER_NAME} • Esports Management")
    return e


def ok(msg: str) -> discord.Embed:
    return base("✅ Success", msg, discord.Color.from_rgb(16, 185, 129))


def err(msg: str) -> discord.Embed:
    return base("❌ Error", msg, discord.Color.from_rgb(239, 68, 68))


def info(msg: str) -> discord.Embed:
    return base("ℹ️ Information", msg, discord.Color.from_rgb(59, 130, 246))


def og_match_dm_embed(
    team_name: str,
    team_tag: str,
    tournament_name: str,
    tournament_id: int,
    match_no: int,
    match_id: int,
    map_name: str,
    scheduled_at: str,
    lineup_details: list = None,
    server_name: str = SERVER_NAME
) -> discord.Embed:
    """
    OG Battle Dispatch embed sent to registered team captains/members in DM.
    Includes the squad's 4 main players + 1 extra substitute player and their roles.
    """
    desc = (
        f"```fix\n"
        f"⚡ {server_name} • OFFICIAL BATTLE DISPATCH ⚡\n"
        f"```\n"
        f"### ⚔️ **ATTENTION WARRIORS • {team_name} [{team_tag}]** ⚔️\n\n"
        f"Your squad has been officially locked in for combat in **{tournament_name}**!\n"
        f"Lock in your 4-man lineup, coordinate in voice, and prepare for the drop."
    )
    embed = discord.Embed(
        title=f"🐺 {server_name} • MATCH DISPATCH",
        description=desc,
        color=discord.Color.from_rgb(245, 158, 11),  # Amber Gold
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="🛡️ Your Squad",
        value=f"**{team_name}** `[{team_tag}]`",
        inline=True
    )
    embed.add_field(
        name="🎮 Match Round",
        value=f"**Match #{match_no}** (ID: `#{match_id}`)",
        inline=True
    )
    embed.add_field(
        name="🏆 Tournament",
        value=f"**{tournament_name}** (ID: `#{tournament_id}`)",
        inline=True
    )
    embed.add_field(
        name="🗺️ Battleground / Map",
        value=f"**{map_name}**",
        inline=True
    )
    embed.add_field(
        name="⏰ Scheduled Drop",
        value=f"**{scheduled_at}**",
        inline=True
    )
    embed.add_field(
        name="📊 Match Status",
        value="🟡 **STANDBY IN LOBBY**",
        inline=True
    )

    # Lineup & Roles breakdown
    if lineup_details:
        role_icons = {
            "IGL": "👑",
            "Rusher": "⚡",
            "Sniper": "🎯",
            "Assaulter": "💥",
            "Support": "🛡️",
            "Substitute": "🔄",
            "Captain": "👑"
        }
        starters = []
        subs = []
        for p in lineup_details:
            r_name = p.get("role", "Player")
            icon = role_icons.get(r_name, "🎮")
            uid_str = f"UID: `{p.get('uid', 'N/A')}`"
            ign_str = f"`{p.get('ign', 'N/A')}`"
            user_mention = f" (<@{p['user_id']}>)" if p.get("user_id") and p["user_id"] > 0 else ""
            line = f"{icon} **{r_name}:** {ign_str} • {uid_str}{user_mention}"

            if p.get("is_sub") or r_name.lower() in ("sub", "substitute"):
                subs.append(line)
            else:
                starters.append(line)

        formatted_lineup = []
        if starters:
            formatted_lineup.append("**⚔️ 4-Man Active Lineup:**\n" + "\n".join(starters))
        if subs:
            formatted_lineup.append("**🔄 5th Player (Extra Substitute):**\n" + "\n".join(subs))

        if formatted_lineup:
            embed.add_field(
                name="👥 Registered Lineup & Roles",
                value="\n\n".join(formatted_lineup),
                inline=False
            )

    embed.add_field(
        name="📜 Mandatory OG Match Protocols",
        value=(
            "▸ ⏱️ **Lobby Assembly:** Be in voice/standby lobby **15 minutes** before scheduled match.\n"
            "▸ 🔑 **Credentials Delivery:** Room ID & Password will be delivered right to your DMs when room opens.\n"
            "▸ 🚫 **Zero Tolerance:** No emulators, config hacks, scripts, or teaming. Instant DQ & server blacklist.\n"
            "▸ 📸 **Scoreboard Proof:** Team Captain must capture a clean end-game screenshot of final scoreboard & kills."
        ),
        inline=False
    )
    embed.set_footer(
        text=f"🐺 {server_name} • Elite Free Fire Esports League"
    )
    return embed


def og_room_dm_embed(
    team_name: str,
    team_tag: str,
    tournament_name: str,
    match_no: int,
    match_id: int,
    room_id: str,
    password: str,
    map_name: str = "Battlefield",
    server_name: str = SERVER_NAME
) -> discord.Embed:
    """
    OG Room Credentials Release embed sent to team captains in DM.
    """
    desc = (
        f"```diff\n"
        f"+ 🐺 {server_name} • CUSTOM ROOM LIVE +\n"
        f"```\n"
        f"### 🚨 **ROOM ACCESS RELEASED • {team_name} [{team_tag}]** 🚨\n\n"
        f"The custom lobby for **Match #{match_no}** is now OPEN!\n"
        f"Enter immediately with your registered lineup."
    )
    embed = discord.Embed(
        title=f"🔑 {server_name} • ROOM CREDENTIALS",
        description=desc,
        color=discord.Color.from_rgb(16, 185, 129),  # Emerald Green
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="🔑 Room ID",
        value=f"```{room_id}```",
        inline=True
    )
    embed.add_field(
        name="🔐 Password",
        value=f"```{password}```",
        inline=True
    )
    embed.add_field(
        name="🎮 Match Round",
        value=f"**Match #{match_no}**",
        inline=True
    )
    embed.add_field(
        name="🛡️ Your Squad",
        value=f"**{team_name}** `[{team_tag}]`",
        inline=True
    )
    embed.add_field(
        name="🏆 Tournament",
        value=f"**{tournament_name}**",
        inline=True
    )
    embed.add_field(
        name="🗺️ Map",
        value=f"**{map_name}**",
        inline=True
    )
    embed.add_field(
        name="⚠️ Important Guidelines",
        value=(
            "▸ 🚪 Enter only your designated squad slot.\n"
            "▸ 🔒 Do NOT share room credentials outside your squad (instant disqualification).\n"
            "▸ ⏳ Match starts in 10 minutes sharp. Be ready in lobby!"
        ),
        inline=False
    )
    embed.set_footer(
        text=f"🐺 {server_name} • Free Fire Esports Arena"
    )
    return embed
