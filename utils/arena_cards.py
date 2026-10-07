"""Deterministic, network-free arena PNGs. Rendering runs off the Discord event loop."""

import io
import math

from PIL import Image, ImageDraw

from config import SERVER_NAME
from utils.banner import (
    FONT_BOLD_PATH,
    FONT_REGULAR_PATH,
    clean_text_for_image,
    draw_wolf_crest,
    get_font,
)

BG = (9, 14, 31)
PANEL = (22, 31, 52)
WHITE = (231, 240, 255)
MUTED = (146, 166, 197)
CYAN = (0, 220, 255)
GOLD = (255, 197, 44)
PINK = (255, 60, 154)


def _canvas(width, height, accent=CYAN):
    image = Image.new("RGBA", (width, height), (*BG, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line(
            (0, y, width, y),
            fill=(9 + y * 8 // height, 14 + y * 10 // height, 31 + y * 18 // height),
        )
    for x in range(-height, width, 140):
        draw.line((x, height, x + height, 0), fill=(23, 32, 51), width=2)
    draw.rectangle((0, 0, width, 9), fill=accent)
    return image, draw


def _text(draw, xy, value, width, size=28, color=WHITE, *, bold=True):
    value = clean_text_for_image(str(value)[:2048]).replace("\n", " ").replace("\t", " ")
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    font = get_font(path, size)
    while size > 14 and draw.textbbox((0, 0), value, font=font)[2] > width:
        size -= 2
        font = get_font(path, size)
    if draw.textbbox((0, 0), value, font=font)[2] > width:
        # Binary search avoids quadratic text measurement for long/malicious names.
        low, high = 0, len(value)
        while low < high:
            middle = (low + high + 1) // 2
            if draw.textbbox((0, 0), value[:middle] + "...", font=font)[2] <= width:
                low = middle
            else:
                high = middle - 1
        value = value[:low] + "..."
    draw.text(xy, value, font=font, fill=color)


def _png(image):
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def bracket_card(bracket):
    rounds = int(math.log2(bracket["size"]))
    width = max(1100, 80 + rounds * 320)
    height = max(720, 260 + (bracket["size"] // 2) * 108)
    image, draw = _canvas(width, height)
    _text(draw, (40, 35), "BRACKET TREE // SINGLE ELIMINATION", width - 80, 40, CYAN)
    _text(draw, (40, 100), bracket["tournament_name"], width - 80, 28)
    _text(
        draw,
        (40, 145),
        f"{len(bracket['entries'])} SQUADS | {bracket['status'].upper()} | STAFF-CONFIRMED SCORES",
        width - 80,
        20,
        MUTED,
    )
    entries = {e["team_id"]: e for e in bracket["entries"]}
    centres = {}
    for node in bracket["nodes"]:
        key = (node["round_no"], node["position"])
        centres[key] = (
            256 + (node["position"] - 1) * 108
            if node["round_no"] == 1
            else (centres[(key[0] - 1, key[1] * 2 - 1)] + centres[(key[0] - 1, key[1] * 2)]) / 2
        )
    for node in bracket["nodes"]:
        r, pos = node["round_no"], node["position"]
        x, y = 40 + (r - 1) * 320, centres[(r, pos)]
        if r > 1:
            for child_pos in (pos * 2 - 1, pos * 2):
                child_y = centres[(r - 1, child_pos)]
                draw.line((x - 50, child_y, x - 25, child_y, x - 25, y, x, y), fill=MUTED, width=2)
        color = (
            GOLD if node["status"] == "finished" else CYAN if node["status"] == "ready" else MUTED
        )
        draw.rounded_rectangle(
            (x, y - 42, x + 270, y + 42), radius=10, fill=PANEL, outline=color, width=2
        )
        _text(
            draw, (x + 12, y - 37), f"NODE #{node['id']} | {node['status'].upper()}", 246, 14, color
        )
        for offset, side in ((-13, "a"), (12, "b")):
            team_id = node[f"team_{side}"]
            entry = entries.get(team_id)
            name = (
                f"{side.upper()}: [{entry['tag']}] {entry['name']}"
                if entry
                else ("BYE" if r == 1 or node["status"] == "bye" else "TBD")
            )
            score = node[f"score_{side}"]
            _text(
                draw,
                (x + 12, y + offset),
                name,
                210,
                18,
                GOLD if team_id and team_id == node["winner_id"] else WHITE,
            )
            if score is not None:
                _text(draw, (x + 234, y + offset), score, 30, 18, color)
    for r in range(1, rounds + 1):
        _text(
            draw, (40 + (r - 1) * 320, 185), "FINAL" if r == rounds else f"ROUND {r}", 270, 17, CYAN
        )
    final = bracket["nodes"][-1]
    if final["winner_id"] and bracket["status"] == "finished":
        _text(
            draw,
            (40, height - 53),
            f"CHAMPION: {entries[final['winner_id']]['name']}",
            width - 80,
            30,
            GOLD,
        )
    else:
        _text(
            draw,
            (40, height - 48),
            "Node IDs are used with /bracket resolve and /bracket bind.",
            width - 80,
            18,
            MUTED,
        )
    return _png(image)


def clash_card(data):
    image, draw = _canvas(1600, 900, PINK)
    fixture = data["match"]
    _text(draw, (55, 40), "SQUAD CLASH // HEAD TO HEAD", 1490, 50, WHITE)
    _text(draw, (55, 115), fixture["tournament_name"], 1490, 30, CYAN)
    _text(
        draw,
        (55, 170),
        f"MATCH #{fixture['match_no']} | {fixture['map'] or 'TBA'} | {fixture['scheduled_at']}",
        1490,
        22,
        MUTED,
    )
    for team, x, color in zip(data["squads"], (55, 910), (CYAN, PINK)):
        draw.rounded_rectangle(
            (x, 240, x + 635, 798), radius=22, fill=PANEL, outline=color, width=3
        )
        draw_wolf_crest(draw, x + 80, 350, 0.75, eye_color=color)
        _text(draw, (x + 170, 282), f"[{team['tag']}]", 420, 28, color)
        _text(draw, (x + 170, 334), team["name"], 420, 42)
        stats = team["stats"]
        _text(
            draw,
            (x + 30, 420),
            f"{stats['points']} PTS  |  {stats['kills']} KILLS  |  {stats['matches']} MATCHES",
            575,
            22,
            color,
        )
        _text(draw, (x + 30, 474), "ROSTER // 4 + 1", 575, 18, MUTED)
        if not team["lineup"]:
            _text(draw, (x + 30, 525), "Lineup pending", 575, 24)
        for index, player in enumerate(team["lineup"][:5]):
            _text(
                draw,
                (x + 30, 523 + index * 46),
                f"{player['ign']} | {player['role']}" + (" [SUB]" if player["is_sub"] else ""),
                575,
                23,
            )
    draw.polygon(((800, 350), (875, 455), (800, 560), (725, 455)), fill=(32, 40, 68), outline=GOLD)
    _text(draw, (754, 425), "VS", 95, 52, GOLD)
    _text(
        draw,
        (55, 840),
        f"{SERVER_NAME} | VERIFIED SQUAD STATS | NO ROOM CREDENTIALS OR PLAYER UIDS",
        1490,
        20,
        MUTED,
    )
    return _png(image)


def hall_of_fame_card(records, page=1, total_pages=1):
    image, draw = _canvas(1600, 1000, GOLD)
    _text(draw, (50, 38), "HALL OF FAME // THE LEGACY", 1500, 52, GOLD)
    _text(
        draw,
        (50, 118),
        f"{SERVER_NAME} | STAFF-FINALIZED CHAMPIONS | PAGE {page}/{total_pages}",
        1500,
        23,
        MUTED,
    )
    for index, record in enumerate(records[:4]):
        x, y = 50 + (index % 2) * 775, 205 + (index // 2) * 375
        draw.rounded_rectangle(
            (x, y, x + 725, y + 340), radius=20, fill=PANEL, outline=GOLD, width=2
        )
        _text(draw, (x + 25, y + 20), record["tournament_name"], 675, 30, CYAN)
        _text(
            draw,
            (x + 25, y + 70),
            f"ARCHIVE #{record['id']} | {record['format'].replace('_', ' ').upper()}",
            675,
            17,
            MUTED,
        )
        champion = record["podium"][0]
        _text(
            draw,
            (x + 25, y + 110),
            f"CHAMPION: [{champion['tag']}] {champion['name']}",
            675,
            30,
            GOLD,
        )
        _text(
            draw,
            (x + 25, y + 163),
            f"{champion['points']} POINTS | {champion['kills']} VERIFIED SQUAD KILLS",
            675,
            21,
        )
        if len(record["podium"]) > 1:
            _text(draw, (x + 25, y + 207), f"RUNNER-UP: {record['podium'][1]['name']}", 675, 23)
        mvp = record["mvp"]
        _text(
            draw,
            (x + 25, y + 252),
            f"MVP: {mvp['ign']} / {mvp['kills']} INDIVIDUAL KILLS"
            if mvp
            else "MVP: NO VERIFIED INDIVIDUAL DATA",
            675,
            21,
            PINK,
        )
        _text(draw, (x + 25, y + 300), f"INDUCTED: {record['inducted_at']} UTC", 675, 15, MUTED)
    _text(
        draw,
        (50, 955),
        "Historical snapshots. Revoked records are excluded. Team scores are never individual MVP kills.",
        1500,
        18,
        MUTED,
    )
    return _png(image)


def prediction_card(pool, entries, page=1, total_pages=1):
    image, draw = _canvas(1440, 1000, PINK)
    _text(draw, (40, 35), "PREDICTION ARENA // PICK YOUR BOOYAH", 1360, 43, PINK)
    _text(draw, (40, 100), f"{pool['tournament_name']} | MATCH #{pool['match_no']}", 1360, 28)
    _text(
        draw,
        (40, 153),
        f"ARENA #{pool['id']} | {pool['status'].upper()} | {pool['total_picks']} PICKS | PAGE {page}/{total_pages}",
        1360,
        22,
        CYAN,
    )
    for index, entry in enumerate(entries[:12]):
        x, y = 40 + (index % 3) * 460, 230 + (index // 3) * 168
        color = GOLD if entry["team_id"] == pool.get("winner_team_id") else CYAN
        draw.rounded_rectangle(
            (x, y, x + 435, y + 142), radius=14, fill=PANEL, outline=color, width=2
        )
        _text(draw, (x + 20, y + 16), f"[{entry['tag']}] {entry['name']}", 395, 28, color)
        percentage = entry["picks"] * 100 / max(1, pool["total_picks"])
        _text(
            draw,
            (x + 20, y + 66),
            f"{entry['picks']} PICKS  /  {percentage:.0f}%  /  TEAM #{entry['team_id']}",
            395,
            18,
        )
        draw.rounded_rectangle((x + 20, y + 108, x + 415, y + 122), radius=5, fill=(46, 56, 80))
        if percentage:
            draw.rounded_rectangle(
                (x + 20, y + 108, x + 20 + int(395 * percentage / 100), y + 122),
                radius=5,
                fill=color,
            )
    _text(
        draw,
        (40, 955),
        "10 bragging-rights points per correct pick. No money, stakes, purchases or payouts. Counts refresh on /prediction arena.",
        1360,
        18,
        MUTED,
    )
    return _png(image)


def passport_card(player, rosters, stats, student=None):
    image, draw = _canvas(1200, 720)
    _text(draw, (45, 30), "PLAYER PASSPORT // ARENA IDENTITY", 1110, 43, CYAN)
    _text(draw, (45, 100), player, 1110, 34)
    subtitle = (
        f"{student['department']} | BATCH {student['batch']} | SECTION {student['section']}"
        if student
        else "ROSTER-LINKED PROFILE | NOT OFFICIAL GARENA IDENTITY VERIFICATION"
    )
    _text(draw, (45, 157), subtitle, 1110, 20, MUTED)
    for x, value, label in (
        (45, stats["kills"], "INDIVIDUAL KILLS"),
        (420, stats["damage"], "RECORDED DAMAGE"),
        (795, stats["matches"], "VERIFIED MATCHES"),
    ):
        draw.rounded_rectangle((x, 215, x + 355, 325), radius=14, fill=PANEL, outline=CYAN, width=2)
        _text(draw, (x + 22, 226), value, 311, 42, GOLD)
        _text(draw, (x + 22, 287), label, 311, 17, MUTED)
    _text(draw, (45, 355), "RECENT ROSTER LINKS // PRIVATE", 1110, 20, CYAN)
    for index, row in enumerate(rosters[:5]):
        _text(
            draw,
            (45, 404 + index * 46),
            f"{row['ign']} | UID {row['uid']} | {row['role']} | {row['team_name']}",
            1110,
            22,
        )
    _text(
        draw,
        (45, 667),
        "Verified individual data only. Conflicting identities / duplicate match rows are excluded. No student IDs.",
        1110,
        17,
        MUTED,
    )
    return _png(image)
