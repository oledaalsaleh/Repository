from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import date

from ..http import PoliteSession
from ..models import Catalog

_THUMB_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.(?:webp|jpe?g|png|avif)$)", re.I)


def upgrade_image_url(url: str) -> str:
    """Turn known thumbnail URLs into their full-resolution originals."""
    url = url.strip().split("?")[0].split("#")[0]
    url = url.replace("/uploads/afisler/k_", "/uploads/afisler/")        # BİM
    url = url.replace("_kucuk_", "_buyuk_")                              # BİM aktüel ürün
    url = url.replace("-thumbnail.", ".")                                # katlok-style CDNs
    return _THUMB_RE.sub("", url)                                        # WordPress -WxH


def unique(seq):
    return list(dict.fromkeys(seq))


class Source(ABC):
    name: str = "base"
    priority: int = 10
    stores: tuple[str, ...] = ()        # store slugs this adapter can serve

    def __init__(self, http: PoliteSession, today: date) -> None:
        self.http = http
        self.today = today
        self.log = logging.getLogger(f"harvester.src.{self.name}")

    @abstractmethod
    def fetch(self) -> list[Catalog]:
        ...
