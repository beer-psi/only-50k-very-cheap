import asyncio
import re

import discord
from discord.ext import commands

from bot import VeryCheapBot
from scrapers import sources


URL_REGEX = re.compile(r"https?:\/\/[^\s<]+[^<.,:;\"'>)|\]\s]")


class HVNCog(commands.Cog, name="HVN"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.author == self.bot.user:
            return

        if not URL_REGEX.search(message.content):
            return

        embed = None

        async def worker(source):
            if (url := source.find_url(message.content)) is None:
                return
            return await source.get_manga_details(url)

        result = next(
            (
                x
                for x in await asyncio.gather(*[worker(source) for source in sources])
                if x is not None
            ),
            None,
        )
        if result is not None:
            embed = result.to_discord_embed()
            return await message.reply(embed=embed, mention_author=False)


async def setup(bot: VeryCheapBot):
    await bot.add_cog(HVNCog(bot))
