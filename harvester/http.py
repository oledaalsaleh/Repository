"""Resilient, polite HTTP layer: retries + backoff, Retry-After, per-host throttling, robots.txt."""
from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger("harvester.http")


class PoliteSession:
    def __init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.BACKOFF_FACTOR,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        })
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    # ── politeness ────────────────────────────────────────────────────────────
    def _throttle(self, host: str, interval: float) -> None:
        with self._lock:
            wait = self._last_hit.get(host, 0) + interval - time.monotonic()
            self._last_hit[host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)

    def allowed(self, url: str) -> bool:
        if not config.RESPECT_ROBOTS:
            return True
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt", timeout=config.REQUEST_TIMEOUT)
                rp.parse(r.text.splitlines() if r.ok else [])
                self._robots[base] = rp
            except requests.RequestException:
                self._robots[base] = None          # unreachable robots.txt → allow
        rp = self._robots[base]
        return rp is None or rp.can_fetch(config.USER_AGENT, url)

    # ── public API ────────────────────────────────────────────────────────────
    def get(self, url: str, *, page: bool = True, **kw) -> requests.Response:
        """GET with throttling. `page=True` enforces robots.txt (images are exempt)."""
        if page and not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        interval = config.PER_HOST_MIN_INTERVAL if page else config.PER_HOST_MIN_INTERVAL / 4
        self._throttle(urlparse(url).netloc, interval)
        kw.setdefault("timeout", config.REQUEST_TIMEOUT)
        resp = self.session.get(url, **kw)
        log.debug("GET %s → %s", url, resp.status_code)
        return resp

    def get_text(self, url: str) -> str:
        r = self.get(url)
        r.raise_for_status()
        r.encoding = r.encoding or r.apparent_encoding
        return r.text
