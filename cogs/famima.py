from datetime import time
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import aiohttp
from discord import ButtonStyle, Interaction, ui
import discord
from discord.ext import commands, tasks
from discord.utils import escape_markdown

if TYPE_CHECKING:
    from bot import VeryCheapBot


class FamimaError(Exception):
    def __init__(self, title: str, description: str) -> None:
        self.title = title
        self.description = description
        super().__init__(f"{title}: {description}")


class FamimaLoginModal(ui.Modal, title="Drac"):
    member_code = ui.TextInput(
        label="Member code",
    )
    pin = ui.TextInput(
        label="PIN",
    )

    async def on_submit(self, interaction: Interaction):
        if len(self.member_code.value) == 0 or len(self.pin.value) == 0:
            await interaction.response.send_message(
                content="Did not provide member code/PIN",
                ephemeral=True
            )
            return

        async with aiohttp.ClientSession() as session:
            session.headers.update({
                "abp.tenantid": "1",
                "accept-language": "en",
                "user-agent": "Dart/2.18 (dart:io)",
            })

            resp = await session.post(
                "https://fmv-pro-cxm-api.retailhub.vn/api/TokenAuth/Authenticate",
                json={
                    "usernameOrEmailAddress": self.member_code.value,
                    "password": self.pin.value,
                },
            )
            data = await resp.json()

            if not data["success"]:
                details = escape_markdown(data["error"]["details"])

                await interaction.response.send_message(
                    content=f"Could not log in to FamilyMart: {details}",
                    ephemeral=True
                )
                return
            
            bot = cast("VeryCheapBot", interaction.client)

            await bot.db.execute(
                "INSERT INTO famima_creds (id, member_code, password) VALUES (?, ?, ?) ON CONFLICT (id) DO UPDATE SET member_code = excluded.member_code, password = excluded.password",
                (interaction.user.id, self.member_code.value, self.pin.value),
            )
            await bot.db.commit()
            
            await interaction.response.send_message(
                content="Successfully logged in.",
                ephemeral=True
            )


class FamimaLoginView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Log in to FamilyMart", style=ButtonStyle.blurple, custom_id="FamimaLoginView:Login")
    async def login(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(FamimaLoginModal())


class FamimaGachaCog(commands.Cog):
    def __init__(self, bot: "VeryCheapBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.famima_roll_task.start()
    
    async def cog_unload(self) -> None:
        self.famima_roll_task.stop()

    @commands.group("famima", invoke_without_command=True, hidden=True)
    async def famima(self, ctx: commands.Context):
        pass

    @famima.command("login")
    async def famima_login(self, ctx: commands.Context):
        await ctx.reply(
            view=FamimaLoginView(),
            mention_author=False,
        )

    @famima.command("logout")
    async def famima_logout(self, ctx: commands.Context):
        await self.bot.db.execute("DELETE FROM famima_creds WHERE id = ?", (ctx.author.id,))
        await self.bot.db.commit()

        embed = discord.Embed(
            color=discord.Color.green(),
            title="Success",
            description="Successfully logged out.",
        )
        await ctx.reply(embed=embed, mention_author=False)
    
    @famima.command("auto")
    async def famima_auto(self, ctx: commands.Context):
        async with self.bot.db.execute("SELECT * FROM famima_creds WHERE id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()

            if row is None:
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title="Error",
                    description=f"You are not logged in. Use `{ctx.prefix}famima login`.",
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
        
            (_, _, _, auto_roll_channel_id) = row

            await self.bot.db.execute(
                "UPDATE famima_creds SET auto_roll_channel_id = ?",
                (ctx.channel.id if auto_roll_channel_id is None else None,)
            )
            await self.bot.db.commit()

            description = (
                f"Enabled automatic daily rolls (at 6am UTC+7) and will notify results to {ctx.channel.mention}."
                if auto_roll_channel_id is None
                else "Disabled automatic daily rolls."
            )

            embed = discord.Embed(
                color=discord.Color.green(),
                title="Success",
                description=description,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
    
    @tasks.loop(time=[time(hour=6, minute=0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))])
    async def famima_roll_task(self):
        async with self.bot.db.execute("SELECT * FROM famima_creds WHERE auto_roll_channel_id != NULL") as cursor:
            rows = await cursor.fetchall()
        
        for row in rows:
            (user_id, member_code, pin, channel_id) = row

            try:
                embed = await self._famima_roll_internal(member_code, pin)
            except FamimaError as e:
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title=e.title,
                    description=e.description,
                )
            
            channel = self.bot.get_channel(channel_id)
            
            await channel.send(
                content=f"<@{user_id}>, your results for today's Famima Gacha is in:",
                embed=embed,
            )

    @famima.command("roll")
    async def famima_roll(self, ctx: commands.Context):
        async with self.bot.db.execute("SELECT * FROM famima_creds WHERE id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()

            if row is None:
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title="Error",
                    description=f"You are not logged in. Use `{ctx.prefix}famima login`.",
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
            
            (_, member_code, pin, _) = row

            async with ctx.typing():
                try:
                    embed = await self._famima_roll_internal(member_code, pin)
                except FamimaError as e:
                    embed = discord.Embed(
                        color=discord.Color.red(),
                        title=e.title,
                        description=e.description,
                    )
                    
                await ctx.reply(embed=embed, mention_author=False)

    async def _famima_roll_internal(self, member_code: str, pin: str):
        async with aiohttp.ClientSession() as session:
            session.headers.update({
                "abp.tenantid": "1",
                "accept-language": "en",
                "content-type": "application/json-patch+json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36",
                "x-requested-with": "jp.co.toshiba.famipoint.membership.mobile.android"
            })

            resp = await session.get("https://fmv-game.retailhub.vn/assets/config/config.env.json")
            config = await resp.json()
            api_server = config["apiServer"]["server"]
            game_code = config["gameSetting"]["gameCode"]

            resp = await session.post(
                f"{api_server}/TokenAuth/Authenticate",
                json={
                    "MaxResultCount": 20,
                    "userNameOrEmailAddress": member_code,
                    "SkipCount": 0,
                    "password": pin,
                },
            )
            auth_data = await resp.json()

            if not auth_data["success"]:
                details = escape_markdown(auth_data["error"]["details"] or auth_data["error"]["message"])

                raise FamimaError("Login failed", details)
            
            session.headers.update({
                "Authorization": f"Bearer {auth_data['result']['accessToken']}"
            })

            resp = await session.get(f"{api_server}/services/app/GameInfos/GetGamePlayInfo?memberCode={member_code}&gameCode={game_code}&MaxResultCount=20&SkipCount=0")
            game_play_data = await resp.json()

            if not game_play_data["success"]:
                details = escape_markdown(game_play_data["error"]["details"] or game_play_data["error"]["message"])

                raise FamimaError("Could not fetch gameplay data", details)

            if game_play_data["result"]["numberOfTicket"] == 0:
                raise FamimaError("You have rolled today", "Try again tomorrow!")
            
            resp = await session.post(
                f"{api_server}/services/app/GameInfos/Spin",
                json={
                    "gameCode": game_code,
                    "MaxResultCount": 20,
                    "memberCode": member_code,
                    "SkipCount": 0,
                },
            )
            spin_data = await resp.json()

            if not spin_data["success"]:
                details = escape_markdown(spin_data["error"]["details"] or spin_data["error"]["message"])        
                
                raise FamimaError("Rolling the gacha failed", details)
            
            embed = discord.Embed(
                color=discord.Color.yellow(),
                title=spin_data["result"]["rewardNameVN"],
            )
            embed.set_image(url=spin_data["result"]["imageLink"])

            return embed


async def setup(bot: "VeryCheapBot"):
    await bot.add_cog(FamimaGachaCog(bot))
    bot.add_view(FamimaLoginView())