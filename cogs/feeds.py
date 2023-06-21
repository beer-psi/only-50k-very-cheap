import asyncio
from typing import TYPE_CHECKING

import discord
from reader import make_reader, Entry, Reader
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from discord.ext.commands import Cog, Context

from bot import BOT_DIR

if TYPE_CHECKING:
    from bot import VeryCheapBot


def entry_to_embed(reader: Reader, entry: Entry) -> list[discord.Embed]:
    color = discord.Color.from_str(str(reader.get_tag(entry.feed_url, "color", "#000000")))
    
    icon_url = reader.get_tag(entry.feed_url, "icon_url", None)
    if icon_url is not None:
        icon_url = str(icon_url)

    soup = BeautifulSoup(str(entry.summary), "html.parser")
    description = soup.get_text()
    images = [x.get("src") for x in soup.select("img") if x.get("src") is not None][:10]
    
    embeds = []
    embed = (
        discord.Embed(
            url=entry.link,
            description=description,
            timestamp=entry.published,
            color=color,
        )
            .set_image(url=images[0] if len(images) > 0 else None)
            .set_author(name=entry.feed.title, url=entry.feed.link, icon_url=icon_url) 
    )
    embeds.append(embed)

    for image in images[1:]:
        embed2 = embed.copy()
        embed2.set_image(url=image)
        embeds.append(embed2)    

    return embeds


class FeedCog(Cog):
    def __init__(self, bot: "VeryCheapBot") -> None:
        self.bot = bot 
        self.reader = make_reader(str(BOT_DIR / "database" / "reader.sqlite3")) 
    
    # def get_reader(self, ctx: Context) -> Reader:
    #     id = ctx.author.id
    #     if ctx.guild is not None:
    #         id = ctx.guild.id
    #     return make_reader(str(BOT_DIR / "database" / "reader" / f"{id}.sqlite3"))

    @tasks.loop(minutes=5)   
    async def update_feeds(self, feed_url: str | None = None):
        reader = self.reader
        reader.update_feeds()

        entries = reader.get_entries(feed=feed_url, read=False)
        for entry in entries:
            channel_id = str(reader.get_tag(entry.feed_url, "channel_id", "-1"))
            if not channel_id.isdigit():
                continue

            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            await channel.send(embeds=entry_to_embed(reader, entry))
            reader.set_entry_read(entry, True)
        
    @commands.group("feed", invoke_without_command=True)
    async def feed(self, ctx: Context):
        pass

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def add(self, ctx: Context, channel: discord.TextChannel, url: str):
        reader = self.reader
        reader.add_feed(url)
        reader.update_feed(url)
        reader.set_tag(url, "channel_id", str(channel.id))
        
        for entry in reader.get_entries(feed=url, read=False):
            reader.set_entry_read(entry, True)
        await ctx.reply(f"Added feed {url} to channel {channel.mention}", mention_author=False)

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def remove(self, ctx: Context, url: str):
        reader = self.reader
        reader.delete_feed(url)
        await ctx.reply(f"Removed feed {url}", mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def list(self, ctx: Context):
        reader = self.reader
        
        embed = discord.Embed(title="Feeds")
        embed.description = ""
        for feed in reader.get_feeds():
            channel_id = str(reader.get_tag(feed.url, "channel_id", "-1"))
            embed.description += f"{feed.url} posting to <#{channel_id}>\n"
        await ctx.reply(embed=embed, mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def update(self, ctx: Context, feed_url: str | None = None):
        if feed_url is None:
            await self.update_feeds()
            await ctx.reply("Updated all feeds", mention_author=False)
        else:
            await self.update_feeds(feed_url)
            await ctx.reply(f"Updated feed {feed_url}", mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def latest(self, ctx: Context, feed_url: str | None = None):
        reader = self.reader
        if feed_url is None:
            entry = next(reader.get_entries(), None)
        else:
            entry = next(reader.get_entries(feed=feed_url), None)
        
        if entry is None:
            await ctx.reply("No new entries", mention_author=False)
            return
        
        embeds = entry_to_embed(reader, entry)
        await ctx.reply(embeds=embeds, mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def config(self, ctx: Context, feed_url: str, key: str, value: str):
        reader = self.reader
        reader.set_tag(feed_url, key, value)
        await ctx.reply(f"Set {key} to {value} for feed {feed_url}", mention_author=False)

async def setup(bot: "VeryCheapBot"):
    await bot.add_cog(FeedCog(bot))
