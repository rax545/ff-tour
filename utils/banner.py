import io
import math
import os
import unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def get_font(path: str, size: int):
    """
    Safely load a truetype font with fallback to default.
    """
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
        if os.path.exists(FONT_BOLD_PATH):
            return ImageFont.truetype(FONT_BOLD_PATH, size)
        if os.path.exists(FONT_REGULAR_PATH):
            return ImageFont.truetype(FONT_REGULAR_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()


def clean_text_for_image(text: str) -> str:
    """
    Clean and normalize unicode characters (e.g., math bold letters)
    into standard ASCII so system TTF fonts render them crisply.
    """
    if not text:
        return ""
    norm = unicodedata.normalize("NFKD", str(text))
    # Replace Bengali currency sign with BDT
    norm = norm.replace("৳", "BDT ").replace("•", "-")
    # Filter out unprintable or non-ascii symbols that might render as boxes
    cleaned = []
    for char in norm:
        if ord(char) < 128:
            cleaned.append(char)
        elif char in ("-", " ", "/", ":", "#", "(", ")", "[", "]", "!"):
            cleaned.append(char)
        else:
            # Drop exotic unsupported emojis/characters for the PIL renderer
            pass
    result = "".join(cleaned).strip()
    return result if result else "WHITE WOLF GLOBAL"


def draw_wolf_crest(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0, alpha: int = 255, eye_color=(0, 240, 255)):
    """
    Draw a sharp, 3D geometric low-poly wolf crest.
    """
    s = scale
    facets = [
        ([(0, -35), (-20, -45), (-12, -15), (0, -20)], (180, 195, 220, int(alpha * 0.9))),
        ([(0, -35), (20, -45), (12, -15), (0, -20)], (225, 235, 250, alpha)),
        ([(-20, -45), (-35, -75), (-25, -20)], (130, 145, 175, int(alpha * 0.85))),
        ([(-20, -45), (-30, -70), (-18, -30)], (90, 105, 140, int(alpha * 0.95))),
        ([(20, -45), (35, -75), (25, -20)], (160, 175, 205, int(alpha * 0.9))),
        ([(20, -45), (30, -70), (18, -30)], (110, 125, 160, int(alpha * 0.95))),
        ([(-25, -20), (-40, -5), (-25, 15), (-12, -5)], (140, 155, 185, int(alpha * 0.8))),
        ([(25, -20), (40, -5), (25, 15), (12, -5)], (175, 190, 220, int(alpha * 0.85))),
        ([(-40, -5), (-32, 22), (-20, 12)], (110, 125, 155, int(alpha * 0.75))),
        ([(40, -5), (32, 22), (20, 12)], (145, 160, 190, int(alpha * 0.8))),
        ([(0, -20), (-12, -15), (-8, 10), (0, 15)], (160, 175, 205, int(alpha * 0.85))),
        ([(0, -20), (12, -15), (8, 10), (0, 15)], (200, 215, 240, int(alpha * 0.95))),
        ([(0, 15), (-8, 10), (-6, 32), (0, 36)], (130, 145, 175, int(alpha * 0.9))),
        ([(0, 15), (8, 10), (6, 32), (0, 36)], (170, 185, 215, int(alpha * 0.95))),
        ([(0, 36), (-6, 32), (0, 48)], (90, 100, 130, int(alpha * 0.8))),
        ([(0, 36), (6, 32), (0, 48)], (120, 135, 160, int(alpha * 0.85))),
        ([(-6, 32), (-25, 15), (-12, 35), (0, 48)], (80, 95, 120, int(alpha * 0.75))),
        ([(6, 32), (25, 15), (12, 35), (0, 48)], (105, 120, 145, int(alpha * 0.8))),
    ]
    for pts, col in facets:
        scaled_pts = [(cx + x * s, cy + y * s) for x, y in pts]
        draw.polygon(scaled_pts, fill=col)

    # Eyes (glowing)
    eye_l = [(cx - 16 * s, cy - 14 * s), (cx - 7 * s, cy - 8 * s), (cx - 14 * s, cy - 6 * s)]
    draw.polygon(eye_l, fill=eye_color + (alpha,))
    eye_r = [(cx + 16 * s, cy - 14 * s), (cx + 7 * s, cy - 8 * s), (cx + 14 * s, cy - 6 * s)]
    draw.polygon(eye_r, fill=eye_color + (alpha,))

    # Nose tip
    nose = [(cx, cy + 28 * s), (cx - 4 * s, cy + 24 * s), (cx + 4 * s, cy + 24 * s)]
    draw.polygon(nose, fill=(30, 35, 50, alpha))


def fit_text_font(text: str, max_width: int, max_size: int, min_size: int = 14, font_path: str = FONT_BOLD_PATH) -> ImageFont.ImageFont:
    """
    Find font size that makes text fit within max_width.
    """
    for size in range(max_size, min_size - 1, -2):
        f = get_font(font_path, size)
        bbox = f.getbbox(text)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return f
    return get_font(font_path, min_size)


def generate_tournament_banner(
    tournament_name: str,
    server_name: str = "WHITE WOLF GLOBAL",
    max_teams: int = 12,
    prize_pool: float = 0.0,
    entry_fee: float = 0.0,
    tournament_id: int = 1,
    status: str = "OPEN"
) -> io.BytesIO:
    """
    Generate an ultra-premium esports tournament banner image with server branding.
    Returns BytesIO object containing the PNG image.
    """
    W, H = 1200, 520
    img = Image.new("RGBA", (W, H), (10, 13, 24, 255))
    draw = ImageDraw.Draw(img)

    clean_server = clean_text_for_image(server_name).upper()
    if not clean_server:
        clean_server = "WHITE WOLF GLOBAL"
    clean_tourn = clean_text_for_image(tournament_name).upper()
    if not clean_tourn:
        clean_tourn = "ESPORTS TOURNAMENT"

    # 1. Background gradient (deep esports midnight blue)
    for y in range(H):
        t = y / H
        r = int(7 + 11 * t)
        g = int(10 + 13 * t)
        b = int(24 + 16 * (1 - t * 0.5))
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # 2. Glowing spotlight halos
    spotlight = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(spotlight)
    sdraw.ellipse([(W // 2 - 320, -180), (W // 2 + 320, 240)], fill=(0, 220, 255, 45))
    sdraw.ellipse([(-150, H - 260), (280, H + 160)], fill=(124, 58, 237, 45))
    sdraw.ellipse([(W - 280, H - 260), (W + 160, H + 160)], fill=(245, 158, 11, 40))
    spotlight = spotlight.filter(ImageFilter.GaussianBlur(70))
    img.alpha_composite(spotlight)

    # 3. Cyber tech grid overlay
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    for x in range(0, W, 45):
        gdraw.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)
    for y in range(0, H, 45):
        gdraw.line([(0, y), (W, y)], fill=(255, 255, 255, 8), width=1)
    for off in range(-200, W + 400, 150):
        gdraw.line([(off, 0), (off + 250, H)], fill=(0, 200, 255, 7), width=1)
    img.alpha_composite(grid)

    # 4. Translucent wolf crest watermark on the right
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    draw_wolf_crest(wdraw, W - 170, 240, scale=3.6, alpha=30, eye_color=(0, 240, 255))
    img.alpha_composite(watermark)

    draw = ImageDraw.Draw(img)

    # Load typography
    font_server = get_font(FONT_BOLD_PATH, 25)
    font_badge = get_font(FONT_BOLD_PATH, 12)
    font_sub = get_font(FONT_BOLD_PATH, 15)
    font_card_lbl = get_font(FONT_BOLD_PATH, 12)
    font_card_sub = get_font(FONT_REGULAR_PATH, 11)
    font_footer = get_font(FONT_BOLD_PATH, 13)

    # 5. Outer frame & neon tech corner brackets
    m = 20
    draw.rectangle([m, m, W - m, H - m], outline=(255, 255, 255, 25), width=1)
    cb = 28
    c_color = (0, 230, 255, 255)
    for px, py in [(m, m), (W - m, m), (m, H - m), (W - m, H - m)]:
        dx = 1 if px == m else -1
        dy = 1 if py == m else -1
        draw.line([(px, py), (px + dx * cb, py)], fill=c_color, width=3)
        draw.line([(px, py), (px, py + dy * cb)], fill=c_color, width=3)

    # 6. Header: Wolf Crest + Server Name
    draw_wolf_crest(draw, 88, 70, scale=0.6, alpha=255)
    draw.text((125, 48), clean_server, fill=(255, 255, 255), font=font_server)
    draw.text((127, 82), "OFFICIAL FREE FIRE ESPORTS ARENA", fill=(0, 220, 255), font=font_badge)

    # Top right pill: TOURNAMENT ID
    tid_text = f"TOURNAMENT #{tournament_id}"
    t_bbox = font_badge.getbbox(tid_text)
    tw = t_bbox[2] - t_bbox[0] + 32
    tx = W - m - 20 - tw
    ty = 50
    draw.rounded_rectangle([tx, ty, tx + tw, ty + 34], radius=8, fill=(124, 58, 237, 80), outline=(139, 92, 246, 200), width=1)
    draw.text((tx + 16, ty + 9), tid_text, fill=(235, 220, 255), font=font_badge)

    # Glowing separator line
    draw.line([(m + 20, 115), (W - m - 20, 115)], fill=(255, 255, 255, 30), width=1)
    draw.line([(m + 20, 115), (m + 250, 115)], fill=(0, 230, 255, 200), width=2)

    # 7. Tournament Title
    font_title = fit_text_font(clean_tourn, W - 140, max_size=44, min_size=22)
    draw.text((62, 142), clean_tourn, fill=(0, 180, 255, 90), font=font_title)
    draw.text((60, 140), clean_tourn, fill=(255, 255, 255), font=font_title)

    # Subtitle
    sub_text = "FREE FIRE BATTLE ROYALE - SQUAD MODE - OFFICIAL CHAMPIONSHIP"
    draw.text((62, 198), sub_text, fill=(148, 163, 184), font=font_sub)

    # 8. 4 Stat Cards
    prize_val = f"BDT {prize_pool:g}" if prize_pool > 0 else "GLORY & HONOR"
    entry_val = f"BDT {entry_fee:g}" if entry_fee > 0 else "FREE ENTRY"
    slots_val = f"{max_teams} SQUADS"
    status_val = str(status).upper()

    cards = [
        ("PRIZE POOL", prize_val, "Guaranteed Pool", (245, 158, 11), (254, 243, 199)),
        ("MAX SLOTS", slots_val, "Battle Royale", (0, 220, 255), (224, 242, 254)),
        ("ENTRY FEE", entry_val, "Per Squad", (16, 185, 129), (209, 250, 229)),
        ("STATUS", status_val, "Limited Slots", (139, 92, 246), (237, 233, 254)),
    ]

    card_y = 250
    card_h = 130
    card_gap = 18
    total_gap = card_gap * 3
    card_w = (W - (m * 2) - 40 - total_gap) // 4
    start_x = m + 20

    for i, (label, val, sub, accent_rgb, text_rgb) in enumerate(cards):
        cx = start_x + i * (card_w + card_gap)
        card_img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card_img)
        cdraw.rounded_rectangle([0, 0, card_w, card_h], radius=12, fill=(16, 22, 36, 230), outline=accent_rgb + (140,), width=2)
        cdraw.rounded_rectangle([0, 0, card_w, 5], radius=3, fill=accent_rgb + (255,))
        img.alpha_composite(card_img, (cx, card_y))

        draw.text((cx + 18, card_y + 20), label, fill=(148, 163, 184), font=font_card_lbl)
        font_card_val = fit_text_font(val, card_w - 36, max_size=24, min_size=15)
        draw.text((cx + 18, card_y + 48), val, fill=text_rgb, font=font_card_val)
        draw.text((cx + 18, card_y + 90), sub, fill=(100, 116, 139), font=font_card_sub)
        draw.ellipse([(cx + card_w - 24, card_y + 20), (cx + card_w - 14, card_y + 30)], fill=accent_rgb + (220,))

    # 9. Bottom Footer Bar
    fy = H - m - 45
    draw.line([(m + 20, fy), (W - m - 20, fy)], fill=(255, 255, 255, 25), width=1)
    draw.line([(W - m - 250, fy), (W - m - 20, fy)], fill=(245, 158, 11, 200), width=2)
    foot_text = f"REGISTER NOW VIA SQUAD PANEL  -  HOSTED BY {clean_server}"
    draw.text((m + 22, fy + 12), foot_text, fill=(148, 163, 184), font=font_footer)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def generate_match_banner(
    tournament_name: str,
    match_no: int = 1,
    map_name: str = "Bermuda",
    scheduled_at: str = "TBA",
    server_name: str = "WHITE WOLF GLOBAL"
) -> io.BytesIO:
    """
    Generate an OG match announcement banner graphic.
    """
    W, H = 1200, 460
    img = Image.new("RGBA", (W, H), (12, 10, 22, 255))
    draw = ImageDraw.Draw(img)

    clean_server = clean_text_for_image(server_name).upper()
    if not clean_server:
        clean_server = "WHITE WOLF GLOBAL"
    clean_tourn = clean_text_for_image(tournament_name).upper()
    clean_map = clean_text_for_image(map_name).upper()
    clean_sched = clean_text_for_image(scheduled_at)

    for y in range(H):
        t = y / H
        r = int(14 + 10 * t)
        g = int(9 + 11 * t)
        b = int(22 + 16 * (1 - t * 0.5))
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    spotlight = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(spotlight)
    sdraw.ellipse([(W // 2 - 250, -150), (W // 2 + 250, 220)], fill=(245, 158, 11, 45))
    sdraw.ellipse([(-100, H - 200), (280, H + 150)], fill=(239, 68, 68, 40))
    sdraw.ellipse([(W - 250, H - 200), (W + 150, H + 150)], fill=(0, 220, 255, 40))
    spotlight = spotlight.filter(ImageFilter.GaussianBlur(70))
    img.alpha_composite(spotlight)

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    for x in range(0, W, 45):
        gdraw.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)
    for y in range(0, H, 45):
        gdraw.line([(0, y), (W, y)], fill=(255, 255, 255, 8), width=1)
    img.alpha_composite(grid)

    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    draw_wolf_crest(wdraw, W - 160, 210, scale=3.2, alpha=28, eye_color=(245, 158, 11))
    img.alpha_composite(watermark)

    draw = ImageDraw.Draw(img)

    font_server = get_font(FONT_BOLD_PATH, 24)
    font_badge = get_font(FONT_BOLD_PATH, 12)
    font_sub = get_font(FONT_BOLD_PATH, 15)
    font_card_lbl = get_font(FONT_BOLD_PATH, 12)
    font_card_sub = get_font(FONT_REGULAR_PATH, 11)
    font_footer = get_font(FONT_BOLD_PATH, 13)

    m = 20
    draw.rectangle([m, m, W - m, H - m], outline=(255, 255, 255, 25), width=1)
    cb = 28
    c_color = (245, 158, 11, 255)
    for px, py in [(m, m), (W - m, m), (m, H - m), (W - m, H - m)]:
        dx = 1 if px == m else -1
        dy = 1 if py == m else -1
        draw.line([(px, py), (px + dx * cb, py)], fill=c_color, width=3)
        draw.line([(px, py), (px, py + dy * cb)], fill=c_color, width=3)

    draw_wolf_crest(draw, 88, 68, scale=0.6, alpha=255, eye_color=(245, 158, 11))
    draw.text((125, 46), clean_server, fill=(255, 255, 255), font=font_server)
    draw.text((127, 80), "OFFICIAL FREE FIRE ESPORTS DISPATCH", fill=(245, 158, 11), font=font_badge)

    match_badge = f"MATCH #{match_no}"
    t_bbox = font_badge.getbbox(match_badge)
    tw = t_bbox[2] - t_bbox[0] + 32
    tx = W - m - 20 - tw
    ty = 48
    draw.rounded_rectangle([tx, ty, tx + tw, ty + 34], radius=8, fill=(245, 158, 11, 80), outline=(245, 158, 11, 200), width=1)
    draw.text((tx + 16, ty + 9), match_badge, fill=(255, 240, 200), font=font_badge)

    draw.line([(m + 20, 112), (W - m - 20, 112)], fill=(255, 255, 255, 30), width=1)
    draw.line([(m + 20, 112), (m + 250, 112)], fill=(245, 158, 11, 200), width=2)

    font_title = fit_text_font(f"MATCH #{match_no} - BATTLE FOR GLORY", W - 140, max_size=38, min_size=20)
    title_text = f"MATCH #{match_no} - BATTLE FOR GLORY"
    draw.text((62, 137), title_text, fill=(245, 158, 11, 90), font=font_title)
    draw.text((60, 135), title_text, fill=(255, 255, 255), font=font_title)

    sub_text = f"TOURNAMENT: {clean_tourn}  -  PREPARE YOUR SQUAD"
    draw.text((62, 188), sub_text, fill=(148, 163, 184), font=font_sub)

    cards = [
        ("MAP", clean_map, "Battlefield Zone", (0, 220, 255), (224, 242, 254)),
        ("SCHEDULE", clean_sched, "Drop Time", (245, 158, 11), (254, 243, 199)),
        ("MODE", "SQUAD BATTLE", "Competitive", (239, 68, 68), (254, 226, 226)),
        ("STATUS", "SCHEDULED", "Standby in Lobby", (16, 185, 129), (209, 250, 229)),
    ]

    card_y = 235
    card_h = 125
    card_gap = 18
    total_gap = card_gap * 3
    card_w = (W - (m * 2) - 40 - total_gap) // 4
    start_x = m + 20

    for i, (label, val, sub, accent_rgb, text_rgb) in enumerate(cards):
        cx = start_x + i * (card_w + card_gap)
        card_img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card_img)
        cdraw.rounded_rectangle([0, 0, card_w, card_h], radius=12, fill=(18, 18, 32, 230), outline=accent_rgb + (140,), width=2)
        cdraw.rounded_rectangle([0, 0, card_w, 5], radius=3, fill=accent_rgb + (255,))
        img.alpha_composite(card_img, (cx, card_y))

        draw.text((cx + 18, card_y + 18), label, fill=(148, 163, 184), font=font_card_lbl)
        font_card_val = fit_text_font(val, card_w - 36, max_size=20, min_size=13)
        draw.text((cx + 18, card_y + 44), val, fill=text_rgb, font=font_card_val)
        draw.text((cx + 18, card_y + 84), sub, fill=(100, 116, 139), font=font_card_sub)
        draw.ellipse([(cx + card_w - 24, card_y + 18), (cx + card_w - 14, card_y + 28)], fill=accent_rgb + (220,))

    fy = H - m - 42
    draw.line([(m + 20, fy), (W - m - 20, fy)], fill=(255, 255, 255, 25), width=1)
    draw.line([(W - m - 250, fy), (W - m - 20, fy)], fill=(245, 158, 11, 200), width=2)
    foot_text = f"ROOM ID & PASSWORD SENT VIA DM  -  HOST: {clean_server}"
    draw.text((m + 22, fy + 12), foot_text, fill=(148, 163, 184), font=font_footer)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def generate_wolf_icon(size: int = 256) -> io.BytesIO:
    """
    Generate a 256x256 circular wolf logo icon for Discord avatars / thumbnails.
    """
    img = Image.new("RGBA", (size, size), (10, 13, 24, 255))
    draw = ImageDraw.Draw(img)

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([(size // 4, size // 4), (3 * size // 4, 3 * size // 4)], fill=(0, 220, 255, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(size // 6))
    img.alpha_composite(glow)

    draw = ImageDraw.Draw(img)
    draw.ellipse([(6, 6), (size - 6, size - 6)], outline=(0, 230, 255, 200), width=3)
    draw_wolf_crest(draw, size // 2, size // 2, scale=size / 150)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
