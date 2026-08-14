import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import json
import os

# 1. الاتصال بقاعدة بيانات Firebase (اختياري وآمن)
db = None
try:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("⚡ تم الاتصال بقاعدة بيانات Firebase بنجاح!")
    else:
        print("ℹ️ ملف serviceAccountKey.json غير موجود، سيتم الحفظ محلياً في offers.json فقط.")
except Exception as e:
    print(f"⚠️ خطأ في الاتصال بـ Firebase: {e}")

# إعداد الـ Headers لتجنب الحظر
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

all_scraped_items = []

def save_offer(store_name, title, img_url, valid_date="Güncel"):
    """دالة مساعدة لحفظ العروض في الفايربيس وقائمة JSON"""
    try:
        if not img_url:
            return
            
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
        
        if db:
            db.collection("all_offers").document(doc_id).set(item_data)
            print(f"✅ [{store_name}] تم حفظ: {title}")
        else:
            print(f"📦 [{store_name}] تم التقاط: {title}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ عنصر لـ {store_name}: {e}")

# ─────────────── 1. كشط عروض BİM (الموقع الرسمي + الكتالوجات) ───────────────
def scrape_bim():
    print("\n🔍 [1/5] جاري سحب عروض متجر BİM...")
    urls = [
        ("https://www.bim.com.tr/Categories/100/aktuel-urunler.aspx", "عروض بيم الرسمية"),
        ("https://www.bim.com.tr/Categories/103/akilli-alisveris.aspx", "عروض بيم الذكية")
    ]
    for url, default_title in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                offers = soup.find_all('div', class_='sub_brochure')
                for i, offer in enumerate(offers, 1):
                    img_node = offer.find('img')
                    if img_node and img_node.get('src'):
                        src = img_node['src']
                        img_url = src if src.startswith('http') else "https://www.bim.com.tr" + src
                        h2_node = offer.find('h2')
                        title = h2_node.text.strip() if h2_node else f"{default_title} - صفحة {i}"
                        save_offer("BİM", title, img_url)
        except Exception as e:
            print(f"💥 خطأ في كشط BİM ({url}): {e}")

# ─────────────── 2. كشط عروض A101 ───────────────
def scrape_a101():
    print("\n🔍 [2/5] جاري سحب عروض متجر A101 (Aldın Aldın)...")
    url = "https://www.a101.com.tr"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'aldin-aldin' in src.lower() or 'katalog' in src.lower() or 'brosur' in src.lower() or 'afis' in src.lower():
                    if not src.startswith('http'):
                        src = "https:" + src if src.startswith('//') else "https://www.a101.com.tr" + src
                    save_offer("A101", f"كتالوج A101 Aldın Aldın - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ في كشط A101: {e}")

# ─────────────── 3. كشط عروض ŞOK ───────────────
def scrape_sok():
    print("\n🔍 [3/5] جاري سحب عروض متجر ŞOK...")
    url = "https://kurumsal.sokmarket.com.tr/haftanin-firsatlari/firsatlar"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'firsat' in src.lower() or 'aktuel' in src.lower() or 'kampanya' in src.lower() or 'hafta' in src.lower():
                    if not src.startswith('http'):
                        src = "https://kurumsal.sokmarket.com.tr" + src
                    save_offer("ŞOK", f"عروض شوك الأسبوعية - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ في كشط ŞOK: {e}")

# ─────────────── 4. كشط عروض Migros ───────────────
def scrape_migros():
    print("\n🔍 [4/5] جاري سحب مجلات عروض Migros (Migroskop)...")
    url = "https://www.migros.com.tr"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'migroskop' in src.lower() or 'kampanya' in src.lower() or 'katalog' in src.lower():
                    if not src.startswith('http'):
                        src = "https:" + src if src.startswith('//') else "https://www.migros.com.tr" + src
                    save_offer("Migros", f"مجلة ميجروس Migroskop - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ في كشط Migros: {e}")

# ─────────────── 5. كشط عروض Tarım Kredi ───────────────
def scrape_tarim_kredi():
    print("\n🔍 [5/5] جاري سحب عروض Tarım Kredi...")
    url = "https://www.tarimkredi.org.tr"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'indirim' in src.lower() or 'katalog' in src.lower() or 'afis' in src.lower() or 'aktuel' in src.lower():
                    if not src.startswith('http'):
                        src = "https:" + src if src.startswith('//') else "https://www.tarimkredi.org.tr" + src
                    save_offer("Tarım Kredi", f"عروض الائتمان الزراعي - صفحة {count}", src)
                    count += 1
    except Exception as e:
        print(f"💥 خطأ في كشط Tarım Kredi: {e}")

def save_json_file():
    """حفظ كافة العروض المسحوبة في ملف offers.json"""
    try:
        with open("offers.json", "w", encoding="utf-8") as f:
            json.dump(all_scraped_items, f, ensure_ascii=False, indent=2)
        print(f"\n📁 تم بنجاح تصدير وحفظ {len(all_scraped_items)} صفحة عرض في ملف offers.json!")
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ ملف offers.json: {e}")

# 🚀 تشغيل الكاشط الشامل لجميع المتاجر
if __name__ == "__main__":
    print("🎬 بدء تشغيل نظام كشط الكتالوجات والعروض المتقدم...")
    scrape_bim()
    scrape_a101()
    scrape_sok()
    scrape_migros()
    scrape_tarim_kredi()
    save_json_file()
    print("\n🏁 تم الانتهاء من تحديث كافة المتاجر بنجاح!")
