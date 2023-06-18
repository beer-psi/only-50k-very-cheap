import discord
from discord.ext import commands

from bot import VeryCheapBot
from scrapers import start_sources, sources


class HVNCog(commands.Cog, name="HVN"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.author == self.bot.user:
            return

        embed = None

        async with message.channel.typing():
            for source in sources:
                if (url := source.find_url(message.content)) is None:
                    continue

                details = await source.get_manga_details(url)
                embed = details.to_discord_embed()
                break

            if embed is not None:
                return await message.reply(embed=embed, mention_author=False)


async def setup(bot: VeryCheapBot):
    await start_sources()
    await bot.add_cog(HVNCog(bot))
