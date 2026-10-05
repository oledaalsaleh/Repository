"""Publishing: change-aware JSON writers, optional Firestore sync + FCM push, CI summary."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from . import config
from .dates import now_tr
from .models import Catalog, stable_id
from .pipeline import HarvestResult

log = logging.getLogger("harvester.publish")


# ── payload builders ──────────────────────────────────────────────────────────
def _created_at(c: Catalog) -> str:
    """Stable timestamp the clients use for 'freshness': max(first_seen, valid_from)."""
    seen = datetime.fromisoformat(c.first_seen) if c.first_seen else datetime.min
    start = datetime.combine(c.valid_from, datetime.min.time())
    return max(seen, start).strftime("%Y-%m-%d %H:%M:%S")


def build_catalogs_json(res: HarvestResult) -> dict:
    stores = {}
    for s in config.STORES.values():
        h = res.health.get(s.key)
        if h is None:
            continue
        stores[s.key] = {
            "slug": s.slug, "color": s.color, "status": h.status,
            "catalogs": h.fresh + h.carried, "pages": h.pages, "sources": sorted(h.sources),
        }
    return {
        "schema": 2,
        "generated_at": now_tr().isoformat(timespec="seconds"),
        "stores": stores,
        "catalogs": [c.to_dict(res.today) for c in res.catalogs],
    }


def build_offers_json(res: HarvestResult) -> list[dict]:
    """Flat, backward-compatible list consumed by LiveOffersService.kt and web/app.js."""
    rows = []
    for c in res.catalogs:
        created = _created_at(c)
        for p in c.pages:
            row = {
                "id": stable_id(c.id, p.url),
                "catalog_id": c.id,
                "store": c.store,
                "title": f"{c.title} - Sayfa {p.index}",
                "image_url": p.url,
                "page": p.index,
                "page_count": len(c.pages),
                "kind": c.kind,
                "valid_from": c.valid_from.isoformat(),
                "valid_to": c.valid_to.isoformat(),
                "valid_date": c.valid_to.strftime("%d.%m.%Y"),
                "created_at": created,
                "source": c.source,
            }
            if p.width and p.height:
                row["width"], row["height"] = p.width, p.height
            rows.append(row)
    return rows


# ── writers ───────────────────────────────────────────────────────────────────
def _strip_volatile(obj):
    return {k: v for k, v in obj.items() if k != "generated_at"} if isinstance(obj, dict) else obj


def write_json(path: Path, payload, dry_run: bool = False) -> bool:
    """Write only if the meaningful content changed → no empty commits every run."""
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        if _strip_volatile(old) == _strip_volatile(payload):
            log.info("unchanged: %s", path)
            return False
    except (FileNotFoundError, ValueError):
        pass
    if dry_run:
        log.info("[dry-run] would write %s", path)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)                          # atomic: clients never read a half-written file
    log.info("written: %s", path)
    return True


# ── Firebase (optional) ───────────────────────────────────────────────────────
def _firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return firebase_admin.get_app()
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if raw:
        cred = credentials.Certificate(json.loads(raw))
    elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    else:
        raise RuntimeError("no Firebase credentials (set FIREBASE_SERVICE_ACCOUNT secret)")
    return firebase_admin.initialize_app(cred)


def sync_firestore(offers: list[dict], catalogs: dict) -> None:
    from firebase_admin import firestore

    db = firestore.client(_firebase_app())
    for coll_name, docs in ((config.FIRESTORE_OFFERS_COLLECTION, {o["id"]: o for o in offers}),
                            (config.FIRESTORE_CATALOGS_COLLECTION, {c["id"]: c for c in catalogs["catalogs"]})):
        coll = db.collection(coll_name)
        existing = {d.id for d in coll.select([]).stream()}
        ops = [("set", i, d) for i, d in docs.items()] + [("del", i, None) for i in existing - docs.keys()]
        for start in range(0, len(ops), 450):  # Firestore batch limit = 500
            batch = db.batch()
            for op, doc_id, data in ops[start:start + 450]:
                ref = coll.document(doc_id)
                batch.set(ref, data) if op == "set" else batch.delete(ref)
            batch.commit()
        log.info("firestore %s: %d upserted, %d deleted", coll_name, len(docs), len(existing - docs.keys()))


def notify_new(res: HarvestResult) -> int:
    """One FCM push per store that received brand-new catalogs (never seen before)."""
    from firebase_admin import messaging

    _firebase_app()
    new = [c for c in res.catalogs if c.id not in res.previous and not c.stale]
    sent = 0
    for store in {c.store for c in new}:
        items = [c for c in new if c.store == store]
        cover = items[0].pages[0].url
        msg = messaging.Message(
            topic=config.FCM_TOPIC,
            notification=messaging.Notification(
                title=f"🛒 {store} yeni aktüel katalog!",
                body=", ".join(c.title for c in items)[:180],
                image=cover,
            ),
            data={"store": store, "catalog_id": items[0].id, "image_url": cover},
            android=messaging.AndroidConfig(priority="high"),
        )
        messaging.send(msg)
        sent += 1
    log.info("FCM: %d notifications sent", sent)
    return sent


# ── reporting ─────────────────────────────────────────────────────────────────
ICON = {"ok": "✅", "stale": "⚠️", "empty": "❌"}


def report(res: HarvestResult) -> str:
    lines = ["## 🛒 Catalog Harvest Report", "",
             "| Store | Status | Catalogs | Pages | Sources | Errors |", "|---|---|---|---|---|---|"]
    for key, h in res.health.items():
        lines.append(f"| {key} | {ICON[h.status]} {h.status} | {h.fresh}+{h.carried} | {h.pages} | "
                     f"{', '.join(sorted(h.sources)) or '—'} | {'; '.join(h.errors)[:120] or '—'} |")
    lines += ["", "| Store | Catalog | Valid | Pages | Source |", "|---|---|---|---|---|"]
    for c in res.catalogs:
        lines.append(f"| {c.store} | {c.title}{' *(stale)*' if c.stale else ''} | "
                     f"{c.valid_from:%d.%m}–{c.valid_to:%d.%m} | {len(c.pages)} | {c.source} |")
    md = "\n".join(lines)
    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")
    for key, h in res.health.items():          # GitHub annotations for degraded stores
        if h.status != "ok" and os.getenv("GITHUB_ACTIONS"):
            print(f"::warning title=Harvester::{key} produced no fresh catalogs ({h.status})")
    return md
