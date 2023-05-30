import random
import re

import discord
from discord.ext.commands import Bot
from dotenv import dotenv_values

intents = discord.Intents.default()
intents.message_content = True

cfg = dotenv_values()
bot = Bot(command_prefix="!", intents=intents)

very_cheap = re.compile(r"có(?: mỗi)? ([1-9]\d{1,2})k")
funny = ["rất rẻ", "quá ít", "rất ít"]

@bot.event
async def on_message(message: discord.Message):
    if message.author.id != int(cfg["LUNA_USER_ID"]):
        return
    
    m = very_cheap.search(message.content, re.IGNORECASE)
    if m is None:
        return
    
    price = m.group(1)
    await message.reply(f"có {price}k ({random.choice(funny)})", mention_author=False)

bot.run(cfg["TOKEN"])
