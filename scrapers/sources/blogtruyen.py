import re
from typing import Optional

from bs4 import BeautifulSoup
from yarl import URL

from scrapers.source import Scraper
from scrapers.source.types import MangaDetails, MangaStatus


MANGA_DETAILS_REGEX = re.compile(r"https?:\/\/(?P<domain>(?:m\.)?blogtruyen(?:\.vn|moi\.com))\/(?P<manga_id>\d+)\/(?P<slug>[a-z\d-]+)")
MANGA_CHAPTER_REGEX = re.compile(r"https?:\/\/(?P<domain>(?:m\.)?blogtruyen(?:\.vn|moi\.com))\/c(?P<chapter_id>\d+)\/(?P<slug>[a-z\d-]+)")


class BlogTruyen(Scraper):
    base_url = "blogtruyenmoi.com"

    def __init__(self) -> None:
        super().__init__()
    
    def find_url(self, content: str) -> Optional[str]:
        details_url = MANGA_DETAILS_REGEX.search(content)
        if details_url is not None:
            return details_url.group(0)
        chapter_url = MANGA_CHAPTER_REGEX.search(content)
        if chapter_url is not None:
            return chapter_url.group(0)
        return None

    async def get_manga_details(self, uri: str) -> MangaDetails:
        if (match := MANGA_CHAPTER_REGEX.search(uri)) is not None:
            return await self._handle_chapter(match.group(0))
        elif (match := MANGA_DETAILS_REGEX.search(uri)) is not None:
            return await self._handle_manga(match.group(0))
        else:
            raise RuntimeError("Invalid URL")
    
    async def _handle_chapter(self, uri: str) -> MangaDetails:
        url = URL(uri)
        resp = await self.session.get(url)
        soup = BeautifulSoup(await resp.text(), "html.parser")

        manga_elem = soup.select_one("div.breadcrumbs a:last-child")
        if manga_elem is None:
            raise RuntimeError("Manga element not found")
        
        manga_url = f"https://{url.host}{manga_elem['href']}"
        return await self._handle_manga(manga_url)
    
    async def _handle_manga(self, uri: str) -> MangaDetails:
        resp = await self.session.get(uri)
        soup = BeautifulSoup(await resp.text(), "html.parser")

        title_elem = soup.select_one(".entry-title a")
        if title_elem is None:
            raise RuntimeError("Title element not found")
        title = str(title_elem["title"]).replace("truyện tranh ", "", 1).strip()

        details = MangaDetails(title=title, url=uri, status=MangaStatus.UNKNOWN)

        if (elem := soup.select_one(".thumbnail img")) is not None:
            url = str(elem["src"])
            if url.startswith("//"):
                url = f"https:{url}"
            if url.startswith("/"):
                url = f"https://{URL(uri).host}{url}"
            details.thumbnail_url = url
        if (elem := soup.select("a[href*=tac-gia]")) is not None and len(elem) > 0:
            details.author = ", ".join([e.text.strip() for e in elem])
        if (elem := soup.select("span.category a")) is not None and len(elem) > 0:
            details.genres = [e.text.strip() for e in elem]
        if (elem := soup.select("span.color-red:not(.bold)")) is not None:
            details.status = self._parse_status(" ".join([e.text.strip() for e in elem]))
        if (synopsis_block := soup.select_one(".manga-detail .detail .content")) is not None:
            for tag in synopsis_block.select("p, br"):
                tag.insert_before("\\n")
            
            if (fb_elements := synopsis_block.select(".fb-page, .fb-group")) is not None and len(fb_elements) > 0:
                for fb_element in fb_elements:
                    fb_element.decompose()
            details.description = synopsis_block.text.replace("\\n", "\n").replace("\n ", "\n").strip()
        
        return details
    
    def _parse_status(self, status: str) -> MangaStatus:
        if "Đang tiến hành" in status:
            return MangaStatus.ONGOING
        elif "Đã hoàn thành" in status:
            return MangaStatus.COMPLETED
        elif "Tạm ngưng" in status:
            return MangaStatus.ON_HIATUS
        return MangaStatus.UNKNOWN
