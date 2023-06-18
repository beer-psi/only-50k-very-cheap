import asyncio

from .sources.hvn import HentaiVN
from .sources.blogtruyen import BlogTruyen

sources = [BlogTruyen(), HentaiVN()]


async def start_sources():
    await asyncio.gather(*[source.start() for source in sources])
