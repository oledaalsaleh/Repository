"""Image validation without heavy deps: status + content-type + real pixel size from headers.

Only the first bytes of each image are downloaded (JPEG SOF / PNG IHDR / WebP VP8* chunk),
so validating 100 pages costs a few MB instead of 30+ MB.
"""
from __future__ import annotations

import logging
import struct
from concurrent.futures import ThreadPoolExecutor

from . import config
from .http import PoliteSession
from .models import Catalog, Page

log = logging.getLogger("harvester.validate")
HEAD_BYTES = 64 * 1024
MAX_BYTES = 512 * 1024


def image_size(data: bytes) -> tuple[int, int] | None:
    """Return (width, height) for PNG / JPEG / WebP / GIF, or None if not yet determinable."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return w, h
        if chunk == b"VP8X":
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + seg_len
    return None


def probe(http: PoliteSession, page: Page) -> Page:
    try:
        with http.get(page.url, page=False, stream=True) as r:
            ctype = r.headers.get("content-type", "")
            if r.status_code != 200 or not ctype.startswith("image/"):
                page.valid = False
                log.warning("✗ %s → %s %s", page.url, r.status_code, ctype)
                return page
            buf, size = b"", None
            for chunk in r.iter_content(8192):
                buf += chunk
                size = image_size(buf) if len(buf) >= 32 else None
                if size or len(buf) >= MAX_BYTES:
                    break
            if size := image_size(buf):
                page.width, page.height = size
                page.valid = size[0] >= config.MIN_IMAGE_WIDTH and size[1] >= config.MIN_IMAGE_HEIGHT
                if not page.valid:
                    log.warning("✗ too small %sx%s %s", *size, page.url)
            else:
                page.valid = True          # unknown format but served as an image → accept
    except Exception as exc:
        page.valid = False
        log.warning("✗ %s → %s", page.url, exc)
    return page


def validate_catalogs(http: PoliteSession, catalogs: list[Catalog]) -> None:
    """Validate every page in parallel, drop broken pages, renumber, drop empty catalogs."""
    pages = [p for c in catalogs for p in c.pages]
    with ThreadPoolExecutor(max_workers=config.VALIDATION_WORKERS) as pool:
        list(pool.map(lambda p: probe(http, p), pages))
    for c in catalogs:
        c.pages = [p for p in c.pages if p.valid]
        for i, p in enumerate(c.pages, 1):
            p.index = i
