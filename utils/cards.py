"""Pillow-generated tournament graphics; room credentials never appear in images."""

import io

from PIL import Image, ImageDraw

from utils.banner import FONT_BOLD_PATH, FONT_REGULAR_PATH, clean_text_for_image, get_font


def card(width, height, title, subtitle, lines, accent=(245, 180, 50)):
    image = Image.new("RGB", (width, height), (9, 14, 31))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line(
            (0, y, width, y),
            fill=(9 + y * 9 // height, 14 + y * 8 // height, 31 + y * 17 // height),
        )
    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=25, outline=accent, width=4)
    draw.rectangle((45, 45, width - 45, 55), fill=accent)
    draw.text(
        (65, 85), clean_text_for_image(title)[:42], font=get_font(FONT_BOLD_PATH, 48), fill=accent
    )
    draw.text(
        (65, 154),
        clean_text_for_image(subtitle)[:65],
        font=get_font(FONT_REGULAR_PATH, 25),
        fill="white",
    )
    available = height - 250
    step = max(30, min(55, available // max(1, len(lines))))
    for i, line in enumerate(lines[: available // step]):
        y = 215 + i * step
        draw.rounded_rectangle((60, y - 5, width - 60, y + step - 8), radius=8, fill=(24, 32, 54))
        draw.text(
            (80, y),
            clean_text_for_image(line)[:85],
            font=get_font(FONT_BOLD_PATH, min(25, step - 10)),
            fill="white",
        )
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf


def room_pass(team, tournament, match_no, map_name):
    return card(
        1100,
        500,
        "VIP ROOM PASS",
        tournament,
        [
            f"SQUAD: {team}",
            f"MATCH #{match_no}  |  MAP: {map_name}",
            "PRIVATE ACCESS - CREDENTIALS IN DM",
        ],
    )


def points_table(tournament, rows, page=1):
    lines = [
        f"{i:02d}   {row['name'][:28]:28}   {row['matches']} MATCHES   {row['kills']} KILLS   {row['pts']} PTS"
        for i, row in enumerate(rows, (page - 1) * 12 + 1)
    ]
    return card(1200, 880, "POINTS TABLE", f"{tournament}  |  PAGE {page}", lines, (0, 220, 255))


def booyah(team, tournament, points):
    return card(1100, 500, "BOOYAH! WINNER", tournament, [team, f"{points} POINTS"], (255, 197, 44))


def mvp(player, team, kills):
    return card(
        1100,
        500,
        "MVP // CYBERPUNK",
        team,
        [player, f"{kills} VERIFIED INDIVIDUAL KILLS"],
        (255, 40, 186),
    )


def live_broadcast(tournament, match_no, map_name, platform):
    return card(
        1280,
        720,
        "LIVE NOW - ON AIR",
        tournament,
        [
            f"MATCH #{match_no}  |  MAP: {map_name}",
            f"WATCH LIVE ON {str(platform).upper()}",
            "TUNE IN NOW - DO NOT MISS THE ACTION",
        ],
        (239, 68, 68),
    )


def passport(player, rosters, stats, student=None):
    from utils.arena_cards import passport_card

    return passport_card(player, rosters, stats, student)


def certificate(record):
    return card(
        1600,
        1000,
        "CERTIFICATE OF ACHIEVEMENT",
        record["tournament_name"],
        [
            record["recipient_name"],
            record["award"],
            f"SQUAD: {record['team_name']}",
            f"ISSUED: {record['issued_at']} UTC",
            f"REGISTRY: {record['code']}",
            "VERIFY WITH /certificate verify - REGISTRY STATUS IS AUTHORITATIVE",
        ],
        (255, 197, 44),
    )


def slot_grid(tournament, teams, max_teams, page=1):
    """Render 24 deterministic, ID-ordered lobby positions per page."""
    if page < 1 or (page - 1) * 24 >= max_teams:
        raise ValueError("Page has no slots.")
    image = Image.new("RGB", (1440, 1000), (9, 14, 31))
    draw = ImageDraw.Draw(image)
    draw.text((40, 30), "SQUAD SLOT GRID", font=get_font(FONT_BOLD_PATH, 44), fill=(0, 220, 255))
    draw.text(
        (40, 95),
        clean_text_for_image(tournament)[:65],
        font=get_font(FONT_REGULAR_PATH, 26),
        fill="white",
    )
    draw.text(
        (40, 140),
        f"{len(teams)}/{max_teams} REGISTERED | PAGE {page} | ID-ORDERED LOBBY",
        font=get_font(FONT_REGULAR_PATH, 22),
        fill="white",
    )
    for pos in range(24):
        index = (page - 1) * 24 + pos
        if index >= max_teams:
            break
        x, y = 40 + (pos % 4) * 350, 210 + (pos // 4) * 125
        occupied = index < len(teams)
        accent = (0, 220, 255) if occupied else (90, 108, 131)
        draw.rounded_rectangle(
            (x, y, x + 330, y + 108), radius=12, fill=(24, 32, 54), outline=accent, width=2
        )
        draw.text(
            (x + 15, y + 10),
            f"SLOT {index + 1:02d}",
            font=get_font(FONT_BOLD_PATH, 22),
            fill=accent,
        )
        name = f"{teams[index]['name']} [{teams[index]['tag']}]" if occupied else "OPEN"
        draw.text(
            (x + 15, y + 52),
            clean_text_for_image(name)[:22],
            font=get_font(FONT_REGULAR_PATH, 22),
            fill="white",
        )
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf
