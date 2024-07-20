import asyncio
from datetime import UTC, time, datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from aiohttp import web
from discord.activity import Game
from discord.http import Route
from discord.ext import commands, tasks
from discord.ext.commands import Context
from discord.utils import _from_json, escape_markdown

from bot import VeryCheapBot


router = web.RouteTableDef()


@router.post("/confessions")
async def confessions(request: web.Request) -> web.Response:
    bot: VeryCheapBot = request.config_dict["bot"]
    thread_id: int = request.config_dict["thread_id"]
    channel = bot.get_channel(thread_id)
    if channel is None:
        channel = await bot.fetch_channel(thread_id)

    content_type = request.headers.get("Content-Type")
    if content_type == "application/json":
        params = await request.json(loads=_from_json)
    elif content_type in ["application/x-www-form-urlencoded", "multipart/form-data"]:
        params = await request.post()
    else:
        raise web.HTTPBadRequest(reason="Invalid Content-Type")

    if "timestamp" not in params or "content" not in params or "index" not in params:
        raise web.HTTPBadRequest(reason="Missing parameters")

    timestamp = params["timestamp"]
    content = params["content"]
    index = params["index"]

    if (
        not isinstance(timestamp, str)
        or not isinstance(content, str)
        or not isinstance(index, (str, int))
    ):
        raise web.HTTPBadRequest(reason="Invalid parameters")

    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError:
        raise web.HTTPBadRequest(reason="Invalid timestamp")

    embed = discord.Embed(
        title=f"confession #{index}",
        description=escape_markdown(content),
        timestamp=parsed_timestamp,
    )

    asyncio.create_task(channel.send(embed=embed))

    raise web.HTTPNoContent


async def on_response_prepare(_: web.Request, response: web.StreamResponse):
    response.headers.add("x-content-type-options", "nosniff")
    if response.headers.get("server"):
        del response.headers["server"]


class DemonsCog(commands.Cog, name="Demons", command_attrs=dict(hidden=True)):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.queue_loop.start()

        if str_thread_id := self.bot.cfg.get("CONFESSIONS_CHANNEL_ID"):
            thread_id = int(str_thread_id)

            self.web_app = web.Application()
            self.web_app.on_response_prepare.append(on_response_prepare)

            self.web_app.add_routes(router)

            self.web_app["bot"] = self.bot
            self.web_app["thread_id"] = thread_id

            _ = asyncio.ensure_future(
                web._run_app(
                    self.web_app,
                    port=6969,
                    host="0.0.0.0",
                )
            )

    async def cog_unload(self) -> None:
        self.queue_loop.stop()

        if hasattr(self, "web_app"):
            await self.web_app.shutdown()
            await self.web_app.cleanup()

    async def cog_check(self, ctx: Context) -> bool:
        user_id = ctx.author.id
        role_ids = [str(role.id) for role in ctx.author.roles]
        return (
            str(user_id) in self.bot.cfg["SOCIETY_USER_IDS"]
            or any(x in self.bot.cfg["SOCIETY_ROLE_IDS"] for x in role_ids)
            or (
                isinstance(ctx.author, discord.Member)
                and ctx.author.guild_permissions.administrator
            )
        )

    @commands.command(name="toggleinvite", aliases=["tinvite"])
    @commands.has_guild_permissions(manage_messages=True)
    async def toggleinvite(self, ctx: Context, enabled: bool | None = None):
        if not isinstance(ctx.channel, discord.Thread):
            raise commands.errors.CheckFailure(
                "This command can only be used in threads."
            )

        new_invitable = not ctx.channel.invitable if enabled is None else enabled

        await self.bot.http.request(
            Route("PATCH", "/channels/{thread_id}", thread_id=ctx.channel.id),
            json={"invitable": new_invitable},
        )

        await ctx.reply(f'Set "Anyone can invite" to {new_invitable} for this thread.')

    @commands.group(name="queue", invoke_without_command=True)
    async def queue(self, ctx: Context):
        pass

    @queue.command("add")
    async def queue_add(self, ctx: Context, *, thread_name: str):
        if len(thread_name) > 100:
            embed = discord.Embed(
                color=discord.Color.red(),
                title="Error",
                description="Thread names must not exceed 100 characters.",
            )
            return await ctx.reply(embed=embed, mention_author=False)

        await self.bot.db.execute(
            "INSERT INTO thread_name_queue (thread_name, owner_id) VALUES (?, ?)",
            (thread_name, ctx.author.id),
        )
        await self.bot.db.commit()

        return await ctx.reply("Added to queue.", mention_author=False)

    @queue.command("remove")
    async def queue_remove(self, ctx: Context, *, thread_name_or_id: str):
        async with self.bot.db.execute(
            "SELECT * FROM thread_name_queue WHERE (thread_name = :id OR id = CAST(:id AS INTEGER)) AND owner_id = :owner_id",
            {"id": thread_name_or_id, "owner_id": ctx.author.id},
        ) as cursor:
            if not await cursor.fetchone():
                return ctx.reply(
                    "Thread name not in queue, or you don't have permission to remove it.",
                    mention_author=False,
                )

        await self.bot.db.execute(
            "DELETE FROM thread_name_queue WHERE (thread_name = :id OR id = CAST(:id AS INTEGER)) AND owner_id = :owner_id",
            {"id": thread_name_or_id, "owner_id": ctx.author.id},
        )
        await self.bot.db.commit()

        return await ctx.reply("Removed from queue.", mention_author=False)

    @queue.command("list")
    async def queue_list(self, ctx: Context):
        rows = await self.bot.db.execute_fetchall("SELECT * FROM thread_name_queue WHERE thread_id = NULL AND deleted = FALSE")

        description = ""
        for row in rows:
            description += f"`{row[0]}` - {row[1]} - <@{row[2]}>\n"

        embed = discord.Embed(title="Thread names", description=description)
        return await ctx.reply(embed=embed, mention_author=False)

    @queue.command("invited")
    async def queue_invited(self, ctx: Context):
        description = ""

        for user in self.bot.cfg["SOCIETY_USER_IDS"].split(" "):
            description += f"<@{user}> "

        for role in self.bot.cfg["SOCIETY_ROLE_IDS"].split(" "):
            description += f"<@&{role}> "

        return await ctx.reply(
            embed=discord.Embed(
                title="Invited people",
                description=description,
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @queue.command("create")
    @commands.has_permissions(administrator=True)
    async def queue_create(self, ctx: Context):
        await self.queue_loop()

    @queue.command("clear")
    @commands.has_permissions(administrator=True)
    async def queue_clear(self, ctx: Context):
        await self.bot.db.execute("DELETE FROM thread_name_queue")
        await self.bot.db.commit()

        return await ctx.reply("Cleared queue.", mention_author=False)

    @queue.command("nuke")
    @commands.has_permissions(manage_threads=True)
    async def queue_nuke(self, ctx: Context):
        await ctx.channel.delete()

    @tasks.loop(time=[time(hour=0, minute=0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))])
    async def queue_loop(self):
        # Clean up old threads
        async with self.bot.db.execute("SELECT * FROM thread_name_queue WHERE thread_id != NULL AND deleted = FALSE") as cursor:
            stale_channels = await cursor.fetchall()

            for stale_channel in stale_channels:
                (id, thread_name, _, thread_id, created, _) = stale_channel

                if datetime.now(UTC) - created >= timedelta(days=2):
                    channel = self.bot.get_channel(thread_id)

                    if channel is not None:
                        await channel.delete()
                    
                    await self.bot.db.execute("UPDATE thread_name_queue SET deleted = TRUE WHERE id = ?", (id,))
            
            await self.bot.db.commit()

        nsfw_channel = self.bot.get_channel(int(self.bot.cfg["NSFW_CHANNEL_ID"]))
        if nsfw_channel is None or not isinstance(nsfw_channel, discord.TextChannel):
            return

        async with self.bot.db.execute("SELECT * FROM thread_name_queue WHERE thread_id = NULL AND deleted = FALSE") as cursor:
            row = await cursor.fetchone()
            if row is None:
                return
            else:
                (id, thread_name, _, _, _, _) = row

        thread = await nsfw_channel.create_thread(
            name=f"[quỷ] {thread_name}",
            type=discord.ChannelType.private_thread,
            invitable=True,
        )
        message = ""

        for user in self.bot.cfg["SOCIETY_USER_IDS"].split(" "):
            message += f"<@{user}> "

        for role in self.bot.cfg["SOCIETY_ROLE_IDS"].split(" "):
            message += f"<@&{role}> "

        thread = await thread.send(message)
        await self.bot.http.request(
            Route("PATCH", "/channels/{thread_id}", thread_id=thread.id),
            json={"invitable": False},
        )

        if id is not None:
            await self.bot.db.execute(
                "UPDATE thread_name_queue SET thread_id = ? WHERE id = ?", (thread.id, id,)
            )
            await self.bot.db.commit()

    # @commands.Cog.listener()
    # async def on_presence_update(self, before: discord.Member, after: discord.Member):
    #     if (
    #         (activity := after.activity) is None
    #         or not isinstance(activity, Game)
    #         or activity.start is None
    #     ):
    #         return

    #     if activity.name == "League of Legends" and datetime.now(
    #         UTC
    #     ) - activity.start >= timedelta(minutes=30):
    #         await after.guild.ban(after, reason="Playing League of Legends")


async def setup(bot: VeryCheapBot):
    if bot.cfg.get("NSFW_CHANNEL_ID"):
        await bot.add_cog(DemonsCog(bot))
