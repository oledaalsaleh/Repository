"""ŞOK — official corporate "Haftanın Fırsatları" page.

Upload filenames embed a timestamp (uploads/20260930101530xxxx.jpg). We use it as a
freshness gate: the page is frequently left stale for months, so anything older than
FRESH_DAYS is ignored and the aggregator fallback takes over automatically.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from ..config import STORES
from ..dates import end_of_validity
from ..models import Catalog, Page
from .base import Source, unique

URL = "https://kurumsal.sokmarket.com.tr/haftanin-firsatlari/firsatlar"
IMG_RE = re.compile(r"https?://kurumsal\.sokmarket\.com\.tr/uploads/((\d{4})(\d{2})(\d{2})\d*)\.(?:jpe?g|png|webp)", re.I)
FRESH_DAYS = 10
SOK_AKTUEL_WEEKDAY = 2  # Wednesday


class SokOfficial(Source):
    name = "sok_official"
    priority = 0
    stores = ("sok",)

    def fetch(self) -> list[Catalog]:
        html = self.http.get_text(URL)
        store = STORES["sok"]
        fresh: list[tuple[date, str]] = []
        for m in IMG_RE.finditer(html):
            try:
                uploaded = date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
            except ValueError:
                continue
            if (self.today - uploaded).days <= FRESH_DAYS:
                fresh.append((uploaded, m.group(0)))

        if not fresh:
            self.log.info("ŞOK official → page is stale, deferring to aggregator")
            return []

        uploaded = max(d for d, _ in fresh)
        # Snap to the Wednesday the catalog starts on, so it merges with aggregator data.
        start = uploaded + timedelta(days=(SOK_AKTUEL_WEEKDAY - uploaded.weekday()) % 7)
        urls = unique(u for _, u in sorted(fresh))
        return [Catalog(
            store=store.key, valid_from=start, valid_to=end_of_validity(start, store.valid_days),
            title=f"ŞOK {start.day:02d}.{start.month:02d}.{start.year} Haftanın Fırsatları",
            source=self.name, source_url=URL, priority=self.priority,
            pages=[Page(i + 1, u) for i, u in enumerate(urls)],
        )]
