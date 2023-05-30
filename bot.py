import random
import re

import discord
from discord.ext.commands import Bot
from dotenv import dotenv_values

intents = discord.Intents.default()
intents.message_content = True

cfg = dotenv_values()
bot = Bot(command_prefix="!", intents=intents)

very_cheap = re.compile(r"(có(?: mỗi)?|mỗi) (\d+)(\s*k|\s*nghìn(?: đồng)?)", re.IGNORECASE)
funny = ["rất rẻ", "quá ít", "rất ít"]

@bot.event
async def on_message(message: discord.Message):
    if message.author.id != int(cfg["LUNA_USER_ID"]):
        return
    
    m = very_cheap.search(message.content)
    if m is None:
        return
    
    only = m.group(1)
    price = m.group(2)
    denomination = m.group(3)
    await message.reply(f"{only} {price}{denomination} ({random.choice(funny)})", mention_author=False)

bot.run(cfg["TOKEN"])
