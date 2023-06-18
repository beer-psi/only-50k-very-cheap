import asyncio
from aiohttp import ClientSession
from typing import Optional, Protocol

from .types import MangaDetails


class Scraper(Protocol):
    base_url: str
    session: ClientSession

    def __init__(self) -> None:
        self.session = ClientSession()

    async def __aenter__(self) -> "Scraper":
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.session.close()

    async def close(self) -> None:
        await self.session.close()

    def find_url(self, content: str) -> Optional[str]:
        ...
    
    async def get_manga_details(self, uri: str) -> MangaDetails:
        ...
