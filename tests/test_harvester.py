"""Offline unit tests:  python -m unittest discover -s tests"""
import struct
import unittest
from datetime import date

from harvester.dates import parse_tr_date, parse_tr_dates
from harvester.models import stable_id
from harvester.sources.aktuel_urunler import detect_store, order_pages
from harvester.sources.base import upgrade_image_url
from harvester.validate import image_size


class Dates(unittest.TestCase):
    def test_full(self):
        self.assertEqual(parse_tr_date("BİM 13 Ekim 2026 Aktüel Ürünler Kataloğu"), date(2026, 10, 13))
        self.assertEqual(parse_tr_date("ŞOK 26 AĞUSTOS 2026"), date(2026, 8, 26))

    def test_year_inference(self):
        self.assertEqual(parse_tr_date("29 Eylül Salı", ref=date(2026, 10, 5)), date(2026, 9, 29))
        self.assertEqual(parse_tr_date("2 Ocak Cuma", ref=date(2026, 12, 28)), date(2027, 1, 2))

    def test_range(self):
        self.assertEqual(parse_tr_dates("28 Eylül - 4 Ekim 2026"), [date(2026, 9, 28), date(2026, 10, 4)])
        self.assertEqual(parse_tr_dates("02-05 Ekim", ref=date(2026, 10, 5)), [date(2026, 10, 2), date(2026, 10, 5)])


class Urls(unittest.TestCase):
    def test_upgrade(self):
        self.assertEqual(upgrade_image_url("https://cdn1.bim.com.tr/uploads/afisler/k_ab.jpg"),
                         "https://cdn1.bim.com.tr/uploads/afisler/ab.jpg")
        self.assertEqual(upgrade_image_url("https://x.com/uploads/Bim-1-60x90.webp?v=2"),
                         "https://x.com/uploads/Bim-1.webp")

    def test_order(self):
        self.assertEqual(order_pages(["a-10.webp", "a-2.webp", "a-1.webp"]), ["a-1.webp", "a-2.webp", "a-10.webp"])

    def test_store(self):
        self.assertEqual(detect_store("ŞOK 3 Ekim 2026"), "sok")
        self.assertEqual(detect_store("BİM 6 Ekim"), "bim")
        self.assertEqual(detect_store("A101 8 Ekim"), "a101")
        self.assertIsNone(detect_store("Migros 8 Ekim"))

    def test_stable_id(self):
        self.assertEqual(stable_id("BİM", "2026-10-13"), stable_id("BİM", "2026-10-13"))


class ImageSize(unittest.TestCase):
    def test_png(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 940, 1410)
        self.assertEqual(image_size(png), (940, 1410))

    def test_jpeg(self):
        jpg = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + \
              b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 1410, 940) + b"\x00" * 12
        self.assertEqual(image_size(jpg), (940, 1410))


if __name__ == "__main__":
    unittest.main()
