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

# 1. الاتصال بقاعدة بيانات Firebase (اختياري)
db = None
try:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("⚡ تم الاتصال بقاعدة بيانات Firebase بنجاح!", flush=True)
    else:
        print("ℹ️ ملف serviceAccountKey.json غير موجود، سيتم الحفظ محلياً في offers.json فقط.", flush=True)
except Exception as e:
    print(f"⚠️ خطأ في الاتصال بـ Firebase: {e}", flush=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

all_scraped_items = []
seen_images = set()

def save_offer(store_name, title, img_url, valid_date="Güncel"):
    """دالة حفظ العروض واستخراج الصور عالية الدقة"""
    try:
        if not img_url or img_url in seen_images:
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
        print(f"📸 [{store_name}] تم التقاط الكتالوج: {title}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ عنصر لـ {store_name}: {e}", flush=True)

# ─────────────── 1. سحب كافة الكتالوجات الأسبوعية عالية الدقة ───────────────
def scrape_all_catalogs():
    print("\n🔍 [1/3] جاري سحب أحدث الكتالوجات والبروشورات المعتمدة...", flush=True)
    url = "https://www.aktuelkataloglari.com/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            flyers = soup.find_all('img', class_='flyer-img')
            for img in flyers:
                src = img.get('src', '')
                alt = img.get('alt', 'Aktüel Kataloğu')
                
                # تحويل الصورة المصغرة لرابط الصورة الأصلية فائقة الدقة
                high_res_url = src.replace("-thumbnail.webp", ".webp").replace("-thumbnail.jpg", ".jpg")
                if not high_res_url.startswith('http'):
                    high_res_url = "https://www.aktuelkataloglari.com" + high_res_url
                
                # تصنيف المتجر
                alt_lower = alt.lower()
                store = "Diğer"
                if "bim" in alt_lower or "/1/1/" in src:
                    store = "BİM"
                elif "a101" in alt_lower or "/1/2/" in src:
                    store = "A101"
                elif "şok" in alt_lower or "sok" in alt_lower or "/1/10/" in src:
                    store = "ŞOK"
                elif "migros" in alt_lower or "/1/19/" in src:
                    store = "Migros"
                elif "koop" in alt_lower or "tarım" in alt_lower:
                    store = "Tarım Kredi"
                elif "hakmar" in alt_lower:
                    store = "Hakmar"
                else:
                    store = "Aktüel Market"
                
                save_offer(store, alt, high_res_url)
    except Exception as e:
        print(f"💥 خطأ في سحب الكتالوجات المجمعة: {e}", flush=True)

# ─────────────── 2. سحب عروض BİM الرسمية المباشرة ───────────────
def scrape_bim_official():
    print("\n🔍 [2/3] جاري التحقق من أحدث عروض BİM من السيرفر الرسمي...", flush=True)
    url = "https://www.bim.com.tr/Categories/100/aktuel-urunler.aspx"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for i, img in enumerate(soup.find_all('img'), 1):
                src = img.get('src', '')
                if 'uploads/aktuel-urunler' in src:
                    # تحويل لرابط الصورة الكاملة
                    big_url = src.replace('_kucuk_', '_buyuk_')
                    alt = img.get('alt') or f"عرض بيم الأسبوعي - صفحة {i}"
                    save_offer("BİM", alt, big_url)
    except Exception as e:
        print(f"💥 خطأ في كشط BİM الرسمي: {e}", flush=True)

# ─────────────── 3. سحب عروض ŞOK الرسمية المباشرة ───────────────
def scrape_sok_official():
    print("\n🔍 [3/3] جاري سحب عروض ŞOK الرسمية...", flush=True)
    url = "https://kurumsal.sokmarket.com.tr/haftanin-firsatlari/firsatlar"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            count = 1
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if '/uploads/' in src and src.endswith('.jpg'):
                    if not src.startswith('http'):
                        src = "https://kurumsal.sokmarket.com.tr" + src
                    save_offer("ŞOK", f"عروض شوك ماركت - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ في كشط ŞOK الرسمي: {e}", flush=True)

def save_json_file():
    """حفظ كافة العروض المسحوبة في ملف offers.json"""
    try:
        with open("offers.json", "w", encoding="utf-8") as f:
            json.dump(all_scraped_items, f, ensure_ascii=False, indent=2)
        print(f"\n📁 تم بنجاح تصدير وحفظ {len(all_scraped_items)} صفحة عرض في ملف offers.json!", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ ملف offers.json: {e}", flush=True)

def sync_to_firebase():
    if not db or not all_scraped_items:
        return
    print("\n☁️ جاري المزامنة مع Firebase Firestore...", flush=True)
    try:
        batch = db.batch()
        for item in all_scraped_items[:500]:
            doc_ref = db.collection("all_offers").document(item["id"])
            batch.set(doc_ref, item)
        batch.commit()
        print("⚡ تم تحديث قاعدة بيانات Firebase بنجاح!", flush=True)
    except Exception as e:
        print(f"⚠️ تخطي مزامنة Firebase: {e}", flush=True)

# 🚀 تشغيل الكاشط الشامل لجميع المتاجر
if __name__ == "__main__":
    print("🎬 بدء تشغيل نظام كشط الكتالوجات والعروض المتقدم...", flush=True)
    scrape_all_catalogs()
    scrape_bim_official()
    scrape_sok_official()
    save_json_file()
    sync_to_firebase()
    print("\n🏁 تم الانتهاء من تحديث كافة المتاجر بنجاح!", flush=True)
