"""Domain model: a Catalog is an ordered list of Pages for one store and one start date."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date


def stable_id(*parts: str, length: int = 16) -> str:
    """Deterministic id (unlike Python's hash(), which is salted per process)."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:length]


@dataclass
class Page:
    index: int
    url: str
    width: int | None = None
    height: int | None = None
    valid: bool | None = None       # None = not validated yet

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None and k != "valid"}


@dataclass
class Catalog:
    store: str                      # canonical store key ("BİM", "A101", "ŞOK")
    valid_from: date
    valid_to: date
    title: str
    source: str                     # adapter name
    source_url: str
    priority: int                   # lower = more trusted (official = 0)
    kind: str = "aktuel"            # aktuel | indirim | hafta_sonu
    pages: list[Page] = field(default_factory=list)
    first_seen: str | None = None   # ISO datetime, persisted across runs
    stale: bool = False             # carried over from the last successful run

    @property
    def id(self) -> str:
        return stable_id(self.store, self.valid_from.isoformat(), self.kind)

    def status(self, today: date) -> str:
        if today < self.valid_from:
            return "upcoming"
        if today > self.valid_to:
            return "expired"
        return "active"

    def to_dict(self, today: date) -> dict:
        return {
            "id": self.id,
            "store": self.store,
            "title": self.title,
            "kind": self.kind,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat(),
            "status": self.status(today),
            "source": self.source,
            "source_url": self.source_url,
            "first_seen": self.first_seen,
            "stale": self.stale,
            "page_count": len(self.pages),
            "cover": self.pages[0].url if self.pages else None,
            "pages": [p.to_dict() for p in self.pages],
        }
