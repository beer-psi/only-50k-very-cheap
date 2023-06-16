import aiohttp
import discord
import re
from discord.ext import commands

from bs4 import BeautifulSoup

from bot import VeryCheapBot


BASE_URL = "hentaivn.site"
HR_REGEX = re.compile(r"^-{3,}$", re.MULTILINE)
HVN_MANGA_DETAILS_REGEX = re.compile(r"https?:\/\/(?P<domain>hentaivn\.(?:.*))\/(?P<manga_id>\d+)-doc-truyen-(?P<slug>.+)\.html")
HVN_CHAPTER_REGEX = re.compile(r"https?:\/\/(?P<domain>hentaivn\.(?:.*))\/(?P<manga_id>\d+)-(?P<chapter_id>\d+)-xem-truyen-(?P<slug>.+)\.html")


class HVNCog(commands.Cog, name="HVN"):
    def __init__(self, bot: VeryCheapBot) -> None:
        self.bot = bot

    async def _handle_chapter(self, match: re.Match[str]) -> discord.Embed | None:
        url = match.group(0).replace(match.group("domain"), BASE_URL)
        async with aiohttp.ClientSession() as session:
            resp = await session.get(url)
            soup = BeautifulSoup(await resp.text(), "html.parser")
        
        manga_elem = soup.select_one("ol.breadcrumb2 li[itemprop=itemListElement]:nth-child(3) a")
        if manga_elem is None:
            return
        
        manga_url = f"https://{BASE_URL}{manga_elem['href']}"
        if (match2 := HVN_MANGA_DETAILS_REGEX.search(manga_url)) is not None:
            return await self._handle_manga(match2)

    async def _handle_manga(self, match: re.Match[str]) -> discord.Embed | None:
        url = match.group(0).replace(match.group("domain"), BASE_URL)
        async with aiohttp.ClientSession() as session:
            resp = await session.get(url)
            soup = BeautifulSoup(await resp.text(), "html.parser")
        
        title_elem = soup.select_one("ol.breadcrumb2 li[itemprop=itemListElement]:last-child span[itemprop=name]")
        if title_elem is None:
            return
        title = title_elem.text.strip()

        embed = discord.Embed(title=title, url=url)
        info_elem = soup.select_one(".main > .page-left > .left-info > .page-info")
        if info_elem is not None:
            if (author_elem := info_elem.select_one('p:-soup-contains("Tác giả:") a')) is not None:
                embed.add_field(name="Tác giả", value=author_elem.text.strip(), inline=True)
            if (status_elem := info_elem.select_one('p:-soup-contains("Tình Trạng:") a')) is not None:
                embed.add_field(name="Tình trạng", value=status_elem.text.strip(), inline=True)
            if (genre_elems := info_elem.select('p:-soup-contains("Thể Loại:") a')) is not None and len(genre_elems) > 0:
                embed.add_field(name="Thể loại", value=", ".join(genre_elem.text.strip() for genre_elem in genre_elems), inline=False)
            if (description_elem := info_elem.select_one('p:-soup-contains("Nội dung:") + p')) is not None:
                embed.description = HR_REGEX.split(description_elem.text.strip())[0]
            if (thumbnail_elem := soup.select_one(".main > .page-right > .right-info > .page-ava > img")) is not None:
                embed.set_image(url=thumbnail_elem["src"])
        
        return embed

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        embed = None
        if (match := HVN_CHAPTER_REGEX.search(message.content)) is not None:
            embed = await self._handle_chapter(match)
        if (match := HVN_MANGA_DETAILS_REGEX.search(message.content)) is not None:
            embed = await self._handle_manga(match)
        
        if embed is not None:
            await message.reply(embed=embed, mention_author=False)


async def setup(bot: VeryCheapBot):
    await bot.add_cog(HVNCog(bot))
