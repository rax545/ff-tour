import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# .env লোডার
for candidate in [
    BASE_DIR / '.env',
    BASE_DIR / '.env.txt',
    BASE_DIR.parent / '.env',
    BASE_DIR.parent / '.env.txt',
]:
    if candidate.is_file():
        load_dotenv(dotenv_path=candidate)
        break
else:
    load_dotenv()

# বট টোকেন
TOKEN = (
    os.getenv('DISCORD_TOKEN')
    or os.getenv('TOKEN')
    or os.getenv('BOT_TOKEN')
    or ''
).strip().strip('"').strip("'")

GUILD_ID = int(os.getenv('GUILD_ID', '0') or 0)


# মাল্টিপল রোল হ্যান্ডলার
def _parse_role_ids(val: str) -> set:
    if not val:
        return set()
    result = set()
    for item in str(val).split(","):
        cleaned = item.strip()
        if cleaned.isdigit() and int(cleaned) > 0:
            result.add(int(cleaned))
    return result


ADMIN_ROLE_IDS = _parse_role_ids(os.getenv('ADMIN_ROLE_ID', '0'))
MANAGER_ROLE_IDS = _parse_role_ids(os.getenv('MANAGER_ROLE_ID', '0'))
STAFF_ROLE_IDS = ADMIN_ROLE_IDS | MANAGER_ROLE_IDS

ADMIN_ROLE_ID = next(iter(ADMIN_ROLE_IDS), 0)
MANAGER_ROLE_ID = next(iter(MANAGER_ROLE_IDS), 0)

DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/esports.sqlite3')
KILL_POINT = int(os.getenv('KILL_POINT', '1') or 1)
PLACEMENT_POINTS = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

# সার্ভার ব্র্যান্ডিং - 𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥
SERVER_NAME = os.getenv('SERVER_NAME', '𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥')
BRAND = os.getenv('BRAND', '𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥')
SERVER_NAME_CLEAN = 'WHITE WOLF GLOBAL'
TAGLINE = 'Elite Free Fire Esports League'

# 🔥 এই লাইনটির জন্য এরর দিচ্ছিল (এখন ফিক্সড):
DEVELOPER = os.getenv('DEVELOPER', 'Joy')
