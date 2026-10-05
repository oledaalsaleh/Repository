"""Central configuration. Everything tunable lives here (or in env vars)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# ── Output files (offers.json stays backward-compatible with the app & web) ──
OFFERS_FILE = ROOT_DIR / "offers.json"
CATALOGS_FILE = ROOT_DIR / "catalogs.json"

# ── HTTP ──────────────────────────────────────────────────────────────────────
USER_AGENT = os.getenv(
    "HARVESTER_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 AktuelHarvester/2.0",
)
REQUEST_TIMEOUT = (10, 25)          # (connect, read) seconds
MAX_RETRIES = 4
BACKOFF_FACTOR = 1.5                # 0s, 1.5s, 3s, 6s …
PER_HOST_MIN_INTERVAL = 0.8         # polite delay between requests to the same host
RESPECT_ROBOTS = os.getenv("HARVESTER_RESPECT_ROBOTS", "1") == "1"

# ── Validation ────────────────────────────────────────────────────────────────
MIN_IMAGE_WIDTH = 400               # anything smaller is a thumbnail / icon
MIN_IMAGE_HEIGHT = 400
VALIDATION_WORKERS = 8

# ── Lifecycle ─────────────────────────────────────────────────────────────────
DEFAULT_VALID_DAYS = 7              # aktüel products are on sale ~1 week (while stocks last)
MAX_UPCOMING_DAYS = 14              # ignore "catalogs" dated too far in the future
TIMEZONE = "Europe/Istanbul"


@dataclass(frozen=True)
class Store:
    key: str          # canonical key used in JSON  ("BİM", "A101", "ŞOK")
    slug: str         # ascii id                     ("bim", "a101", "sok")
    color: str        # brand colour for clients
    valid_days: int = DEFAULT_VALID_DAYS


STORES: dict[str, Store] = {
    "bim": Store("BİM", "bim", "#E30613"),
    "a101": Store("A101", "a101", "#00A0E3"),
    "sok": Store("ŞOK", "sok", "#FFC20E"),
}

# ── Firebase (optional) ───────────────────────────────────────────────────────
# Provide credentials via ONE of:
#   FIREBASE_SERVICE_ACCOUNT        → full JSON content (recommended for GitHub Secrets)
#   GOOGLE_APPLICATION_CREDENTIALS  → path to a JSON key file
FIRESTORE_OFFERS_COLLECTION = "all_offers"
FIRESTORE_CATALOGS_COLLECTION = "catalogs"
FCM_TOPIC = "daily_deals"
