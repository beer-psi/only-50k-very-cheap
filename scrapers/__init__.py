import signal

from .sources.hvn import HentaiVN
from .sources.blogtruyen import BlogTruyen

sources = [
    BlogTruyen(),
    HentaiVN()
]
