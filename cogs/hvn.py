import discord
from discord.ext import commands

from bot import VeryCheapBot
from scrapers import sources


class HVNCog(commands.Cog, name="HVN"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        embed = None

        for source in sources:
            if (url := source.find_url(message.content)) is None:
                continue
            
            try:
                details = await source.get_manga_details(url)
                embed = details.to_discord_embed()
            except Exception as e:
                return
        
        if embed is not None:
            await message.reply(embed=embed, mention_author=False)


async def setup(bot: VeryCheapBot):
    await bot.add_cog(HVNCog(bot))
