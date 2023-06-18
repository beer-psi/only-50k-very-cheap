import discord
import random
import re
from discord.ext import commands
from discord.ext.commands import Context

from bot import VeryCheapBot


very_cheap = re.compile(
    r"(?P<only>m[oỗ]i|c[oó])\s+(?P<price>\d+\s*(?:k|m|b|ng[aà]n|ngh[iì]n|tr(?:i[eệ]u)?|t[iỉ]|t[yỷ])(?:\s*[dđ][oồ]ng|₫)?)",
    re.IGNORECASE,
)
very_cheap_2 = re.compile(
    r"(?P<price>\d+\s*(?:k|m|b|ng[aà]n|ngh[iì]n|tr(?:i[eệ]u)?|t[iỉ]|t[yỷ])(?:\s*[dđ][oồ]ng|₫)?)\s*(?P<only>th[oô]i|ch[uứ] m[aấ]y)",
    re.IGNORECASE,
)
funny = ["rất rẻ", "quá ít", "rất ít"]


def process_homoglyphs(content: str) -> str:
    content = re.sub(
        r"[0️⃣OoΟοσОоՕօסه٥ھہە۵߀०০੦૦ଠ୦௦ం౦ಂ೦ംഠ൦ං๐໐ဝ၀ჿዐᴏᴑℴⲞⲟⵔ〇ꓳꬽﮦﮧﮨﮩﮪﮫﮬﮭﻩﻪﻫﻬ０Ｏｏ𐊒𐊫𐐄𐐬𐓂𐓪𐔖𑓐𑢵𑣈𑣗𑣠𝐎𝐨𝑂𝑜𝑶𝒐𝒪𝓞𝓸𝔒𝔬𝕆𝕠𝕺𝖔𝖮𝗈𝗢𝗼𝘖𝘰𝙊𝙤𝙾𝚘𝚶𝛐𝛔𝛰𝜊𝜎𝜪𝝄𝝈𝝤𝝾𝞂𝞞𝞸𝞼𝟎𝟘𝟢𝟬𝟶𞸤𞹤𞺄🯰]",
        "0",
        content,
    )
    content = re.sub(
        r"[1️⃣Iil|ıƖǀɩɪ˛ͺΙιІіӀӏ׀וןا١۱ߊᎥᛁιℐℑℓℹⅈⅠⅰⅼ∣⍳⏽Ⲓⵏꓲꙇꭵﺍﺎ１Ｉｉｌ￨𐊊𐌉𐌠𑣃𖼨𝐈𝐢𝐥𝐼𝑖𝑙𝑰𝒊𝒍𝒾𝓁𝓘𝓲𝓵𝔦𝔩𝕀𝕚𝕝𝕴𝖎𝖑𝖨𝗂𝗅𝗜𝗶𝗹𝘐𝘪𝘭𝙄𝙞𝙡𝙸𝚒𝚕𝚤𝚰𝛊𝛪𝜄𝜤𝜾𝝞𝝸𝞘𝞲𝟏𝟙𝟣𝟭𝟷𞣇𞸀𞺀🯱]",
        "1",
        content,
    )
    content = re.sub(r"2️⃣ƧϨᒿꙄꛯꝚ２𝟐𝟚𝟤𝟮𝟸🯲", "2", content)
    content = re.sub(r"[3️⃣ƷȜЗӠⳌꝪꞫ３𑣊𖼻𝈆𝟑𝟛𝟥𝟯𝟹🯳]", "3", content)
    content = re.sub(r"[4️⃣Ꮞ４𑢯𝟒𝟜𝟦𝟰𝟺🯴]", "4", content)
    content = re.sub(r"[5️⃣Ƽ５𑢻𝟓𝟝𝟧𝟱𝟻🯵]", "5", content)
    content = re.sub(r"[6️⃣бᏮⳒ６𑣕𝟔𝟞𝟨𝟲𝟼🯶]", "6", content)
    content = re.sub(r"[7️⃣７𐓒𑣆𝈒𝟕𝟟𝟩𝟳𝟽🯷]", "7", content)
    content = re.sub(r"[8️⃣Ȣȣ৪੪ଃ８𐌚𝟖𝟠𝟪𝟴𝟾𞣋🯸]", "8", content)
    content = re.sub(r"[9️⃣৭੧୨൭ⳊꝮ９𑢬𑣌𑣖𝟗𝟡𝟫𝟵𝟿🯹]", "9", content)
    return content


class LunaCog(commands.Cog, name="Events"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    @commands.command()
    async def test(self, ctx: Context, *, content: str):
        message = ctx.message
        if very_cheap.search(content) is not None:
            await message.add_reaction("✅")
        elif very_cheap_2.search(content) is not None:
            await message.add_reaction("✅")
        else:
            await message.add_reaction("❌")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != int(self.bot.cfg["LUNA_USER_ID"]):
            return

        if message.content.startswith("l>"):
            return

        if (m := very_cheap.search(message.content)) is not None:
            only = m.group("only")
            price = process_homoglyphs(m.group("price"))
            await message.reply(
                f"{only} {price} ({random.choice(funny)})", mention_author=False
            )
        elif (m := very_cheap_2.search(message.content)) is not None:
            only = m.group("only")
            price = process_homoglyphs(m.group("price"))
            await message.reply(
                f"{price} {only} ({random.choice(funny)})", mention_author=False
            )


async def setup(bot: VeryCheapBot):
    await bot.add_cog(LunaCog(bot))
