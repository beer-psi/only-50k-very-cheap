import random
import re

import discord
from discord.ext.commands import Bot
from dotenv import dotenv_values

intents = discord.Intents.default()
intents.message_content = True

cfg = dotenv_values()
bot = Bot(command_prefix="!", intents=intents)

very_cheap = re.compile(r"(c[óo](?: m[ỗo]i)?|m[ỗo]i) (\S+?)(\s*(?:k|m|b|ng[àa]n|ngh[ìi]n|tri[ệe]u|t[iỉ]|t[yỷ])(?: [dđ][oồ]ng)?)\b", re.IGNORECASE)
very_cheap_2 = re.compile(r"(\S+?)(\s*(?:k|m|b|ng[àa]n|ngh[ìi]n|tri[ệe]u|t[iỉ]|t[yỷ])(?: [dđ][oồ]ng)?) (th[oô]i|ch[uứ] m[aấ]y)")
funny = ["rất rẻ", "quá ít", "rất ít"]

def process_homoglyphs(content: str) -> str:
    content = re.sub(r"[0️⃣OoΟοσОоՕօסه٥ھہە۵߀०০੦૦ଠ୦௦ం౦ಂ೦ംഠ൦ං๐໐ဝ၀ჿዐᴏᴑℴⲞⲟⵔ〇ꓳꬽﮦﮧﮨﮩﮪﮫﮬﮭﻩﻪﻫﻬ０Ｏｏ𐊒𐊫𐐄𐐬𐓂𐓪𐔖𑓐𑢵𑣈𑣗𑣠𝐎𝐨𝑂𝑜𝑶𝒐𝒪𝓞𝓸𝔒𝔬𝕆𝕠𝕺𝖔𝖮𝗈𝗢𝗼𝘖𝘰𝙊𝙤𝙾𝚘𝚶𝛐𝛔𝛰𝜊𝜎𝜪𝝄𝝈𝝤𝝾𝞂𝞞𝞸𝞼𝟎𝟘𝟢𝟬𝟶𞸤𞹤𞺄🯰]", "0", content)
    content = re.sub(r"[1️⃣Iil|ıƖǀɩɪ˛ͺΙιІіӀӏ׀וןا١۱ߊᎥᛁιℐℑℓℹⅈⅠⅰⅼ∣⍳⏽Ⲓⵏꓲꙇꭵﺍﺎ１Ｉｉｌ￨𐊊𐌉𐌠𑣃𖼨𝐈𝐢𝐥𝐼𝑖𝑙𝑰𝒊𝒍𝒾𝓁𝓘𝓲𝓵𝔦𝔩𝕀𝕚𝕝𝕴𝖎𝖑𝖨𝗂𝗅𝗜𝗶𝗹𝘐𝘪𝘭𝙄𝙞𝙡𝙸𝚒𝚕𝚤𝚰𝛊𝛪𝜄𝜤𝜾𝝞𝝸𝞘𝞲𝟏𝟙𝟣𝟭𝟷𞣇𞸀𞺀🯱]", "1", content)
    content = re.sub(r"2️⃣ƧϨᒿꙄꛯꝚ２𝟐𝟚𝟤𝟮𝟸🯲", "2", content)
    content = re.sub(r"[3️⃣ƷȜЗӠⳌꝪꞫ３𑣊𖼻𝈆𝟑𝟛𝟥𝟯𝟹🯳]", "3", content)
    content = re.sub(r"[4️⃣Ꮞ４𑢯𝟒𝟜𝟦𝟰𝟺🯴]", "4", content)
    content = re.sub(r"[5️⃣Ƽ５𑢻𝟓𝟝𝟧𝟱𝟻🯵]", "5", content)
    content = re.sub(r"[6️⃣бᏮⳒ６𑣕𝟔𝟞𝟨𝟲𝟼🯶]", "6", content)
    content = re.sub(r"[7️⃣７𐓒𑣆𝈒𝟕𝟟𝟩𝟳𝟽🯷]", "7", content)
    content = re.sub(r"[8️⃣Ȣȣ৪੪ଃ８𐌚𝟖𝟠𝟪𝟴𝟾𞣋🯸]", "8", content)
    content = re.sub(r"[9️⃣৭੧୨൭ⳊꝮ９𑢬𑣌𑣖𝟗𝟡𝟫𝟵𝟿🯹]", "9", content)
    return content

@bot.event
async def on_message(message: discord.Message):
    if message.author.id != int(cfg["LUNA_USER_ID"]):
        return
    
    if (m := very_cheap.search(message.content)) is not None:
        only = m.group(1)
        price = process_homoglyphs(m.group(2))
        denomination = m.group(3)
        await message.reply(f"{only} {price}{denomination} ({random.choice(funny)})", mention_author=False)
    elif (m := very_cheap_2.search(message.content)) is not None:
        only = m.group(3)
        price = process_homoglyphs(m.group(1))
        denomination = m.group(2)
        await message.reply(f"{price}{denomination} {only} ({random.choice(funny)})", mention_author=False)
    

if __name__ == "__main__":
    bot.run(cfg["TOKEN"])
