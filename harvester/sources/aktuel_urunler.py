"""aktuel-urunler.com — WordPress RSS feeds (one post = one catalog, pages in order).

Used as the primary source for A101 (the official site is behind a Cloudflare challenge)
and as an automatic fallback for BİM / ŞOK.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime

from ..config import STORES
from ..dates import end_of_validity, fold, parse_tr_date
from ..models import Catalog, Page
from .base import Source, unique, upgrade_image_url

BASE = "https://aktuel-urunler.com"
FEEDS = [
    f"{BASE}/bim-aktuel/feed/",
    f"{BASE}/a101-aktuel-urunler/feed/",
    f"{BASE}/sok/feed/",
    f"{BASE}/feed/",                       # catch-all for posts in odd sub-categories
]
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
IMG_RE = re.compile(r'(?:src|data-src|href)="(https?://[^"]+/uploads/[^"]+\.(?:webp|jpe?g|png))"', re.I)
PAGE_NO_RE = re.compile(r"-(\d{1,2})\.(?:webp|jpe?g|png)$", re.I)
STORE_PATTERNS = [("bim", re.compile(r"\bbim\b")), ("a101", re.compile(r"\ba101\b")), ("sok", re.compile(r"\bsok\b"))]


def detect_store(title: str) -> str | None:
    t = fold(title)
    for slug, pat in STORE_PATTERNS:
        if pat.search(t):
            return slug
    return None


def order_pages(urls: list[str]) -> list[str]:
    """Sort by the trailing '-N' page number when every URL has one, else keep feed order."""
    nums = [PAGE_NO_RE.search(u) for u in urls]
    if all(nums):
        return [u for _, u in sorted(zip((int(n.group(1)) for n in nums), urls), key=lambda x: x[0])]
    return urls


class AktuelUrunlerRSS(Source):
    name = "aktuel_urunler_rss"
    priority = 10
    stores = ("bim", "a101", "sok")

    def fetch(self) -> list[Catalog]:
        seen_links: set[str] = set()
        catalogs: list[Catalog] = []
        for feed in FEEDS:
            try:
                root = ET.fromstring(self.http.get(feed).content)
            except Exception as exc:  # one bad feed must not kill the others
                self.log.warning("feed failed %s: %s", feed, exc)
                continue
            for item in root.iter("item"):
                link = (item.findtext("link") or "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                cat = self._parse_item(item, link)
                if cat:
                    catalogs.append(cat)
        self.log.info("aktuel-urunler → %d catalogs", len(catalogs))
        return catalogs

    def _parse_item(self, item: ET.Element, link: str) -> Catalog | None:
        title = (item.findtext("title") or "").strip()
        slug = detect_store(title)
        if not slug:
            return None
        store = STORES[slug]

        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").date()
        except (TypeError, ValueError):
            published = self.today
        start = parse_tr_date(title, ref=published) or published

        html = item.findtext(CONTENT_NS) or ""
        urls = self._extract_pages(html)
        if not urls:                               # feed truncated → read the post itself
            try:
                urls = self._extract_pages(self.http.get_text(link))
            except Exception as exc:
                self.log.warning("post failed %s: %s", link, exc)
        if not urls:
            return None

        cats = fold(" ".join(c.text or "" for c in item.findall("category")) + " " + title)
        kind = "hafta_sonu" if "hafta sonu" in cats else "aktuel"
        return Catalog(
            store=store.key, valid_from=start, valid_to=end_of_validity(start, store.valid_days),
            title=re.sub(r"\s+", " ", title), kind=kind,
            source=self.name, source_url=link, priority=self.priority,
            pages=[Page(i + 1, u) for i, u in enumerate(urls)],
        )

    @staticmethod
    def _extract_pages(html: str) -> list[str]:
        raw = [u for u in IMG_RE.findall(html) if not re.search(r"-\d{2,3}x\d{2,3}\.", u)]
        return order_pages(unique(upgrade_image_url(u) for u in raw))
