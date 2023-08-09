from datetime import time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context

from bot import VeryCheapBot


class DemonsCog(commands.Cog, name="Demons", command_attrs=dict(hidden=True)):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        role_ids = [str(role.id) for role in ctx.author.roles]
        return (
            self.bot.cfg["SEGG_DEMON_ROLE_ID"] in role_ids
            or self.bot.cfg["SEGG_INTERN_ROLE_ID"] in role_ids
        )

    @commands.group(name="queue", invoke_without_command=True)
    async def queue(self, ctx: Context):
        pass

    @queue.command("add")
    async def queue_add(self, ctx: Context, *, thread_name: str):
        await self.bot.db.execute("INSERT INTO thread_name_queue (thread_name, owner_id) VALUES (?, ?)", (thread_name, ctx.author.id))
        await self.bot.db.commit()

        return await ctx.reply("Added to queue.", mention_author=False)

    @queue.command("remove")
    async def queue_remove(self, ctx: Context, *, thread_name_or_id: str):
        async with self.bot.db.execute(
            "SELECT * FROM thread_name_queue WHERE (thread_name = :id OR id = CAST(:id AS INTEGER)) AND owner_id = :owner_id",
            {"id": thread_name_or_id, "owner_id": ctx.author.id}
        ) as cursor:
            if not await cursor.fetchone():
                return ctx.reply("Thread name not in queue, or you don't have permission to remove it.", mention_author=False)

        await self.bot.db.execute(
            "DELETE FROM thread_name_queue WHERE (thread_name = :id OR id = CAST(:id AS INTEGER)) AND owner_id = :owner_id",
            {"id": thread_name_or_id, "owner_id": ctx.author.id}
        )
        await self.bot.db.commit()

        return await ctx.reply("Removed from queue.", mention_author=False)

    @queue.command("list")
    async def queue_list(self, ctx: Context):
        rows = await self.bot.db.execute_fetchall("SELECT * FROM thread_name_queue")

        description = ""
        for row in rows:
            description += f"{row[1]} - <@{row[2]}>\n"

        embed = discord.Embed(title="Thread names", description=description)
        return await ctx.reply(embed=embed, mention_author=False)

    @tasks.loop(time=[time(hour=0, minute=0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))])
    async def queue_loop(self):
        nsfw_channel = self.bot.get_channel(int(self.bot.cfg["NSFW_CHANNEL_ID"]))
        if nsfw_channel is None or not isinstance(nsfw_channel, discord.TextChannel):
            return

        async with self.bot.db.execute("SELECT * FROM thread_name_queue") as cursor:
            row = await cursor.fetchone()
            if row is None:
                id = None
                thread_name = "mmb"
            else:
                (id, thread_name, _) = row

        thread = await nsfw_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False,
        )
        await thread.send(f"<@&{self.bot.cfg['SEGG_DEMON_ROLE_ID']}> <@&{self.bot.cfg['SEGG_INTERN_ROLE_ID']}>")

        if id is not None:
            await self.bot.db.execute("DELETE FROM thread_name_queue WHERE id = ?", (id,))
            await self.bot.db.commit()


async def setup(bot: VeryCheapBot):
    await bot.add_cog(DemonsCog(bot))

