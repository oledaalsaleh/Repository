"""CLI:  python -m harvester [--dry-run] [--stores bim,a101,sok] [--firestore] [--notify] [--mirror PATH]..."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config, pipeline, publish


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harvester", description="BİM / A101 / ŞOK catalog harvester")
    ap.add_argument("--stores", default=",".join(config.STORES), help="comma list: bim,a101,sok")
    ap.add_argument("--dry-run", action="store_true", help="fetch + validate, write nothing")
    ap.add_argument("--no-validate", action="store_true", help="skip image validation (faster, riskier)")
    ap.add_argument("--firestore", action="store_true", help="sync Firestore collections")
    ap.add_argument("--notify", action="store_true", help="FCM push for brand-new catalogs")
    ap.add_argument("--mirror", action="append", default=[], type=Path,
                    help="extra path(s) to copy offers.json to (e.g. app assets, web/)")
    ap.add_argument("--strict", action="store_true", help="exit 2 if any store has no fresh data")
    ap.add_argument("--force", action="store_true", help="sync Firestore even if files are unchanged")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("harvester")

    stores = {s.strip() for s in args.stores.split(",") if s.strip() in config.STORES}
    res = pipeline.run(stores, validate=not args.no_validate)

    if not res.catalogs:                       # never overwrite good data with an empty result
        print(publish.report(res))
        log.error("no catalogs at all — previous files left untouched")
        return 1

    catalogs = publish.build_catalogs_json(res)
    offers = publish.build_offers_json(res)
    changed = publish.write_json(config.CATALOGS_FILE, catalogs, args.dry_run)
    changed |= publish.write_json(config.OFFERS_FILE, offers, args.dry_run)
    for path in args.mirror:
        publish.write_json(path, offers, args.dry_run)

    if not args.dry_run and (changed or args.force):
        if args.firestore:
            try:
                publish.sync_firestore(offers, catalogs)
            except Exception as exc:
                log.error("firestore sync failed: %s", exc)
        if args.notify:
            try:
                publish.notify_new(res)
            except Exception as exc:
                log.error("FCM failed: %s", exc)

    print(publish.report(res))

    if args.strict and any(h.status != "ok" for h in res.health.values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
