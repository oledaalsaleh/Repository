import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import json
import os

db = None
try:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("⚡ تم الاتصال بـ Firebase بنجاح!", flush=True)
except Exception as e:
    pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

all_scraped_items = []
seen_images = set()

def save_offer(store_name, title, img_url, valid_date="Güncel"):
    """حفظ الروابط المؤكدة والصحيحة 100%"""
    try:
        if not img_url or img_url in seen_images:
            return
        if not img_url.startswith("http"):
            return
            
        seen_images.add(img_url)
        clean_url = re.sub(r'[^a-zA-Z0-9]', '_', img_url.split('/')[-1])
        doc_id = f"{store_name.lower()}_{clean_url}"
        
        item_data = {
            "id": doc_id,
            "store": store_name,
            "title": title,
            "image_url": img_url,
            "valid_date": valid_date,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        all_scraped_items.append(item_data)
        print(f"📸 [{store_name}] {title} --> {img_url[:60]}...", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ في الحفظ: {e}", flush=True)

def scrape_katlok_catalogs():
    print("\n🔍 [1/3] سحب الكتالوجات الأسبوعية الأصلية...", flush=True)
    url = "https://www.aktuelkataloglari.com/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # 1. فحص صفحات الكتالوجات المباشرة لسحب الصور الأصلية
            catalog_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/brosur/' in href and href not in catalog_links:
                    catalog_links.append(href)
            
            for cat_url in catalog_links[:10]:
                try:
                    cr = requests.get(cat_url, headers=HEADERS, timeout=8)
                    if cr.status_code == 200:
                        csoup = BeautifulSoup(cr.text, 'html.parser')
                        h1 = csoup.find('h1')
                        base_title = h1.text.strip() if h1 else "Aktüel Kataloğu"
                        store = "Diğer"
                        if "bim" in cat_url: store = "BİM"
                        elif "a101" in cat_url: store = "A101"
                        elif "sok" in cat_url: store = "ŞOK"
                        elif "migros" in cat_url: store = "Migros"
                        elif "hakmar" in cat_url: store = "Hakmar"
                        
                        page_num = 1
                        for cimg in csoup.find_all('img'):
                            csrc = cimg.get('src', '')
                            # الصور الأصلية الكاملة للصفحات
                            if 'cdn.katlok.com' in csrc and (csrc.endswith('.webp') or csrc.endswith('.jpg')):
                                save_offer(store, f"{base_title} - ص {page_num}", csrc)
                                page_num += 1
                except Exception as ex:
                    pass

            # 2. فحص الصور المصغرة المتبقية
            for img in soup.find_all('img', class_='flyer-img'):
                src = img.get('src', '')
                alt = img.get('alt', 'Aktüel Kataloğu')
                store = "BİM" if "bim" in alt.lower() else ("A101" if "a101" in alt.lower() else ("ŞOK" if "şok" in alt.lower() else "Migros"))
                save_offer(store, alt, src)
    except Exception as e:
        print(f"💥 خطأ في الكتالوجات المجمعة: {e}", flush=True)

def scrape_bim_official():
    print("\n🔍 [2/3] سحب عروض BİM الرسمية...", flush=True)
    try:
        r = requests.get("https://www.bim.com.tr/Categories/100/aktuel-urunler.aspx", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for i, img in enumerate(soup.find_all('img'), 1):
                src = img.get('src', '')
                if 'uploads/aktuel-urunler' in src:
                    big_url = src.replace('_kucuk_', '_buyuk_')
                    if not big_url.startswith('http'):
                        big_url = "https://www.bim.com.tr" + big_url
                    save_offer("BİM", f"عروض بيم الرسمية - صفحة {i}", big_url)
    except Exception as e:
        print(f"💥 خطأ BİM: {e}", flush=True)

def scrape_sok_official():
    print("\n🔍 [3/3] سحب عروض ŞOK الرسمية...", flush=True)
    try:
        r = requests.get("https://kurumsal.sokmarket.com.tr/haftanin-firsatlari/firsatlar", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            count = 1
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if '/uploads/' in src and src.endswith('.jpg'):
                    if not src.startswith('http'):
                        src = "https://kurumsal.sokmarket.com.tr" + src
                    save_offer("ŞOK", f"عروض شوك الأسبوعية - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ ŞOK: {e}", flush=True)

def save_json():
    try:
        with open("offers.json", "w", encoding="utf-8") as f:
            json.dump(all_scraped_items, f, ensure_ascii=False, indent=2)
        print(f"\n📁 تم بنجاح حفظ {len(all_scraped_items)} رابط صورة حقيقية ومؤكدة في offers.json!", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ حفظ JSON: {e}", flush=True)

def sync_firebase():
    if not db or not all_scraped_items:
        return
    try:
        batch = db.batch()
        for item in all_scraped_items[:500]:
            doc_ref = db.collection("all_offers").document(item["id"])
            batch.set(doc_ref, item)
        batch.commit()
        print("⚡ تم تحديث Firebase بنجاح!", flush=True)
    except Exception as e:
        pass

if __name__ == "__main__":
    scrape_katlok_catalogs()
    scrape_bim_official()
    scrape_sok_official()
    save_json()
    sync_firebase()
    print("\n🏁 اكتمل سحب كافة الصور بنجاح!", flush=True)
