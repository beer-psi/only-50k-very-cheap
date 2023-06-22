import logging
import logging.handlers
from asyncio import gather, to_thread
from datetime import time
from typing import TYPE_CHECKING

import aiohttp
import discord
from reader import make_reader, Entry, Reader
from bs4 import BeautifulSoup
from discord import Webhook
from discord.ext import commands, tasks
from discord.ext.commands import Cog, Context

from bot import BOT_DIR

if TYPE_CHECKING:
    from bot import VeryCheapBot


async def entry_to_embed(reader: Reader, entry: Entry) -> list[discord.Embed]:
    color = discord.Color.from_str(str(await to_thread(reader.get_tag, entry.feed_url, "color", "#000000")))
    
    icon_url = await to_thread(reader.get_tag, entry.feed_url, "icon_url", None)
    if icon_url is not None:
        icon_url = str(icon_url)

    soup = BeautifulSoup(str(entry.summary), "html.parser")
    description = soup.get_text()
    images = [x.get("src") for x in soup.select("img") if x.get("src") is not None][:10]
    
    embeds = []
    base_embed = discord.Embed(url=entry.link)
    
    embed0 = base_embed.copy()
    embed0.description = description
    embed0.timestamp = entry.published
    embed0.color = color
    embed0.set_image(url=images[0] if len(images) > 0 else None)
    embed0.set_author(name=entry.feed.title, url=entry.feed.link, icon_url=icon_url)
    embeds.append(embed0)

    for image in images[1:]:
        embed2 = base_embed.copy()
        embed2.set_image(url=image)
        embeds.append(embed2)    

    return embeds


class FeedCog(Cog):
    def __init__(self, bot: "VeryCheapBot") -> None:
        self.bot = bot 
        self.logger = logging.getLogger("cogs.feeds")
        self.reader: Reader = make_reader(str(BOT_DIR / "database" / "reader.sqlite3")) 

        self.logger.debug("Starting update_feeds task")
        self.logger.debug(self.update_feeds.start())
    
    async def cog_unload(self):
        self.update_feeds.cancel()
    
    # def get_reader(self, ctx: Context) -> Reader:
    #     id = ctx.author.id
    #     if ctx.guild is not None:
    #         id = ctx.guild.id
    #     return make_reader(str(BOT_DIR / "database" / "reader" / f"{id}.sqlite3"))

    @tasks.loop(time=[time(hour=x // 2, minute=x % 2 * 30 + 1) for x in range(48)])
    async def update_feeds(self, feed_url: str | None = None):
        if feed_url is not None:
            self.logger.debug(f"Updating feed {feed_url}")
        else:
            self.logger.debug("Updating all feeds (scheduled)")
        reader = self.reader
        await to_thread(reader.update_feeds)

        entries = await to_thread(reader.get_entries, feed=feed_url, read=False)
        webhooks = {}
        for entry in entries:
            channel_id = str(await to_thread(reader.get_tag, entry.feed_url, "channel_id", "-1"))
            if not channel_id.isdigit():
                continue

            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if channel is None or not isinstance(channel, discord.TextChannel):
                continue

            icon_url = await to_thread(reader.get_tag, entry.feed_url, "icon_url", None)
            if icon_url is not None:
                async with aiohttp.ClientSession() as session, session.get(icon_url) as resp:
                    icon = await resp.read()
            else:
                icon = None

            webhook = webhooks.get(entry.feed_url, None)
            if webhook is None:
                if (webhook_url := await to_thread(reader.get_tag, entry.feed_url, "webhook_url", None)) is not None:
                    webhook = Webhook.from_url(str(webhook_url))
                else:
                    webhook = await channel.create_webhook(name=entry.feed.title or "Feed", avatar=icon)
                    await to_thread(reader.set_tag, entry.feed_url, "webhook_url", webhook.url)
                webhooks[entry.feed_url] = webhook

            await webhook.send(embeds=await entry_to_embed(reader, entry), wait=True)
            await to_thread(reader.set_entry_read, entry, True)
        
    @update_feeds.error
    async def update_feeds_error(self, error):
        self.logger.error(error)

    @commands.group("feed", invoke_without_command=True)
    async def feed(self, ctx: Context):
        pass

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def add(self, ctx: Context, channel: discord.TextChannel, url: str):
        reader = self.reader
        await to_thread(reader.add_feed, url)
        await to_thread(reader.update_feed, url)
        await to_thread(reader.set_tag, url, "channel_id", str(channel.id))
        
        entries = await to_thread(reader.get_entries, feed=url, read=False)

        coros = [to_thread(reader.set_entry_read, entry, True) for entry in entries]
        await gather(*coros)
        await ctx.reply(f"Added feed {url} to channel {channel.mention}", mention_author=False)

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def remove(self, ctx: Context, url: str):
        reader = self.reader
        await to_thread(reader.delete_feed, url)
        await ctx.reply(f"Removed feed {url}", mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def list(self, ctx: Context):
        reader = self.reader
        
        embed = discord.Embed(title="Feeds")
        embed.description = ""

        feeds = await to_thread(reader.get_feeds)
        for feed in feeds:
            channel_id = str(await to_thread(reader.get_tag, feed.url, "channel_id", "-1"))
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
            entries = await to_thread(reader.get_entries)
            entry = next(entries, None)
        else:
            entries = await to_thread(reader.get_entries, feed=feed_url)
            entry = next(entries, None)
        
        if entry is None:
            await ctx.reply("No new entries", mention_author=False)
            return
        
        embeds = await entry_to_embed(reader, entry)
        await ctx.reply(embeds=embeds, mention_author=False)
    
    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def config(self, ctx: Context, feed_url: str, key: str, value: str):
        reader = self.reader
        await to_thread(reader.set_tag, feed_url, key, value)
        await ctx.reply(f"Set {key} to {value} for feed {feed_url}", mention_author=False)

async def setup(bot: "VeryCheapBot"):
    await bot.add_cog(FeedCog(bot))
