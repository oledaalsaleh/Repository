"""BİM — official poster (afiş) page. Highest-fidelity source (940×1410 originals).

HTML contract (verified 2026-10):
    div.genelgrup.grup1 → "Aktüel"   |   div.genelgrup.grup2 → "İndirim"
      a.subTabArea span.text          → "29 Eylül Salı"
      .smallArea a.small[data-bigimg] → full-size page URLs (k_ prefix = thumbnail)
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..config import STORES
from ..dates import end_of_validity, parse_tr_dates
from ..models import Catalog, Page
from .base import Source, unique, upgrade_image_url

URL = "https://www.bim.com.tr/Categories/680/afisler.aspx"
KINDS = {"grup1": "aktuel", "grup2": "indirim"}


class BimOfficial(Source):
    name = "bim_official"
    priority = 0
    stores = ("bim",)

    def fetch(self) -> list[Catalog]:
        soup = BeautifulSoup(self.http.get_text(URL), "html.parser")
        store = STORES["bim"]
        catalogs: list[Catalog] = []

        for group in soup.select("div.genelgrup"):
            classes = group.get("class", [])
            kind = next((KINDS[c] for c in classes if c in KINDS), "aktuel")
            label_el = group.select_one(".subTabArea .text")
            label = " ".join(label_el.get_text(" ").split()) if label_el else ""
            dates = parse_tr_dates(label, self.today)
            if not dates:
                self.log.warning("BİM: unparseable label %r — skipped", label)
                continue

            urls = [a.get("data-bigimg") or a.get("href") or ""
                    for a in group.select(".smallArea a.small, .bigArea a.fancyboxImage")]
            urls = unique(upgrade_image_url(u) for u in urls
                          if "/uploads/afisler/" in u and not u.rstrip().endswith("/"))
            if not urls:
                continue

            start = dates[0]
            end = dates[1] if len(dates) > 1 else end_of_validity(start, store.valid_days)
            title_kind = "İndirim" if kind == "indirim" else "Aktüel Ürünler"
            catalogs.append(Catalog(
                store=store.key, valid_from=start, valid_to=end,
                title=f"BİM {label} {title_kind}", kind=kind,
                source=self.name, source_url=URL, priority=self.priority,
                pages=[Page(i + 1, u) for i, u in enumerate(urls)],
            ))
        self.log.info("BİM official → %d catalogs", len(catalogs))
        return catalogs
