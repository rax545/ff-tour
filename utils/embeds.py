import discord
from config import BRAND

def base(title,description='',color=discord.Color.from_rgb(124,58,237)):
    e=discord.Embed(title=title,description=description,color=color,timestamp=discord.utils.utcnow()); e.set_footer(text=BRAND+' • Esports Management'); return e
def ok(msg): return base('✅ Done',msg,discord.Color.green())
def err(msg): return base('❌ Error',msg,discord.Color.red())
def info(msg): return base('ℹ️ Information',msg,discord.Color.blurple())
