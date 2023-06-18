from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

import discord


class MangaStatus(Enum):
    UNKNOWN = 0
    ONGOING = 1
    COMPLETED = 2
    CANCELLED = 3
    ON_HIATUS = 4

    def __str__(self) -> str:
        if self.value == 0:
            return "Không rõ"
        elif self.value == 1:
            return "Đang tiến hành"
        elif self.value == 2:
            return "Đã hoàn thành"
        elif self.value == 3:
            return "Đã hủy"
        elif self.value == 4:
            return "Tạm ngưng"
        else:
            return "Không rõ"


@dataclass
class MangaDetails:
    url: str
    title: str
    status: MangaStatus
    genres: Sequence[str] = field(default_factory=list)
    author: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None

    def to_discord_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title, url=self.url)

        if self.author is not None:
            embed.add_field(name="Tác giả", value=self.author, inline=True)
        if self.status is not None:
            embed.add_field(name="Tình trạng", value=str(self.status), inline=True)
        if self.genres is not None and len(self.genres) > 0:
            embed.add_field(name="Thể loại", value=", ".join(self.genres), inline=False)
        if self.description is not None:
            embed.description = self.description
        if self.thumbnail_url is not None:
            embed.set_image(url=self.thumbnail_url)

        return embed
