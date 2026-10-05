"""
Catalog Harvester — production-grade aktüel catalog collector for BİM, A101 and ŞOK.

Pipeline:  sources (official → aggregator)  →  normalize  →  validate images
           →  merge / dedupe  →  last-known-good fallback  →  publish (JSON / Firestore / FCM)
"""

__version__ = "2.0.0"
