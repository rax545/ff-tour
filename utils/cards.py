"""Pillow-generated tournament graphics; room credentials never appear in images."""
import io
from PIL import Image, ImageDraw
from utils.banner import get_font, FONT_BOLD_PATH, FONT_REGULAR_PATH, clean_text_for_image


def card(width, height, title, subtitle, lines, accent=(245, 180, 50)):
    image = Image.new('RGB', (width, height), (9, 14, 31))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line((0, y, width, y), fill=(9 + y * 9 // height, 14 + y * 8 // height, 31 + y * 17 // height))
    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=25, outline=accent, width=4)
    draw.rectangle((45, 45, width - 45, 55), fill=accent)
    draw.text((65, 85), clean_text_for_image(title)[:42], font=get_font(FONT_BOLD_PATH, 48), fill=accent)
    draw.text((65, 154), clean_text_for_image(subtitle)[:65], font=get_font(FONT_REGULAR_PATH, 25), fill='white')
    available = height - 250
    step = max(30, min(55, available // max(1, len(lines))))
    for i, line in enumerate(lines[:available // step]):
        y = 215 + i * step
        draw.rounded_rectangle((60, y - 5, width - 60, y + step - 8), radius=8, fill=(24, 32, 54))
        draw.text((80, y), clean_text_for_image(line)[:85], font=get_font(FONT_BOLD_PATH, min(25, step - 10)), fill='white')
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return buf


def room_pass(team, tournament, match_no, map_name):
    return card(1100, 500, 'VIP ROOM PASS', tournament,
                [f'SQUAD: {team}', f'MATCH #{match_no}  |  MAP: {map_name}', 'PRIVATE ACCESS - CREDENTIALS IN DM'])


def points_table(tournament, rows, page=1):
    lines = [f'{i:02d}   {row["name"][:28]:28}   {row["matches"]} MATCHES   {row["kills"]} KILLS   {row["pts"]} PTS'
             for i, row in enumerate(rows, (page - 1) * 12 + 1)]
    return card(1200, 880, 'POINTS TABLE', f'{tournament}  |  PAGE {page}', lines, (0, 220, 255))


def booyah(team, tournament, points):
    return card(1100, 500, 'BOOYAH! WINNER', tournament, [team, f'{points} POINTS'], (255, 197, 44))


def mvp(player, team, kills):
    return card(1100, 500, 'MVP // CYBERPUNK', team, [player, f'{kills} TEAM KILLS'], (255, 40, 186))
