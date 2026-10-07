import io
import math
import os
import unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from config import DEVELOPER as _DEVELOPER
except Exception:  # pragma: no cover - config always available in-repo
    _DEVELOPER = "Joy"

DEV_TAG = f"DEVELOPED BY {_DEVELOPER.upper()}"

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
    foot_text = f"REGISTER NOW VIA SQUAD PANEL  -  HOSTED BY {clean_server}  -  {DEV_TAG}"
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
    foot_text = f"ROOM ID & PASSWORD SENT VIA DM  -  HOST: {clean_server}  -  {DEV_TAG}"
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


# ============================================================
# GOD-TIER CYBERPUNK SHARED HELPERS
# ============================================================

CYAN = (0, 230, 255)
MAGENTA = (255, 40, 186)
GOLD = (245, 158, 11)
RED = (239, 68, 68)
GREEN = (16, 185, 129)
PURPLE = (139, 92, 246)
GREY = (148, 163, 184)
DARK_PANEL = (16, 22, 36)


def _cyber_canvas(W, H, top=(8, 11, 22), bottom=(18, 10, 32)):
    """Vertical gradient background. Returns (img, draw)."""
    img = Image.new("RGBA", (W, H), top + (255,))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
    return img, draw


def _cyber_grid(img, W, H, step=45, alpha=8, diag=True):
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    for x in range(0, W, step):
        g.line([(x, 0), (x, H)], fill=(255, 255, 255, alpha), width=1)
    for y in range(0, H, step):
        g.line([(0, y), (W, y)], fill=(255, 255, 255, alpha), width=1)
    if diag:
        for off in range(-H, W + H, step * 3):
            g.line([(off, 0), (off + H, H)], fill=(0, 200, 255, max(3, alpha - 2)), width=1)
    img.alpha_composite(grid)


def _glow_spot(img, cx, cy, rx, ry, color, blur=60, alpha=50):
    spot = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s = ImageDraw.Draw(spot)
    s.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], fill=tuple(color) + (alpha,))
    spot = spot.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(spot)


def _corner_brackets(draw, W, H, m=20, color=CYAN + (255,), cb=28, width=3):
    draw.rectangle([m, m, W - m, H - m], outline=(255, 255, 255, 25), width=1)
    for px, py in [(m, m), (W - m, m), (m, H - m), (W - m, H - m)]:
        dx = 1 if px == m else -1
        dy = 1 if py == m else -1
        draw.line([(px, py), (px + dx * cb, py)], fill=color, width=width)
        draw.line([(px, py), (px, py + dy * cb)], fill=color, width=width)


def _dev_footer(draw, W, H, server_name, y=None, accent=GOLD + (255,)):
    """Standard Root LU footer bar with developer credit on every card."""
    if y is None:
        y = H - 52
    m = 20
    draw.line([(m + 20, y), (W - m - 20, y)], fill=(255, 255, 255, 25), width=1)
    draw.line([(W - m - 340, y), (W - m - 20, y)], fill=accent, width=2)
    clean_server = clean_text_for_image(server_name).upper() or "ROOT LU"
    text = f"{clean_server} - LEADING UNIVERSITY CSE - {DEV_TAG}"
    draw.text((m + 22, y + 12), text, fill=GREY, font=get_font(FONT_BOLD_PATH, 13))


def _pill(draw, x, y, text, font, fill, outline, text_color, pad=16, h=34):
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0] + pad * 2
    draw.rounded_rectangle([x, y, x + tw, y + h], radius=8, fill=fill, outline=outline, width=1)
    draw.text((x + pad, y + (h - (bbox[3] - bbox[1])) // 2 - bbox[1]),
              text, fill=text_color, font=font)
    return tw


def _panel(draw, x, y, w, h, accent, fill=DARK_PANEL + (235,), radius=12, top_stripe=True):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill,
                           outline=tuple(accent) + (160,), width=2)
    if top_stripe:
        draw.rounded_rectangle([x, y, x + w, y + 5], radius=3, fill=tuple(accent) + (255,))


def _barcode(draw, x, y, w, h, color=(0, 230, 255, 220)):
    """Decorative barcode stripes."""
    import random
    rng = random.Random(42)
    cx = x
    while cx < x + w:
        bw = rng.choice([2, 2, 3, 4, 5, 7])
        draw.rectangle([cx, y, cx + bw, y + h], fill=color)
        cx += bw + rng.choice([2, 3, 4, 6])


def _save_png(img) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _clamp_text(text, limit):
    text = clean_text_for_image(text)
    return text if len(text) <= limit else text[: limit - 1] + "~"


# ============================================================
# 3. PERSONALIZED VIP ROOM PASS
# ============================================================

def generate_room_pass_card(
    team_name: str,
    tournament_name: str,
    match_no: int,
    map_name: str,
    slot: int = 1,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """Personalized VIP room pass card. Credentials are NEVER rendered."""
    W, H = 1100, 500
    img, draw = _cyber_canvas(W, H, top=(6, 14, 26), bottom=(10, 24, 40))
    _cyber_grid(img, W, H)
    _glow_spot(img, 120, 110, 260, 150, CYAN, blur=70, alpha=40)
    _glow_spot(img, W - 100, H - 80, 240, 140, GOLD, blur=70, alpha=35)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=GOLD + (255,))

    # Left VIP stripe
    draw.rectangle([20, 20, 34, H - 20], fill=GOLD + (255,))

    f_badge = get_font(FONT_BOLD_PATH, 13)
    f_title = get_font(FONT_BOLD_PATH, 46)
    f_lbl = get_font(FONT_BOLD_PATH, 12)
    f_val = get_font(FONT_BOLD_PATH, 22)
    f_small = get_font(FONT_REGULAR_PATH, 13)

    draw.text((70, 52), "VIP ROOM PASS", fill=GOLD + (255,), font=f_title)
    draw.text((72, 112), "PERSONALIZED SQUAD ACCESS - OFFICIAL BATTLE PASS", fill=CYAN + (255,), font=f_badge)
    draw.line([(70, 140), (W - 60, 140)], fill=(255, 255, 255, 30), width=1)

    fields = [
        ("SQUAD", _clamp_text(team_name, 30).upper(), (224, 242, 254)),
        ("TOURNAMENT", _clamp_text(tournament_name, 30).upper(), (254, 243, 199)),
        ("MATCH", f"#{match_no}", (209, 250, 229)),
        ("MAP", _clamp_text(map_name, 16).upper(), (251, 207, 232)),
        ("LOBBY SLOT", f"SLOT {slot:02d}", (233, 213, 252)),
    ]
    fx, fy = 70, 170
    for i, (lbl, val, col) in enumerate(fields):
        cx = fx + (i % 3) * 330
        cy = fy + (i // 3) * 92
        _panel(draw, cx, cy, 300, 76, GOLD)
        draw.text((cx + 16, cy + 12), lbl, fill=GREY, font=f_lbl)
        draw.text((cx + 16, cy + 34), val, fill=col, font=f_val)

    # Access status + masked credentials notice
    ay = 372
    _panel(draw, 70, ay, 640, 62, GREEN)
    draw.text((90, ay + 10), "ACCESS STATUS", fill=GREY, font=f_lbl)
    draw.text((90, ay + 30), "GRANTED - CREDENTIALS DELIVERED VIA DM ONLY", fill=(134, 239, 172), font=f_val)
    _barcode(draw, 760, ay + 8, 270, 46)
    draw.text((760, ay + 58 - 4), "SCAN AT LOBBY", fill=GREY, font=f_small)

    _dev_footer(draw, W, H, server_name)
    return _save_png(img)


# ============================================================
# 4. 12-TEAM POINTS TABLE LEADERBOARD
# ============================================================

def generate_points_table_graphic(
    tournament_name: str,
    rows,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """12-team points table leaderboard graphic. rows: dicts with
    name, tag, matches, kills, pts."""
    W, H = 1200, 880
    img, draw = _cyber_canvas(W, H)
    _cyber_grid(img, W, H)
    _glow_spot(img, W // 2, -60, 420, 180, CYAN, blur=80, alpha=40)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H)

    f_title = get_font(FONT_BOLD_PATH, 44)
    f_sub = get_font(FONT_REGULAR_PATH, 18)
    f_head = get_font(FONT_BOLD_PATH, 15)
    f_row = get_font(FONT_BOLD_PATH, 20)
    f_row_sm = get_font(FONT_REGULAR_PATH, 16)

    draw.text((60, 42), "POINTS TABLE", fill=(255, 255, 255), font=f_title)
    draw.text((62, 100), f"{_clamp_text(tournament_name, 48).upper()} - TOP 12 SQUAD STANDINGS",
              fill=CYAN + (255,), font=f_sub)
    draw.line([(60, 140), (W - 60, 140)], fill=(255, 255, 255, 30), width=1)

    # Column headers
    hy = 156
    cols = [("RANK", 60), ("SQUAD", 170), ("M", 800), ("KILLS", 910), ("PTS", 1050)]
    for lbl, cx in cols:
        draw.text((cx, hy), lbl, fill=GREY, font=f_head)
    draw.line([(60, hy + 26), (W - 60, hy + 26)], fill=CYAN + (120,), width=2)

    medal_colors = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}
    row_h = 52
    start_y = hy + 40
    for i in range(12):
        ry = start_y + i * row_h
        if i % 2 == 0:
            draw.rectangle([50, ry - 6, W - 50, ry + row_h - 10], fill=(30, 41, 59, 255))
        rank = i + 1
        if rank in medal_colors:
            rc = medal_colors[rank]
            draw.ellipse([58, ry + 6, 92, ry + 40], fill=rc + (255,))
            rtxt = str(rank)
            bb = f_row.getbbox(rtxt)
            draw.text((75 - (bb[2] - bb[0]) / 2, ry + 23 - (bb[3] - bb[1]) / 2 - bb[1]),
                      rtxt, fill=(10, 10, 20), font=f_row)
        else:
            draw.text((66, ry + 10), f"{rank:02d}", fill=GREY, font=f_row_sm)
        if i < len(rows):
            row = rows[i]
            accent = medal_colors.get(rank, (224, 242, 254))
            name = _clamp_text(f"{row['name']} [{row.get('tag', '')}]", 34)
            draw.text((170, ry + 8), name, fill=accent, font=f_row)
            draw.text((800, ry + 10), str(row.get("matches", 0)), fill=(255, 255, 255), font=f_row_sm)
            draw.text((910, ry + 10), str(row.get("kills", 0)), fill=(252, 165, 165), font=f_row_sm)
            pts = str(row.get("pts", 0))
            pb = f_row.getbbox(pts)
            draw.text((1140 - (pb[2] - pb[0]), ry + 8), pts, fill=GOLD + (255,), font=f_row)
        else:
            draw.text((170, ry + 8), "- OPEN SLOT -", fill=(71, 85, 105), font=f_row_sm)

    _dev_footer(draw, W, H, server_name)
    return _save_png(img)


# ============================================================
# 5. BOOYAH WINNER CELEBRATION CARD
# ============================================================

def generate_booyah_card(
    team_name: str,
    tournament_name: str,
    points: int,
    kills: int = 0,
    server_name: str = "Root LU"
) -> io.BytesIO:
    W, H = 1200, 630
    img, draw = _cyber_canvas(W, H, top=(26, 16, 4), bottom=(52, 32, 6))
    _cyber_grid(img, W, H, step=50)
    _glow_spot(img, W // 2, 90, 480, 200, GOLD, blur=90, alpha=70)
    _glow_spot(img, 90, H - 60, 220, 130, (255, 90, 40), blur=70, alpha=40)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=GOLD + (255,))

    # Confetti
    import random
    rng = random.Random(7)
    for _ in range(90):
        cx = rng.randint(30, W - 30)
        cy = rng.randint(30, H - 80)
        col = rng.choice([GOLD, (255, 215, 0), (255, 120, 40), (255, 255, 255), (255, 180, 60)])
        draw.rectangle([cx, cy, cx + rng.randint(3, 7), cy + rng.randint(2, 5)], fill=col + (200,))

    # Trophy silhouette
    tx, ty = W // 2, 128
    cup = [(tx - 70, ty - 40), (tx + 70, ty - 40), (tx + 52, ty + 30), (tx - 52, ty + 30)]
    draw.polygon(cup, fill=(255, 200, 60, 230), outline=(255, 240, 160, 255))
    draw.rectangle([tx - 14, ty + 30, tx + 14, ty + 62], fill=(255, 200, 60, 230))
    draw.rectangle([tx - 44, ty + 62, tx + 44, ty + 76], fill=(255, 220, 120, 255))
    for hx in (-1, 1):
        draw.line([(tx + hx * 70, ty - 40), (tx + hx * 110, ty - 62), (tx + hx * 96, ty - 8), (tx + hx * 70, ty - 16)],
                  fill=(255, 220, 120, 255), width=6)

    f_booyah = get_font(FONT_BOLD_PATH, 96)
    f_tag = get_font(FONT_BOLD_PATH, 16)
    f_team = get_font(FONT_BOLD_PATH, 40)
    f_sub = get_font(FONT_REGULAR_PATH, 18)
    f_chip = get_font(FONT_BOLD_PATH, 20)

    text = "BOOYAH!"
    bb = f_booyah.getbbox(text)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) / 2 + 5, 196 + 5), text, fill=(120, 70, 0, 160), font=f_booyah)
    draw.text(((W - tw) / 2, 196), text, fill=(255, 230, 140), font=f_booyah)

    draw.text((W // 2 - 130, 316), "WINNER WINNER - CHICKEN DINNER", fill=GOLD + (255,), font=f_tag)
    team_txt = _clamp_text(team_name, 34).upper()
    f_team = fit_text_font(team_txt, W - 160, max_size=40, min_size=22)
    bb = f_team.getbbox(team_txt)
    draw.text(((W - (bb[2] - bb[0])) / 2, 352), team_txt, fill=(255, 255, 255), font=f_team)
    sub = f"CHAMPIONS OF {_clamp_text(tournament_name, 40).upper()}"
    draw.text((W // 2 - len(sub) * 4.6, 414), sub, fill=GREY, font=f_sub)

    chips = [("TOURNAMENT POINTS", f"{points} PTS", GOLD), ("TOTAL KILLS", f"{kills}", (255, 120, 120))]
    cx = W // 2 - 320
    for lbl, val, accent in chips:
        _panel(draw, cx, 456, 300, 76, accent)
        draw.text((cx + 18, 468), lbl, fill=GREY, font=get_font(FONT_BOLD_PATH, 12))
        draw.text((cx + 18, 492), val, fill=(255, 255, 255), font=f_chip)
        cx += 320

    _dev_footer(draw, W, H, server_name, y=H - 58, accent=GOLD + (255,))
    return _save_png(img)


# ============================================================
# 6. MVP PLAYER OF THE MATCH CARD
# ============================================================

def generate_mvp_card(
    player_ign: str,
    team_name: str,
    kills: int,
    damage: int = 0,
    placement: int = 1,
    server_name: str = "Root LU"
) -> io.BytesIO:
    W, H = 1200, 630
    img, draw = _cyber_canvas(W, H, top=(20, 8, 26), bottom=(44, 12, 52))
    _cyber_grid(img, W, H)
    _glow_spot(img, W // 2, 80, 460, 190, MAGENTA, blur=90, alpha=55)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=MAGENTA + (255,))

    f_mvp = get_font(FONT_BOLD_PATH, 110)
    f_lbl = get_font(FONT_BOLD_PATH, 15)
    f_ign = get_font(FONT_BOLD_PATH, 44)
    f_sub = get_font(FONT_REGULAR_PATH, 18)
    f_chip = get_font(FONT_BOLD_PATH, 22)

    text = "MVP"
    bb = f_mvp.getbbox(text)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) / 2 + 6, 66), text, fill=(90, 0, 70, 170), font=f_mvp)
    draw.text(((W - tw) / 2, 60), text, fill=(255, 120, 220), font=f_mvp)
    draw.text((W // 2 - 150, 196), "PLAYER OF THE MATCH", fill=MAGENTA + (255,), font=f_lbl)

    ign = _clamp_text(player_ign, 30).upper()
    f_ign = fit_text_font(ign, W - 200, max_size=44, min_size=24)
    bb = f_ign.getbbox(ign)
    draw.text(((W - (bb[2] - bb[0])) / 2, 240), ign, fill=(255, 255, 255), font=f_ign)
    draw.text((W // 2 - len(team_name) * 5.2, 306), f"SQUAD: {team_name.upper()}", fill=GREY, font=f_sub)

    chips = [
        ("KILLS", f"{kills}", (255, 110, 110)),
        ("DAMAGE", f"{damage:,}", CYAN),
        ("PLACEMENT", f"#{placement}", GOLD),
    ]
    cx = W // 2 - 480
    for lbl, val, accent in chips:
        _panel(draw, cx, 366, 300, 84, accent)
        draw.text((cx + 18, 380), lbl, fill=GREY, font=get_font(FONT_BOLD_PATH, 12))
        draw.text((cx + 18, 406), val, fill=(255, 255, 255), font=f_chip)
        cx += 320

    draw.text((W // 2 - 210, 486), "MOST VALUABLE PLAYER - OFFICIAL AWARD", fill=(216, 180, 252), font=f_sub)
    _dev_footer(draw, W, H, server_name, accent=MAGENTA + (255,))
    return _save_png(img)


# ============================================================
# 7. YOUTUBE/TWITCH LIVE STREAM CARD
# ============================================================

def generate_live_stream_card(
    tournament_name: str,
    match_no: int,
    map_name: str,
    platform: str = "YouTube",
    server_name: str = "Root LU"
) -> io.BytesIO:
    W, H = 1280, 720
    img, draw = _cyber_canvas(W, H, top=(30, 8, 10), bottom=(60, 12, 16))
    _cyber_grid(img, W, H, step=50)
    _glow_spot(img, W // 2, 100, 500, 220, RED, blur=90, alpha=60)
    _glow_spot(img, W - 120, H - 100, 260, 150, PURPLE, blur=70, alpha=40)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=RED + (255,))

    f_live = get_font(FONT_BOLD_PATH, 64)
    f_lbl = get_font(FONT_BOLD_PATH, 14)
    f_val = get_font(FONT_BOLD_PATH, 26)
    f_small = get_font(FONT_REGULAR_PATH, 15)
    f_cta = get_font(FONT_BOLD_PATH, 30)

    # LIVE badge with pulsing dot
    _pill(draw, 60, 48, "LIVE", f_live, (190, 30, 30, 255), (255, 120, 120, 255), (255, 255, 255), pad=24, h=76)
    draw.ellipse([212, 72, 240, 100], fill=(255, 60, 60, 255))
    _glow_spot(img, 226, 86, 40, 40, (255, 60, 60), blur=18, alpha=120)
    draw = ImageDraw.Draw(img)
    draw.text((280, 66), "ON AIR - OFFICIAL BROADCAST", fill=(255, 160, 160), font=f_val)

    draw.line([(60, 160), (W - 60, 160)], fill=(255, 255, 255, 30), width=1)

    title = f"MATCH #{match_no} - LIVE NOW"
    f_title = fit_text_font(title, W - 160, max_size=52, min_size=28)
    draw.text((60, 190), title, fill=(255, 255, 255), font=f_title)
    draw.text((62, 262), f"{_clamp_text(tournament_name, 44).upper()}", fill=(255, 120, 120), font=f_val)

    cards = [
        ("MAP", _clamp_text(map_name, 18).upper(), CYAN),
        ("PLATFORM", _clamp_text(platform, 14).upper(), PURPLE),
        ("MODE", "SQUAD BR", GOLD),
        ("STATUS", "STREAMING", (255, 80, 80)),
    ]
    cy = 330
    cw = (W - 120 - 3 * 18) // 4
    for i, (lbl, val, accent) in enumerate(cards):
        cx = 60 + i * (cw + 18)
        _panel(draw, cx, cy, cw, 110, accent)
        draw.text((cx + 18, cy + 16), lbl, fill=GREY, font=f_lbl)
        draw.text((cx + 18, cy + 44), val, fill=(255, 255, 255), font=f_val)
        draw.text((cx + 18, cy + 80), "ROOT LU BROADCAST", fill=(100, 116, 139), font=f_small)

    # CTA bar
    _panel(draw, 60, 480, W - 120, 90, (255, 60, 60), fill=(70, 14, 14, 240))
    draw.text((90, 500), "WATCH NOW - LIVE COVERAGE", fill=(255, 255, 255), font=f_cta)
    draw.text((90, 544), "CLICK THE LINK BUTTON - SUPPORT YOUR SQUAD ON STREAM", fill=(252, 165, 165), font=f_small)
    # Play triangle
    draw.polygon([(W - 150, 505), (W - 150, 545), (W - 105, 525)], fill=(255, 80, 80, 255))

    _dev_footer(draw, W, H, server_name, accent=RED + (255,))
    return _save_png(img)


# ============================================================
# 8. CYBERPUNK GAMER PASSPORT ID CARD
# ============================================================

def generate_player_passport_card(
    player_name: str,
    ign: str,
    uid: str,
    role: str = "Player",
    batch: str = "",
    section: str = "",
    kills: int = 0,
    matches: int = 0,
    server_name: str = "Root LU"
) -> io.BytesIO:
    W, H = 960, 600
    img, draw = _cyber_canvas(W, H, top=(6, 16, 22), bottom=(10, 26, 38))
    _cyber_grid(img, W, H, step=40)
    _glow_spot(img, W - 100, 80, 260, 160, CYAN, blur=70, alpha=45)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=CYAN + (255,), cb=24)

    f_head = get_font(FONT_BOLD_PATH, 26)
    f_badge = get_font(FONT_BOLD_PATH, 12)
    f_lbl = get_font(FONT_BOLD_PATH, 12)
    f_val = get_font(FONT_BOLD_PATH, 21)
    f_name = get_font(FONT_BOLD_PATH, 34)

    draw.text((56, 44), "ROOT LU GAMER PASSPORT", fill=(255, 255, 255), font=f_head)
    _pill(draw, W - 250, 40, "VERIFIED PLAYER", f_badge, (6, 60, 50, 220), (52, 211, 153, 255), (134, 239, 172))
    draw.text((58, 82), "OFFICIAL CYBERPUNK IDENTITY CARD - CSE ESPORTS DIVISION", fill=CYAN + (255,), font=f_badge)
    draw.line([(56, 112), (W - 56, 112)], fill=(255, 255, 255, 30), width=1)

    # Photo box with wolf crest
    px, py, ps = 70, 150, 190
    draw.rounded_rectangle([px, py, px + ps, py + ps], radius=14, fill=(10, 18, 30, 255),
                           outline=CYAN + (200,), width=2)
    draw_wolf_crest(draw, px + ps // 2, py + ps // 2 - 6, scale=1.15, alpha=255)
    draw.text((px + ps // 2 - 34, py + ps - 30), "PHOTO ID", fill=GREY, font=f_lbl)

    # Chip
    draw.rounded_rectangle([px + 220, py + 6, px + 300, py + 62], radius=8,
                           fill=(250, 204, 21, 220), outline=(255, 230, 120, 255), width=2)
    for lx in range(px + 228, px + 296, 12):
        draw.line([(lx, py + 10), (lx, py + 58)], fill=(180, 140, 10, 255), width=1)

    fields = [
        ("PLAYER", _clamp_text(player_name, 22).upper()),
        ("FREE FIRE IGN", _clamp_text(ign, 22).upper()),
        ("FREE FIRE UID", _clamp_text(uid, 20)),
        ("COMBAT ROLE", _clamp_text(role, 14).upper()),
        ("BATCH", _clamp_text(batch or "N/A", 8)),
        ("SECTION", _clamp_text(section or "N/A", 8)),
        ("KILLS", str(kills)),
        ("MATCHES", str(matches)),
    ]
    fx0, fy0 = px + 220, py + 80
    for i, (lbl, val) in enumerate(fields):
        cx = fx0 + (i % 2) * 330
        cy = fy0 + (i // 2) * 62
        draw.text((cx, cy), lbl, fill=GREY, font=f_lbl)
        draw.text((cx, cy + 20), val, fill=(224, 242, 254), font=f_val)

    # Bottom band
    by = H - 118
    draw.rounded_rectangle([56, by, W - 56, by + 56], radius=10, fill=(8, 40, 50, 240),
                           outline=CYAN + (140,), width=1)
    name_txt = _clamp_text(player_name, 24).upper()
    draw.text((80, by + 13), name_txt, fill=(255, 255, 255), font=f_name)
    _barcode(draw, W - 300, by + 12, 220, 32)

    _dev_footer(draw, W, H, server_name, y=H - 46)
    return _save_png(img)


# ============================================================
# 9. CERTIFICATE OF ESPORTS EXCELLENCE
# ============================================================

def generate_certificate_card(
    recipient_name: str,
    award: str,
    tournament_name: str,
    team_name: str,
    code: str,
    issued_at: str,
    server_name: str = "Root LU"
) -> io.BytesIO:
    W, H = 1600, 1000
    img, draw = _cyber_canvas(W, H, top=(12, 10, 24), bottom=(28, 20, 12))
    _glow_spot(img, W // 2, H // 2, 700, 420, GOLD, blur=120, alpha=30)
    draw = ImageDraw.Draw(img)

    # Ornate double border
    draw.rectangle([30, 30, W - 30, H - 30], outline=GOLD + (220,), width=4)
    draw.rectangle([48, 48, W - 48, H - 48], outline=GOLD + (120,), width=1)
    _corner_brackets(draw, W, H, m=48, color=GOLD + (255,), cb=40, width=4)

    f_small = get_font(FONT_BOLD_PATH, 16)
    f_cert = get_font(FONT_BOLD_PATH, 30)
    f_title = get_font(FONT_BOLD_PATH, 58)
    f_recipient = get_font(FONT_BOLD_PATH, 64)
    f_award = get_font(FONT_BOLD_PATH, 34)
    f_body = get_font(FONT_REGULAR_PATH, 22)


    draw.text((W // 2 - 210, 96), "ROOT LU - LEADING UNIVERSITY", fill=CYAN + (255,), font=f_cert)
    title = "CERTIFICATE OF ESPORTS EXCELLENCE"
    f_title = fit_text_font(title, W - 300, max_size=58, min_size=30)
    bb = f_title.getbbox(title)
    draw.text(((W - (bb[2] - bb[0])) / 2, 150), title, fill=(255, 245, 200), font=f_title)
    draw.line([(W // 2 - 320, 232), (W // 2 + 320, 232)], fill=GOLD + (200,), width=2)

    draw.text((W // 2 - 190, 272), "THIS CERTIFIES THAT", fill=GREY, font=f_small)
    recipient = _clamp_text(recipient_name, 30).upper()
    f_recipient = fit_text_font(recipient, W - 400, max_size=64, min_size=34)
    bb = f_recipient.getbbox(recipient)
    draw.text(((W - (bb[2] - bb[0])) / 2, 316), recipient, fill=(255, 255, 255), font=f_recipient)

    draw.text((W // 2 - 260, 412), "HAS BEEN AWARDED", fill=GREY, font=f_small)
    award_txt = _clamp_text(award, 44).upper()
    f_award = fit_text_font(award_txt, W - 400, max_size=34, min_size=20)
    bb = f_award.getbbox(award_txt)
    draw.text(((W - (bb[2] - bb[0])) / 2, 456), award_txt, fill=GOLD + (255,), font=f_award)

    body = (f"FOR OUTSTANDING PERFORMANCE IN THE { _clamp_text(tournament_name, 40).upper() } "
            f"REPRESENTING SQUAD { _clamp_text(team_name, 24).upper() }")
    draw.text((W // 2 - len(body) * 5.4, 530), body, fill=(203, 213, 225), font=f_body)

    # Details row
    dy = 610
    details = [("REGISTRY CODE", code.upper()), ("ISSUED (UTC)", str(issued_at)[:19]), ("SQUAD", _clamp_text(team_name, 20).upper())]
    cx = W // 2 - 540
    for lbl, val in details:
        _panel(draw, cx, dy, 340, 84, GOLD)
        draw.text((cx + 18, dy + 12), lbl, fill=GREY, font=f_small)
        draw.text((cx + 18, dy + 40), _clamp_text(val, 24), fill=(255, 255, 255), font=f_award.__class__ and get_font(FONT_BOLD_PATH, 22))
        cx += 360

    # Seal
    sx, sy = W // 2, 790
    seal = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)
    sd.ellipse([sx - 74, sy - 74, sx + 74, sy + 74], fill=(120, 20, 30, 220), outline=GOLD + (255,), width=4)
    sd.ellipse([sx - 58, sy - 58, sx + 58, sy + 58], outline=(255, 220, 120, 180), width=1)
    img.alpha_composite(seal)
    draw = ImageDraw.Draw(img)
    draw_wolf_crest(draw, sx, sy - 8, scale=0.62, alpha=255, eye_color=(255, 220, 120))
    draw.text((sx - 44, sy + 44), "ROOT LU", fill=(255, 230, 160), font=f_small)

    # Signature lines
    for lx in (W // 2 - 420, W // 2 + 80):
        draw.line([(lx, 880), (lx + 300, 880)], fill=(148, 163, 184, 200), width=1)
    draw.text((W // 2 - 420, 892), "TOURNAMENT DIRECTOR", fill=GREY, font=f_small)
    draw.text((W // 2 + 80, 892), DEV_TAG, fill=GREY, font=f_small)

    _dev_footer(draw, W, H, server_name, y=H - 52, accent=GOLD + (255,))
    return _save_png(img)


# ============================================================
# 10. 12-SLOT LOBBY DROPMAP & GRID
# ============================================================

def generate_slotlist_card(
    tournament_name: str,
    teams,
    max_teams: int = 12,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """12-slot lobby dropmap & grid. teams: list of dicts with name, tag,
    batch, section (optional)."""
    W, H = 1280, 840
    img, draw = _cyber_canvas(W, H)
    _cyber_grid(img, W, H)
    _glow_spot(img, W // 2, -40, 460, 160, CYAN, blur=80, alpha=40)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H)

    f_title = get_font(FONT_BOLD_PATH, 42)
    f_sub = get_font(FONT_REGULAR_PATH, 18)
    f_slot = get_font(FONT_BOLD_PATH, 18)
    f_team = get_font(FONT_BOLD_PATH, 21)
    f_small = get_font(FONT_REGULAR_PATH, 14)

    draw.text((56, 40), "LOBBY DROPMAP", fill=(255, 255, 255), font=f_title)
    draw.text((58, 96), f"{_clamp_text(tournament_name, 44).upper()} - 12 SQUAD BATTLE GRID",
              fill=CYAN + (255,), font=f_sub)
    draw.text((58, 126), f"{len(teams)}/{max_teams} SQUADS CONFIRMED - DROP ZONES LOCKED",
              fill=GREY, font=f_sub)
    draw.line([(56, 160), (W - 56, 160)], fill=(255, 255, 255, 30), width=1)

    cols, rows_n = 4, 3
    gap = 16
    gx, gy = 56, 184
    gw = (W - 112 - gap * (cols - 1)) // cols
    gh = (H - 184 - 70 - gap * (rows_n - 1)) // rows_n

    for slot in range(cols * rows_n):
        r, c = divmod(slot, cols)
        x = gx + c * (gw + gap)
        y = gy + r * (gh + gap)
        occupied = slot < len(teams)
        team = teams[slot] if occupied else None
        accent = CYAN if occupied else (71, 85, 105)
        _panel(draw, x, y, gw, gh, accent, fill=(13, 30, 40, 240) if occupied else (20, 24, 34, 220))
        draw.text((x + 16, y + 12), f"SLOT {slot + 1:02d}", fill=accent + (255,), font=f_slot)
        draw.text((x + gw - 92, y + 12), "DROP", fill=GREY, font=f_small)
        if team:
            nm = _clamp_text(f"{team['name']} [{team.get('tag', '')}]", 20)
            draw.text((x + 16, y + 44), nm, fill=(255, 255, 255), font=f_team)
            meta = f"BATCH {team.get('batch', '-')} / SEC {team.get('section', '-')}"
            draw.text((x + 16, y + 76), meta, fill=GREY, font=f_small)
            draw.text((x + 16, y + 98), "READY TO DROP", fill=(74, 222, 128), font=f_small)
        else:
            draw.text((x + 16, y + 56), "OPEN SLOT", fill=(100, 116, 139), font=f_team)
            draw.text((x + 16, y + 90), "AWAITING SQUAD", fill=(71, 85, 105), font=f_small)
        # Mini drop-zone crosshair
        mx, my = x + gw - 46, y + gh - 46
        draw.ellipse([mx - 22, my - 22, mx + 22, my + 22], outline=accent + (120,), width=2)
        draw.line([(mx - 30, my), (mx + 30, my)], fill=accent + (120,), width=1)
        draw.line([(mx, my - 30), (mx, my + 30)], fill=accent + (120,), width=1)

    _dev_footer(draw, W, H, server_name)
    return _save_png(img)


# ============================================================
# 11. HEAD-TO-HEAD VERSUS SQUAD CLASH POSTER
# ============================================================

def generate_matchup_clash_card(
    team_a: dict,
    team_b: dict,
    tournament_name: str,
    match_no: int = 1,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """Head-to-head VERSUS squad clash poster. team_a/team_b: dicts with
    name, tag, pts, kills, matches (optional)."""
    W, H = 1200, 700
    img, draw = _cyber_canvas(W, H, top=(6, 14, 22), bottom=(20, 8, 26))
    _cyber_grid(img, W, H)
    _glow_spot(img, 220, H // 2, 300, 260, CYAN, blur=80, alpha=50)
    _glow_spot(img, W - 220, H // 2, 300, 260, MAGENTA, blur=80, alpha=50)
    draw = ImageDraw.Draw(img)

    # Diagonal split background
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon([(0, 0), (W // 2 + 60, 0), (W // 2 - 60, H), (0, H)], fill=(0, 180, 220, 26))
    od.polygon([(W, 0), (W // 2 + 60, 0), (W // 2 - 60, H), (W, H)], fill=(255, 40, 186, 22))
    img.alpha_composite(overlay)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H)

    f_head = get_font(FONT_BOLD_PATH, 15)
    f_vs = get_font(FONT_BOLD_PATH, 120)
    f_tag = get_font(FONT_BOLD_PATH, 20)
    f_stat = get_font(FONT_BOLD_PATH, 20)
    f_lbl = get_font(FONT_BOLD_PATH, 12)

    draw.text((60, 44), f"{_clamp_text(tournament_name, 40).upper()} - MATCH #{match_no}",
              fill=(255, 255, 255), font=f_head)
    _pill(draw, W - 300, 36, "SQUAD CLASH", f_head, (60, 20, 70, 220), MAGENTA + (255,), (240, 170, 255))
    draw.line([(60, 76), (W - 60, 76)], fill=(255, 255, 255, 30), width=1)

    def draw_side(cx_center, team, accent, align_left):
        name = _clamp_text(team.get("name", "TBD"), 18).upper()
        f_team = fit_text_font(name, 440, max_size=40, min_size=22)
        bb = f_team.getbbox(name)
        tw = bb[2] - bb[0]
        nx = cx_center - tw - 30 if align_left else cx_center + 30
        ny = 150
        draw.text((nx + 3, ny + 3), name, fill=tuple(accent) + (90,), font=f_team)
        draw.text((nx, ny), name, fill=(255, 255, 255), font=f_team)
        tag = f"[{team.get('tag', '???')}]"
        draw.text((nx, ny + 52), tag, fill=tuple(accent) + (255,), font=f_tag)
        stats = [
            ("POINTS", str(team.get("pts", 0))),
            ("KILLS", str(team.get("kills", 0))),
            ("MATCHES", str(team.get("matches", 0))),
        ]
        sy = ny + 100
        for lbl, val in stats:
            _panel(draw, nx, sy, 200, 58, accent)
            draw.text((nx + 14, sy + 6), lbl, fill=GREY, font=f_lbl)
            draw.text((nx + 14, sy + 24), val, fill=(255, 255, 255), font=f_stat)
            sy += 70

    draw_side(W // 2 - 40, team_a, CYAN, align_left=True)
    draw_side(W // 2 + 40, team_b, MAGENTA, align_left=False)

    # Center VS medallion
    vx, vy = W // 2, 330
    med = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(med)
    md.ellipse([vx - 86, vy - 86, vx + 86, vy + 86], fill=(10, 10, 20, 245), outline=(255, 255, 255, 60), width=3)
    img.alpha_composite(med)
    draw = ImageDraw.Draw(img)
    _glow_spot(img, vx, vy, 90, 90, GOLD, blur=40, alpha=60)
    draw = ImageDraw.Draw(img)
    draw.ellipse([vx - 86, vy - 86, vx + 86, vy + 86], fill=(10, 10, 20, 235), outline=GOLD + (255,), width=3)
    bb = f_vs.getbbox("VS")
    draw.text((vx - (bb[2] - bb[0]) / 2, vy - (bb[3] - bb[1]) / 2 - bb[1] - 6), "VS",
              fill=(255, 255, 255), font=f_vs)
    # Diagonal slash lines
    draw.line([(W // 2 - 40, 120), (W // 2 + 40, 600)], fill=(255, 255, 255, 40), width=2)
    draw.line([(W // 2 + 40, 120), (W // 2 - 40, 600)], fill=(255, 255, 255, 25), width=1)

    draw.text((W // 2 - 260, 470), "HEAD TO HEAD - ONE SQUAD LEAVES THE ARENA", fill=GREY, font=f_head)
    _pill(draw, W // 2 - 110, 510, "WHO TAKES THE dub?".upper(), f_stat, (20, 40, 60, 220), CYAN + (255,), (200, 240, 255), pad=28, h=48)

    _dev_footer(draw, W, H, server_name)
    return _save_png(img)


# ============================================================
# 12. ALL-TIME HALL OF FAME & TROPHY CABINET
# ============================================================

def generate_hall_of_fame_card(
    entries,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """All-time hall of fame & trophy cabinet. entries: dicts with season,
    team_name, team_tag, achievement, points, kills."""
    W, H = 1280, 800
    img, draw = _cyber_canvas(W, H, top=(20, 14, 4), bottom=(40, 28, 6))
    _cyber_grid(img, W, H)
    _glow_spot(img, W // 2, 0, 500, 180, GOLD, blur=90, alpha=55)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=GOLD + (255,))

    f_title = get_font(FONT_BOLD_PATH, 52)
    f_sub = get_font(FONT_BOLD_PATH, 15)
    f_season = get_font(FONT_BOLD_PATH, 14)
    f_ach = get_font(FONT_REGULAR_PATH, 16)
    f_stat = get_font(FONT_BOLD_PATH, 18)

    title = "HALL OF FAME"
    bb = f_title.getbbox(title)
    draw.text(((W - (bb[2] - bb[0])) / 2, 44), title, fill=(255, 235, 170), font=f_title)
    draw.text((W // 2 - 220, 112), "ALL-TIME CHAMPIONS & TROPHY CABINET", fill=GOLD + (255,), font=f_sub)
    draw.line([(W // 2 - 300, 146), (W // 2 + 300, 146)], fill=GOLD + (160,), width=2)

    if not entries:
        draw.text((W // 2 - 260, 380), "NO LEGENDS INDUCTED YET - BE THE FIRST!",
                  fill=GREY, font=f_ach)
    else:
        shown = entries[:8]
        cols = 4 if len(shown) > 4 else len(shown)
        rows_n = math.ceil(len(shown) / cols)
        gap = 18
        gx, gy = 56, 176
        gw = (W - 112 - gap * (cols - 1)) // cols
        gh = (H - 176 - 70 - gap * (rows_n - 1)) // rows_n
        for i, e in enumerate(shown):
            r, c = divmod(i, cols)
            x = gx + c * (gw + gap)
            y = gy + r * (gh + gap)
            _panel(draw, x, y, gw, gh, GOLD)
            # Trophy icon
            tx, ty = x + gw // 2, y + 40
            draw.polygon([(tx - 20, ty - 16), (tx + 20, ty - 16), (tx + 14, ty + 8), (tx - 14, ty + 8)],
                         fill=(255, 215, 0, 240))
            draw.rectangle([tx - 5, ty + 8, tx + 5, ty + 20], fill=(255, 215, 0, 240))
            draw.rectangle([tx - 14, ty + 20, tx + 14, ty + 26], fill=(255, 235, 130, 255))
            season = _clamp_text(str(e.get("season", "")), 12).upper()
            draw.text((x + 14, y + gh - 66), season, fill=CYAN + (255,), font=f_season)
            nm = _clamp_text(f"{e.get('team_name', 'TBD')} [{e.get('team_tag', '')}]", 16)
            draw.text((x + 14, y + gh - 48), nm, fill=(255, 255, 255), font=get_font(FONT_BOLD_PATH, 17))
            ach = _clamp_text(str(e.get("achievement", "")), 22).upper()
            draw.text((x + 14, y + gh - 26), ach, fill=(255, 220, 130), font=f_stat)

    _dev_footer(draw, W, H, server_name, accent=GOLD + (255,))
    return _save_png(img)


# ============================================================
# 13. KNOCKOUT TOURNAMENT BRACKET TREE
# ============================================================

def generate_tournament_bracket_card(
    tournament_name: str,
    rounds,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """Knockout bracket tree. rounds: list of rounds; each round is a list of
    match dicts with team_a_name, team_b_name, team_a_tag, team_b_tag,
    winner_name, status."""
    n_rounds = max(1, len(rounds))
    col_w = 280
    box_w = 240
    box_h = 64
    W = 120 + n_rounds * col_w + 40
    max_slots = max((len(r) for r in rounds), default=1)
    v_gap = 26
    H = 190 + max_slots * (box_h + v_gap) + 90
    H = max(H, 560)

    img, draw = _cyber_canvas(W, H)
    _cyber_grid(img, W, H, step=50)
    _glow_spot(img, W // 2, 0, 500, 150, CYAN, blur=90, alpha=35)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H)

    f_title = fit_text_font("TOURNAMENT BRACKET", W - 200, max_size=40, min_size=22)
    draw.text((60, 40), "TOURNAMENT BRACKET", fill=(255, 255, 255), font=f_title)
    draw.text((62, 92), f"{_clamp_text(tournament_name, 50).upper()} - SINGLE ELIMINATION KNOCKOUT TREE",
              fill=CYAN + (255,), font=get_font(FONT_BOLD_PATH, 15))
    draw.line([(60, 130), (W - 60, 130)], fill=(255, 255, 255, 30), width=1)

    f_round = get_font(FONT_BOLD_PATH, 16)
    f_team = get_font(FONT_BOLD_PATH, 15)

    round_names = {1: "FINALS", 2: "SEMIFINALS", 3: "QUARTERFINALS"}
    centers = []
    for ri, round_matches in enumerate(rounds):
        cx = 80 + ri * col_w + box_w // 2
        # Round label
        if len(rounds) - ri <= 3:
            label = round_names.get(len(rounds) - ri, f"ROUND {ri + 1}")
        else:
            label = f"ROUND {ri + 1}"
        bb = f_round.getbbox(label)
        draw.text((cx - (bb[2] - bb[0]) / 2, 142), label, fill=GOLD + (255,), font=f_round)

        n = len(round_matches)
        total_h = n * box_h + (n - 1) * v_gap
        start_y = 180 + max(0, (max_slots * (box_h + v_gap) - total_h) // 2)
        match_centers = []
        for mi, m in enumerate(round_matches):
            bx = 80 + ri * col_w
            by = start_y + mi * (box_h + v_gap)
            match_centers.append((bx, by, bx + box_w // 2, by + box_h // 2))
            accent = GREEN if m.get("status") in ("completed", "bye") else CYAN
            if m.get("status") == "bye":
                accent = GOLD
            _panel(draw, bx, by, box_w, box_h, accent, fill=(12, 20, 30, 245), radius=8, top_stripe=False)
            draw.line([(bx, by + box_h // 2), (bx + box_w, by + box_h // 2)],
                      fill=(255, 255, 255, 25), width=1)
            a_name = _clamp_text(m.get("team_a_name") or ("BYE" if m.get("status") == "bye" and not m.get("team_a_name") else "TBD"), 16)
            b_name = _clamp_text(m.get("team_b_name") or ("BYE" if m.get("status") == "bye" and not m.get("team_b_name") else "TBD"), 16)
            a_win = m.get("winner_name") and m.get("team_a_name") and m["winner_name"] == m.get("team_a_name")
            b_win = m.get("winner_name") and m.get("team_b_name") and m["winner_name"] == m.get("team_b_name")
            draw.text((bx + 12, by + 9), a_name, fill=(134, 239, 172) if a_win else (224, 242, 254), font=f_team)
            draw.text((bx + 12, by + box_h // 2 + 9), b_name, fill=(134, 239, 172) if b_win else (251, 207, 232), font=f_team)
            if a_win or b_win:
                draw.text((bx + box_w - 34, by + 9), "W", fill=GOLD + (255,), font=f_round)
        centers.append(match_centers)

    # Connectors between rounds
    for ri in range(len(rounds) - 1):
        for mi in range(len(centers[ri])):
            if mi % 2 == 0 and mi + 1 < len(centers[ri]):
                _, _, x1, y1 = centers[ri][mi]
                _, _, _, y2 = centers[ri][mi + 1]
                x2, y2b, _, _ = centers[ri + 1][mi // 2]
                mid_x = (x1 + x2 - box_w // 2) // 2 + box_w // 2
                draw.line([(x1, y1), (mid_x, y1)], fill=(255, 255, 255, 45), width=2)
                draw.line([(x1, y2), (mid_x, y2)], fill=(255, 255, 255, 45), width=2)
                draw.line([(mid_x, y1), (mid_x, y2)], fill=(255, 255, 255, 45), width=2)
                draw.line([(mid_x, (y1 + y2) // 2), (x2 - box_w // 2, (y1 + y2) // 2)],
                          fill=(255, 255, 255, 45), width=2)

    _dev_footer(draw, W, H, server_name)
    return _save_png(img)


# ============================================================
# 14. LIVE COMBAT KILL FEED GRAPHIC
# ============================================================

def generate_killfeed_card(
    events,
    server_name: str = "Root LU",
    match_label: str = "LIVE MATCH"
) -> io.BytesIO:
    """Live combat kill feed graphic. events: list of dicts with keys
    player, action (e.g. 'ELIMINATED'), detail (optional)."""
    W, H = 1280, 640
    img, draw = _cyber_canvas(W, H, top=(24, 8, 8), bottom=(44, 12, 12))
    _cyber_grid(img, W, H, step=50)
    _glow_spot(img, W // 2, 0, 480, 140, RED, blur=80, alpha=45)
    draw = ImageDraw.Draw(img)
    _corner_brackets(draw, W, H, color=RED + (255,))

    f_title = get_font(FONT_BOLD_PATH, 34)
    f_lbl = get_font(FONT_BOLD_PATH, 13)
    f_player = get_font(FONT_BOLD_PATH, 24)
    f_action = get_font(FONT_BOLD_PATH, 24)
    f_detail = get_font(FONT_REGULAR_PATH, 18)

    draw.text((60, 40), "LIVE KILL FEED", fill=(255, 255, 255), font=f_title)
    draw.ellipse([268, 56, 292, 80], fill=(255, 60, 60, 255))
    draw.text((312, 52), _clamp_text(match_label, 40).upper(), fill=(255, 130, 130), font=f_lbl)
    draw.line([(60, 100), (W - 60, 100)], fill=(255, 255, 255, 30), width=1)

    if not events:
        draw.text((W // 2 - 240, 300), "NO ELIMINATIONS REPORTED YET", fill=GREY, font=f_detail)
    else:
        row_h = 46
        start_y = 122
        for i, ev in enumerate(events[:10]):
            ry = start_y + i * row_h
            if i % 2 == 0:
                draw.rectangle([52, ry - 6, W - 52, ry + row_h - 12], fill=(255, 255, 255, 6))
            player = _clamp_text(str(ev.get("player", "???")), 22).upper()
            action = _clamp_text(str(ev.get("action", "ELIMINATED")), 14).upper()
            detail = _clamp_text(str(ev.get("detail", "")), 30)
            draw.text((70, ry), player, fill=CYAN + (255,), font=f_player)
            ax = 70 + f_player.getbbox(player)[2] + 18
            draw.text((ax, ry), action, fill=(255, 90, 90), font=f_action)
            if detail:
                dx = ax + f_action.getbbox(action)[2] + 18
                draw.text((dx, ry + 4), detail, fill=GREY, font=f_detail)
            # Skull marker
            kx = W - 110
            draw.polygon([(kx, ry + 4), (kx + 18, ry + 4), (kx + 18, ry + 18), (kx + 9, ry + 24), (kx, ry + 18)],
                         fill=(255, 90, 90, 200))
            draw.ellipse([kx + 4, ry + 8, kx + 7, ry + 11], fill=(24, 8, 8, 255))
            draw.ellipse([kx + 11, ry + 8, kx + 14, ry + 11], fill=(24, 8, 8, 255))

    _dev_footer(draw, W, H, server_name, accent=RED + (255,))
    return _save_png(img)


# ============================================================
# 15. BROADCAST LOWER-THIRD NEWS TICKER
# ============================================================

def generate_broadcast_lowerthird_card(
    headline: str,
    subline: str = "",
    server_name: str = "Root LU"
) -> io.BytesIO:
    """Broadcast lower-third news ticker bar (1920x220)."""
    W, H = 1920, 220
    img, draw = _cyber_canvas(W, H, top=(10, 12, 20), bottom=(16, 18, 30))
    draw = ImageDraw.Draw(img)

    # Main bar
    draw.rectangle([0, 40, W, 150], fill=(8, 10, 18, 245))
    draw.rectangle([0, 40, W, 46], fill=RED + (255,))
    draw.rectangle([0, 144, W, 150], fill=RED + (255,))

    # LIVE block
    draw.rectangle([0, 40, 190, 150], fill=(190, 24, 24, 255))
    f_live = get_font(FONT_BOLD_PATH, 52)
    bb = f_live.getbbox("LIVE")
    draw.text((95 - (bb[2] - bb[0]) / 2, 95 - (bb[3] - bb[1]) / 2 - bb[1] - 8), "LIVE",
              fill=(255, 255, 255), font=f_live)
    draw.ellipse([160, 60, 176, 76], fill=(255, 90, 90, 255))

    # Headline + subline
    f_head = fit_text_font(_clamp_text(headline, 60).upper(), 1300, max_size=44, min_size=22)
    draw.text((220, 56), _clamp_text(headline, 60).upper(), fill=(255, 255, 255), font=f_head)
    if subline:
        draw.text((222, 112), _clamp_text(subline, 80), fill=(160, 200, 255), font=get_font(FONT_REGULAR_PATH, 20))

    # Brand block right
    draw.rectangle([W - 360, 40, W, 150], fill=(0, 120, 140, 200))
    clean_server = clean_text_for_image(server_name).upper() or "ROOT LU"
    draw.text((W - 340, 62), clean_server, fill=(255, 255, 255), font=get_font(FONT_BOLD_PATH, 30))
    draw.text((W - 340, 104), DEV_TAG, fill=(170, 240, 250), font=get_font(FONT_BOLD_PATH, 15))

    # Ticker strip
    draw.rectangle([0, 150, W, H], fill=(4, 6, 12, 255))
    ticker = f" {clean_server} ESPORTS - LEADING UNIVERSITY CSE - FREE FIRE TOURNAMENT BROADCAST - {DEV_TAG} - "
    f_t = get_font(FONT_BOLD_PATH, 20)
    offset = 20
    while offset < W:
        draw.text((offset, 172), ticker[:90], fill=(120, 200, 220), font=f_t)
        offset += 1180
    draw.rectangle([0, 150, W, 154], fill=CYAN + (160,))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ============================================================
# 16. FUT STYLE ULTIMATE PLAYER TRADING CARD
# ============================================================

def generate_ultimate_player_card(
    player_name: str,
    team_tag: str,
    role: str,
    ovr: int,
    attributes: dict,
    kills: int = 0,
    matches: int = 0,
    wins: int = 0,
    server_name: str = "Root LU"
) -> io.BytesIO:
    """FUT-style Ultimate Player Trading Card with OVR & 6 attributes
    (PAC, SHO, PAS, DRI, DEF, PHY)."""
    W, H = 600, 900
    img, draw = _cyber_canvas(W, H, top=(6, 10, 26), bottom=(14, 8, 34))
    _cyber_grid(img, W, H, step=36)
    _glow_spot(img, W // 2, 120, 300, 220, CYAN, blur=80, alpha=45)
    draw = ImageDraw.Draw(img)

    # Card body with clipped top
    m = 22
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([m, m + 60, W - m, H - m], radius=26, fill=(10, 16, 32, 250),
                         outline=CYAN + (255,), width=3)
    cd.polygon([(m + 26, m + 60), (m + 60, m), (W - m - 60, m), (W - m - 26, m + 60)],
               fill=(10, 16, 32, 250))
    cd.line([(m + 60, m), (m + 26, m + 60)], fill=CYAN + (255,), width=3)
    cd.line([(W - m - 60, m), (W - m - 26, m + 60)], fill=CYAN + (255,), width=3)
    img.alpha_composite(card)
    draw = ImageDraw.Draw(img)

    f_big = get_font(FONT_BOLD_PATH, 84)
    f_med = get_font(FONT_BOLD_PATH, 26)
    f_lbl = get_font(FONT_BOLD_PATH, 15)
    f_attr = get_font(FONT_BOLD_PATH, 30)
    f_name = get_font(FONT_BOLD_PATH, 34)
    f_small = get_font(FONT_REGULAR_PATH, 15)

    # OVR block
    draw.text((m + 26, m + 84), str(int(ovr)), fill=(255, 255, 255), font=f_big)
    draw.text((m + 30, m + 178), "OVR", fill=CYAN + (255,), font=f_med)
    draw.line([(m + 26, m + 214), (m + 150, m + 214)], fill=GOLD + (255,), width=3)
    draw.text((m + 28, m + 226), _clamp_text(role, 12).upper(), fill=GOLD + (255,), font=f_med)

    # Team tag top-right
    tag = _clamp_text(team_tag, 10).upper()
    tb = f_med.getbbox(tag)
    draw.text((W - m - 30 - (tb[2] - tb[0]), m + 96), tag, fill=(255, 255, 255), font=f_med)
    draw.text((W - m - 30 - (tb[2] - tb[0]), m + 134), "ROOT LU", fill=GREY, font=f_small)

    # Player silhouette
    px, py = W // 2, m + 330
    silhouette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(silhouette)
    sd.ellipse([px - 58, py - 78, px + 58, py + 38], fill=(0, 220, 255, 40))
    sd.ellipse([px - 34, py - 56, px + 34, py + 12], fill=(120, 200, 220, 90))
    sd.ellipse([px - 62, py - 8, px + 62, py + 96], fill=(120, 200, 220, 70))
    silhouette = silhouette.filter(ImageFilter.GaussianBlur(2))
    img.alpha_composite(silhouette)
    draw = ImageDraw.Draw(img)

    # 6 attributes in 2 columns x 3 rows
    keys = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
    ax0, ay0 = m + 40, 520
    for i, k in enumerate(keys):
        cx = ax0 + (i % 2) * 250
        cy = ay0 + (i // 2) * 78
        val = int(attributes.get(k, 0))
        draw.text((cx, cy), k, fill=GREY, font=f_lbl)
        draw.text((cx, cy + 20), str(val), fill=(255, 255, 255), font=f_attr)
        # Attribute bar
        bw = 190
        draw.rectangle([cx, cy + 58, cx + bw, cy + 64], fill=(40, 50, 70, 255))
        draw.rectangle([cx, cy + 58, cx + int(bw * val / 99), cy + 64], fill=CYAN + (255,))

    # Name band
    ny = H - m - 118
    draw.rectangle([m + 4, ny, W - m - 4, ny + 64], fill=(0, 0, 0, 120))
    name = _clamp_text(player_name, 20).upper()
    f_name = fit_text_font(name, W - 2 * m - 40, max_size=34, min_size=20)
    bb = f_name.getbbox(name)
    draw.text(((W - (bb[2] - bb[0])) / 2, ny + 14), name, fill=(255, 255, 255), font=f_name)

    # Stat strip
    stats = f"KILLS {kills}   MATCHES {matches}   WINS {wins}"
    draw.text((W // 2 - len(stats) * 4.4, ny + 76), stats, fill=GREY, font=f_small)
    draw.text((W // 2 - len("ULTIMATE TEAM") * 4.6, H - m - 26), "ROOT LU ULTIMATE TEAM - " + DEV_TAG,
              fill=(100, 220, 240), font=f_small)

    return _save_png(img)


# ============================================================
# 17. CYBERPUNK WANTED: DEAD OR ELIMINATED BOUNTY POSTER
# ============================================================

def generate_bounty_poster(
    target_name: str,
    amount: int,
    placer_name: str,
    reason: str = "",
    server_name: str = "Root LU"
) -> io.BytesIO:
    """Cyberpunk 'WANTED: DEAD OR ELIMINATED' bounty poster."""
    W, H = 900, 1200
    img, draw = _cyber_canvas(W, H, top=(26, 6, 6), bottom=(48, 10, 10))
    _cyber_grid(img, W, H, step=42, diag=True)
    _glow_spot(img, W // 2, 620, 380, 420, RED, blur=100, alpha=45)
    draw = ImageDraw.Draw(img)

    # Red distressed frame
    m = 26
    draw.rectangle([m, m, W - m, H - m], outline=(220, 40, 40, 255), width=6)
    draw.rectangle([m + 12, m + 12, W - m - 12, H - m - 12], outline=(220, 40, 40, 140), width=2)
    for px, py in [(m, m), (W - m, m), (m, H - m), (W - m, H - m)]:
        dx = 1 if px == m else -1
        dy = 1 if py == m else -1
        draw.line([(px, py), (px + dx * 44, py)], fill=(255, 80, 80, 255), width=5)
        draw.line([(px, py), (px, py + dy * 44)], fill=(255, 80, 80, 255), width=5)

    f_wanted = get_font(FONT_BOLD_PATH, 110)
    f_sub = get_font(FONT_BOLD_PATH, 30)
    f_target = get_font(FONT_BOLD_PATH, 54)
    f_amt = get_font(FONT_BOLD_PATH, 64)
    f_lbl = get_font(FONT_BOLD_PATH, 16)
    f_small = get_font(FONT_REGULAR_PATH, 18)

    text = "WANTED"
    bb = f_wanted.getbbox(text)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) / 2 + 5, 76), text, fill=(90, 0, 0, 180), font=f_wanted)
    draw.text(((W - tw) / 2, 70), text, fill=(255, 70, 70), font=f_wanted)

    sub = "DEAD OR ELIMINATED"
    sb = f_sub.getbbox(sub)
    draw.text(((W - (sb[2] - sb[0])) / 2, 200), sub, fill=(255, 200, 200), font=f_sub)
    draw.line([(W // 2 - 260, 248), (W // 2 + 260, 248)], fill=(220, 40, 40, 255), width=3)

    # Target silhouette portrait frame
    px, py, pw, ph = W // 2 - 170, 290, 340, 300
    draw.rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], outline=(255, 80, 80, 255), width=4)
    draw.rectangle([px, py, px + pw, py + ph], fill=(12, 4, 6, 255))
    draw_wolf_crest(draw, px + pw // 2, py + ph // 2 - 20, scale=2.1, alpha=200, eye_color=(255, 60, 60))
    # Scan lines
    for ly in range(py + 10, py + ph, 22):
        draw.line([(px + 8, ly), (px + pw - 8, ly)], fill=(255, 60, 60, 40), width=1)

    target = _clamp_text(target_name, 24).upper()
    f_target = fit_text_font(target, W - 120, max_size=54, min_size=28)
    bb = f_target.getbbox(target)
    draw.text(((W - (bb[2] - bb[0])) / 2, 630), target, fill=(255, 255, 255), font=f_target)
    draw.text((W // 2 - 130, 700), "WANTED IN ALL BATTLE ROYALE LOBBIES", fill=GREY, font=f_lbl)

    # Reward
    ry = 760
    draw.rounded_rectangle([W // 2 - 300, ry, W // 2 + 300, ry + 110], radius=14,
                           fill=(60, 10, 10, 240), outline=(255, 180, 40, 255), width=3)
    draw.text((W // 2 - 110, ry + 14), "REWARD", fill=(255, 220, 120), font=f_sub)
    amt = f"{int(amount):,} COINS"
    ab = f_amt.getbbox(amt)
    draw.text(((W - (ab[2] - ab[0])) / 2, ry + 48), amt, fill=(255, 235, 150), font=f_amt)

    # Issuer + reason
    draw.text((W // 2 - 200, 910), f"ISSUED BY: {_clamp_text(placer_name, 22).upper()}",
              fill=(200, 210, 225), font=f_small)
    if reason:
        draw.text((W // 2 - 260, 944), f'"{_clamp_text(reason, 46)}"', fill=(160, 170, 190), font=f_small)
    _barcode(draw, W // 2 - 130, 990, 260, 44, color=(255, 80, 80, 200))
    draw.text((W // 2 - 90, 1044), "BRING THEM DOWN", fill=(255, 120, 120), font=f_lbl)

    _dev_footer(draw, W, H, server_name, y=H - 52, accent=(255, 80, 80, 255))
    return _save_png(img)
