import re

import discord
from discord.ext import commands

from bot import VeryCheapBot

GITHUB_ISSUE_REGEX = re.compile(r"(?P<username>[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38})/(?P<repo>[a-zA-Z0-9-_]{0,100})#(?P<issue>\d+)")


class MiscCog(commands.Cog, name="Miscellaneous"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content
        if (m := GITHUB_ISSUE_REGEX.search(content)) is not None:
            username = m.group("username")
            repo = m.group("repo")
            issue = m.group("issue")
            await message.channel.send(f"https://github.com/{username}/{repo}/issues/{issue}")


async def setup(bot: VeryCheapBot):
    await bot.add_cog(MiscCog(bot))
