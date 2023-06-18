import re
from typing import Optional

from bs4 import BeautifulSoup
from yarl import URL

from scrapers.source import Scraper
from scrapers.source.types import MangaDetails, MangaStatus


HR_REGEX = re.compile(r"^-{3,}$", re.MULTILINE)
HVN_MANGA_DETAILS_REGEX = re.compile(
    r"https?:\/\/(?P<domain>hentaivn\.(?:.*))\/(?P<manga_id>\d+)-doc-truyen-(?P<slug>.+)\.html"
)
HVN_CHAPTER_REGEX = re.compile(
    r"https?:\/\/(?P<domain>hentaivn\.(?:.*))\/(?P<manga_id>\d+)-(?P<chapter_id>\d+)-xem-truyen-(?P<slug>.+)\.html"
)


class HentaiVN(Scraper):
    base_url = "hentaivn.site"

    def __init__(self) -> None:
        super().__init__()

    def find_url(self, content: str) -> Optional[str]:
        details_url = HVN_MANGA_DETAILS_REGEX.search(content)
        if details_url is not None:
            return details_url.group(0)
        chapter_url = HVN_CHAPTER_REGEX.search(content)
        if chapter_url is not None:
            return chapter_url.group(0)
        return None

    async def get_manga_details(self, uri: str) -> MangaDetails:
        if (match := HVN_CHAPTER_REGEX.search(uri)) is not None:
            return await self._handle_chapter(match.group(0))
        elif (match := HVN_MANGA_DETAILS_REGEX.search(uri)) is not None:
            return await self._handle_manga(match.group(0))
        else:
            raise RuntimeError("Invalid URL")

    async def _handle_chapter(self, uri: str) -> MangaDetails:
        url = URL(uri).with_host(self.base_url)
        resp = await self.session.get(url)
        soup = BeautifulSoup(await resp.text(), "html.parser")

        manga_elem = soup.select_one(
            "ol.breadcrumb2 li[itemprop=itemListElement]:nth-child(3) a"
        )
        if manga_elem is None:
            raise RuntimeError("Manga element not found")

        manga_url = f"https://{self.base_url}{manga_elem['href']}"
        return await self._handle_manga(manga_url)

    async def _handle_manga(self, uri: str) -> MangaDetails:
        url = URL(uri).with_host(self.base_url)
        resp = await self.session.get(url)
        soup = BeautifulSoup(await resp.text(), "html.parser")

        title_elem = soup.select_one(
            "ol.breadcrumb2 li[itemprop=itemListElement]:last-child span[itemprop=name]"
        )
        if title_elem is None:
            raise RuntimeError("Title element not found")
        title = title_elem.text.strip()

        details = MangaDetails(url=str(url), title=title, status=MangaStatus.UNKNOWN)

        info_elem = soup.select_one(".main > .page-left > .left-info > .page-info")
        if info_elem is not None:
            if (
                author_elem := info_elem.select_one('p:-soup-contains("Tác giả:") a')
            ) is not None:
                details.author = author_elem.text.strip()
            if (
                status_elem := info_elem.select_one('p:-soup-contains("Tình Trạng:") a')
            ) is not None:
                details.status = self._status_parser(status_elem.text.strip())
            if (
                genre_elems := info_elem.select('p:-soup-contains("Thể Loại:") a')
            ) is not None and len(genre_elems) > 0:
                details.genres = [genre_elem.text.strip() for genre_elem in genre_elems]
            if (
                description_elem := info_elem.select_one(
                    'p:-soup-contains("Nội dung:") + p'
                )
            ) is not None:
                details.description = HR_REGEX.split(description_elem.text.strip())[0]
            if (
                thumbnail_elem := soup.select_one(
                    ".main > .page-right > .right-info > .page-ava > img"
                )
            ) is not None:
                details.thumbnail_url = str(thumbnail_elem["src"])

        return details

    def _status_parser(self, status: str) -> MangaStatus:
        match status:
            case "Đang tiến hành":
                return MangaStatus.ONGOING
            case "Đã hoàn thành":
                return MangaStatus.COMPLETED
            case _:
                return MangaStatus.UNKNOWN
