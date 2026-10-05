"""Source adapters. Each adapter returns normalized Catalog objects for one or more stores.

Priority convention:  0 = official retailer site,  10 = aggregator.
Add a new source = add a class here and register it in `ALL_SOURCES`.
"""
from __future__ import annotations

from .aktuel_urunler import AktuelUrunlerRSS
from .base import Source
from .bim_official import BimOfficial
from .sok_official import SokOfficial

ALL_SOURCES: list[type[Source]] = [
    BimOfficial,
    SokOfficial,
    AktuelUrunlerRSS,
]

__all__ = ["ALL_SOURCES", "Source"]
