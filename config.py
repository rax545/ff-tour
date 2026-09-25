import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN', '')
GUILD_ID = int(os.getenv('GUILD_ID', '0') or 0)
ADMIN_ROLE_ID = int(os.getenv('ADMIN_ROLE_ID', '0') or 0)
MANAGER_ROLE_ID = int(os.getenv('MANAGER_ROLE_ID', '0') or 0)
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/esports.sqlite3')
KILL_POINT = int(os.getenv('KILL_POINT', '1') or 1)
PLACEMENT_POINTS = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

# Server Branding - 𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥
SERVER_NAME = os.getenv('SERVER_NAME', '𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥')
BRAND = os.getenv('BRAND', '𝐖𝐡𝐢𝐭𝐞 𝐖𝐨𝐥𝐟 𝐆𝐥𝐨𝐛𝐚𝐥')
SERVER_NAME_CLEAN = 'WHITE WOLF GLOBAL'
TAGLINE = 'Elite Free Fire Esports League'
