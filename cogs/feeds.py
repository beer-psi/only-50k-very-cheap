import logging
import logging.handlers
from asyncio import gather, to_thread
from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from reader import make_reader, Entry, Reader
from bs4 import BeautifulSoup
from discord import Webhook
from discord.ext import commands, tasks
from discord.ext.commands import Cog, Context
from discord.utils import escape_markdown

from bot import BOT_DIR

if TYPE_CHECKING:
    from bot import VeryCheapBot


async def entry_to_embed(reader: Reader, entry: Entry) -> list[discord.Embed]:
    color = discord.Color.from_str(
        str(await to_thread(reader.get_tag, entry.feed_url, "color", "#000000"))
    )

    icon_url = await to_thread(reader.get_tag, entry.feed_url, "icon_url", None)
    if icon_url is not None:
        icon_url = str(icon_url)

    soup = BeautifulSoup(str(entry.summary), "html.parser")
    for br in soup.find_all("br"):
        br.insert_before("\\n")
    for p in soup.find_all("p"):
        p.insert_before("\\n")
    for a in soup.find_all("a"):
        content = a.get_text(strip=True)
        if not content.startswith("#"):
            a.replace_with(a.get("href"))
    description = soup.get_text(strip=True).replace("\\n", "\n").replace("\n ", "\n").replace("nitter.beerpsi.tech", "twitter.com")

    images = []
    for tag in soup.select("video, img"):
        if tag.name == "video" and (img := tag.get("poster")) is not None:
            images.append(img)
        elif (img := tag.get("src")) is not None:
            images.append(img)
    images = images[:4]

    embeds = []
    base_embed = discord.Embed(url=entry.link)

    embed0 = base_embed.copy()
    embed0.description = escape_markdown(description)
    embed0.timestamp = entry.published
    embed0.color = color
    embed0.set_image(url=images[0] if len(images) > 0 else None)

    author = entry.author
    author_link = entry.feed.link
    if author is None:
        author = entry.feed.title or ""
    if author.startswith("@"):
        author_link = f"https://twitter.com/{author[1:]}"
    embed0.set_author(name=author, url=author_link, icon_url=icon_url)
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

    @tasks.loop(time=[time(hour=x // 6, minute=x % 6 * 10 + 5) for x in range(144)])
    async def update_feeds(self, feed_url: str | None = None, scheduled=True):
        if feed_url is not None:
            await to_thread(
                self.logger.info,
                f"Updating feed {feed_url}" + (" (scheduled)" if scheduled else ""),
            )
        else:
            await to_thread(
                self.logger.info,
                "Updating all feeds" + (" (scheduled)" if scheduled else ""),
            )
        reader = self.reader
        await to_thread(reader.update_feeds, workers=10)

        entries = reversed(list(await to_thread(reader.get_entries, feed=feed_url, read=False)))
        webhooks = {}
        current_latest_by_feed: dict[str, datetime] = {}
        new_latest_by_feed: dict[str, datetime] = {}
        new_post_count = 0
        
        for entry in entries:
            if (latest_timestamp := current_latest_by_feed.get(entry.feed_url)) is None:
                latest_timestamp = str(
                    await to_thread(
                        reader.get_tag,
                        entry.feed_url,
                        "latest_timestamp",
                        "1970-01-01T00:00:00Z",
                    )
                )
                latest_timestamp = datetime.fromisoformat(latest_timestamp)
                current_latest_by_feed[entry.feed_url] = latest_timestamp

            if entry.published is not None and entry.published < latest_timestamp:
                await to_thread(reader.set_entry_read, entry, True)
                continue

            new_post_count += 1
            channel_id = str(
                await to_thread(reader.get_tag, entry.feed_url, "channel_id", "-1")
            )
            if not channel_id.isdigit():
                await to_thread(
                    self.logger.warn,
                    f"Invalid channel_id {channel_id} for feed {entry.feed_url}",
                )
                continue

            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            
            link_name = "Posted"
            link = (entry.link or "").replace("nitter.beerpsi.tech", "twitter.com")
            if entry.title is not None:
                if entry.title.startswith("RT by"):
                    link_name = "Retweeted"
            if channel is None or (
                not isinstance(channel, discord.TextChannel)
                and not isinstance(channel, discord.Thread)
                and not isinstance(channel, discord.StageChannel)
                and not isinstance(channel, discord.VoiceChannel)
            ):
                await to_thread(
                    self.logger.warn,
                    f"Channel {channel_id} not found or is not a text channel for feed {entry.feed_url}",
                )
                continue

            if not bool(
                await to_thread(reader.get_tag, entry.feed_url, "send_by_webhook", True)
            ):
                await channel.send(
                    embeds=await entry_to_embed(reader, entry),
                    content=f"[{link_name}]({link})",
                )
                await to_thread(reader.set_entry_read, entry, True)
                continue

            webhook = webhooks.get(channel_id, None)
            if webhook is None:
                if (
                    webhook_url := await to_thread(
                        reader.get_tag, (), f"webhook_url_{channel_id}", None
                    )
                ) is not None:
                    await to_thread(
                        self.logger.debug,
                        f"Found webhook_url {webhook_url} for channel {channel_id}",
                    )
                    webhook = Webhook.from_url(str(webhook_url), client=self.bot)
                else:
                    await to_thread(
                        self.logger.debug, f"Creating webhook for channel {channel_id}"
                    )
                    webhook = await channel.create_webhook(name="Feed giá rẻ")
                    await to_thread(
                        reader.set_tag, (), f"webhook_url_{channel_id}", webhook.url
                    )
                webhooks[channel_id] = webhook

            icon_url = await to_thread(reader.get_tag, entry.feed_url, "icon_url", None)

            await webhook.send(
                username=entry.feed.title
                if entry.feed.title is not None
                else "Feed giá rẻ",
                avatar_url=str(icon_url) if icon_url is not None else None,
                content=f"[{link_name}]({link})",
                embeds=await entry_to_embed(reader, entry),
                wait=True,
            )
            await to_thread(reader.set_entry_read, entry, True)

            if entry.published is not None:
                if (
                    (new_ts := new_latest_by_feed.get(entry.feed_url)) is None
                    or entry.published > new_ts
                ):
                    new_latest_by_feed[entry.feed_url] = entry.published

        for feed_url, latest in new_latest_by_feed.items():
            await to_thread(reader.set_tag, feed_url, "latest_timestamp", latest.isoformat())
        await to_thread(self.logger.info, f"Pushed {new_post_count} new posts")

    @update_feeds.error
    async def update_feeds_error(self, error):
        self.logger.error(error)

    @commands.group("feed", invoke_without_command=True)
    async def feed(self, ctx: Context):
        pass

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def add(
        self,
        ctx: Context,
        channel: discord.TextChannel
        | discord.VoiceChannel
        | discord.StageChannel
        | discord.Thread,
        url: str,
    ):
        reader = self.reader
        await to_thread(reader.add_feed, url)
        await to_thread(reader.update_feed, url)
        await to_thread(reader.set_tag, url, "channel_id", str(channel.id))

        entries = list(await to_thread(reader.get_entries, feed=url, read=False))

        if entries[0].published is not None:
            await to_thread(reader.set_tag, url, "latest_timestamp", entries[0].published.isoformat())

        coros = [to_thread(reader.set_entry_read, entry, True) for entry in entries]
        await gather(*coros)
        await ctx.reply(
            f"Added feed {url} to channel {channel.mention}", mention_author=False
        )

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
            channel_id = str(
                await to_thread(reader.get_tag, feed.url, "channel_id", "-1")
            )
            embed.description += f"{feed.url} posting to <#{channel_id}>\n"
        await ctx.reply(embed=embed, mention_author=False)

    @feed.command()
    @commands.has_permissions(manage_channels=True)
    async def update(self, ctx: Context, feed_url: str | None = None):
        async with ctx.typing():
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

        actual_value = value
        if key == "send_by_webhook":
            actual_value = value.lower() in ["true", "1", "yes", "y", "on"]

        await to_thread(reader.set_tag, feed_url, key, actual_value)
        await ctx.reply(
            f"Set {key} to {actual_value} for feed {feed_url}", mention_author=False
        )


async def setup(bot: "VeryCheapBot"):
    await bot.add_cog(FeedCog(bot))
