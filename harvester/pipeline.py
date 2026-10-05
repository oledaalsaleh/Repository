"""Orchestration: run sources → window filter → dedupe by priority → validate → last-known-good."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config
from .dates import now_tr
from .http import PoliteSession
from .models import Catalog, Page
from .sources import ALL_SOURCES
from .validate import validate_catalogs

log = logging.getLogger("harvester.pipeline")


@dataclass
class StoreHealth:
    fresh: int = 0
    carried: int = 0
    pages: int = 0
    sources: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.fresh:
            return "ok"
        return "stale" if self.carried else "empty"


@dataclass
class HarvestResult:
    catalogs: list[Catalog]
    health: dict[str, StoreHealth]
    previous: dict[str, dict]           # previous catalogs.json entries by id
    today: date


def load_previous() -> dict[str, dict]:
    try:
        data = json.loads(config.CATALOGS_FILE.read_text(encoding="utf-8"))
        return {c["id"]: c for c in data.get("catalogs", [])}
    except (FileNotFoundError, ValueError, KeyError):
        return {}


def _from_previous(d: dict) -> Catalog:
    return Catalog(
        store=d["store"], valid_from=date.fromisoformat(d["valid_from"]),
        valid_to=date.fromisoformat(d["valid_to"]), title=d["title"], kind=d.get("kind", "aktuel"),
        source=d.get("source", "previous"), source_url=d.get("source_url", ""), priority=99,
        pages=[Page(p["index"], p["url"], p.get("width"), p.get("height"), True) for p in d["pages"]],
        first_seen=d.get("first_seen"), stale=True,
    )


def run(stores: set[str] | None = None, validate: bool = True) -> HarvestResult:
    today = now_tr().date()
    stores = stores or set(config.STORES)
    wanted = {config.STORES[s].key for s in stores}
    http = PoliteSession()
    health = {st.key: StoreHealth() for slug, st in config.STORES.items() if slug in stores}

    # 1. Collect from every adapter — an exception in one never stops the others.
    candidates: list[Catalog] = []
    for src_cls in ALL_SOURCES:
        if not set(src_cls.stores) & stores:
            continue
        try:
            found = src_cls(http, today).fetch()
        except Exception as exc:
            log.error("source %s failed: %s", src_cls.name, exc)
            for s in src_cls.stores:
                if s in stores:
                    health[config.STORES[s].key].errors.append(f"{src_cls.name}: {exc}")
            continue
        candidates += [c for c in found if c.store in wanted]

    # 2. Lifecycle window: drop expired and far-future entries.
    horizon = today + timedelta(days=config.MAX_UPCOMING_DAYS)
    candidates = [c for c in candidates if c.valid_to >= today and c.valid_from <= horizon]

    # 3. Group duplicates (same store + start date + kind) and pick the best candidate.
    groups: dict[str, list[Catalog]] = defaultdict(list)
    for c in candidates:
        groups[c.id].append(c)

    winners: list[Catalog] = []
    pending = {cid: sorted(g, key=lambda c: (c.priority, -len(c.pages))) for cid, g in groups.items()}
    while pending:                              # round 1 = best candidates, round 2+ = fallbacks
        batch = {cid: g.pop(0) for cid, g in pending.items()}
        if validate:
            validate_catalogs(http, list(batch.values()))
        for cid, cand in batch.items():
            if cand.pages:
                winners.append(cand)
                pending[cid] = []
            else:
                log.warning("candidate %s from %s had no valid pages", cid, cand.source)
        pending = {cid: g for cid, g in pending.items() if g}

    # 4. first_seen persistence + health accounting.
    previous = load_previous()
    stamp = now_tr().strftime("%Y-%m-%dT%H:%M:%S")
    for c in winners:
        c.first_seen = previous.get(c.id, {}).get("first_seen") or stamp
        h = health[c.store]
        h.fresh += 1
        h.pages += len(c.pages)
        h.sources.add(c.source)

    # 5. Last-known-good: a store that produced nothing keeps its still-valid previous catalogs.
    for store_key, h in health.items():
        if h.fresh:
            continue
        for d in previous.values():
            if d["store"] == store_key and date.fromisoformat(d["valid_to"]) >= today:
                winners.append(_from_previous(d))
                h.carried += 1
                h.pages += len(d["pages"])
        log.warning("store %s: no fresh data, carried %d catalogs", store_key, h.carried)

    order = {s.key: i for i, s in enumerate(config.STORES.values())}
    winners.sort(key=lambda c: (order.get(c.store, 99), -c.valid_from.toordinal()))
    return HarvestResult(winners, health, previous, today)
