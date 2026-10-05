# 🛒 Catalog Harvester — BİM · A101 · ŞOK

Collects aktüel catalog pages automatically, validates every image, and publishes
`offers.json` (flat, used by the Android app + web) and `catalogs.json` (grouped).

```
sources (official → aggregator) → window filter → dedupe by priority → validate images
        → last-known-good fallback → publish (JSON · Firestore · FCM) → CI report
```

| Store | Primary source | Fallback |
|---|---|---|
| BİM  | `bim.com.tr/Categories/680/afisler.aspx` (official, 940×1410) | aktuel-urunler RSS |
| A101 | aktuel-urunler RSS (official site is behind Cloudflare) | last-known-good |
| ŞOK  | `kurumsal.sokmarket.com.tr` (only if fresh ≤10 days) | aktuel-urunler RSS |

## Run

```bash
pip install -r requirements.txt
python -m harvester --dry-run                 # fetch + validate, write nothing
python -m harvester                           # write offers.json + catalogs.json
python -m harvester --stores a101,sok -v      # subset, verbose
python -m harvester --mirror bim/web/offers.json --mirror bim/app/src/main/assets/offers.json
FIREBASE_SERVICE_ACCOUNT="$(cat key.json)" python -m harvester --firestore --notify
python -m unittest tests.test_harvester
```

## Guarantees
- **Deterministic ids** (`sha1(store|valid_from|kind)`) → no duplicate notifications.
- **No empty overwrite**: zero results never replaces good data; a failing store keeps its
  still-valid catalogs (`"stale": true`).
- **No noise commits**: files are only rewritten when content changes (atomic write).
- **Polite**: robots.txt, per-host throttling, retries with backoff + `Retry-After`.
- **Validated**: every page returns 200, `image/*`, and ≥ 400×400 px (read from headers only).

## Add a new store / source
1. Add the store to `STORES` in `config.py`.
2. Create `sources/<name>.py` subclassing `Source`, return `Catalog` objects.
3. Register it in `sources/__init__.py` (`priority=0` official, `10` aggregator).
