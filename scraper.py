import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re

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


# إعداد الـ Headers لتجنب الحظر من المواقع التركية
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

import json
import os

all_scraped_items = []

def save_to_firebase(store_name, title, img_url):
    """دالة مساعدة لحفظ العروض في الفايربيس وتجميعها في ملف JSON"""
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

# ─────────────── 1. كشط عروض BİM ───────────────
def scrape_bim():
    print("\n🔍 جاري سحب عروض متجر BİM...")
    url = "https://www.bim.com.tr/Categories/103/akilli-alisveris.aspx"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            offers = soup.find_all('div', class_='sub_brochure')
            for offer in offers:
                img_node = offer.find('img')
                if img_node:
                    img_url = "https://www.bim.com.tr" + img_node['src']
                    h2_node = offer.find('h2')
                    title = h2_node.text.strip() if h2_node else "عروض بيم الأسبوعية"
                    save_to_firebase("BİM", title, img_url)
        else:
            print(f"❌ فشل سحب عروض BİM (كود الاستجابة: {response.status_code})")
    except Exception as e:
        print(f"💥 خطأ في كشط BİM: {e}")

# ─────────────── 2. كشط عروض A101 ───────────────
def scrape_a101():
    print("\n🔍 جاري سحب عروض متجر A101...")
    url = "https://www.a101.com.tr"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'aldin-aldin' in src.lower() or 'katalog' in src.lower() or 'brosur' in src.lower():
                    if not src.startswith('http'):
                        src = "https:" + src if src.startswith('//') else "https://www.a101.com.tr" + src
                    save_to_firebase("A101", f"كتالوج A101 - صفحة {count}", src)
                    count += 1
        else:
            print(f"❌ فشل سحب عروض A101 (كود الاستجابة: {response.status_code})")
    except Exception as e:
        print(f"💥 خطأ في كشط A101: {e}")

# ─────────────── 3. كشط عروض ŞOK ───────────────
def scrape_sok():
    print("\n🔍 جاري سحب عروض متجر ŞOK...")
    url = "https://kurumsal.sokmarket.com.tr/haftanin-firsatlari/firsatlar"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            count = 1
            for img in images:
                src = img.get('src', '')
                if 'firsat' in src.lower() or 'aktuel' in src.lower() or 'kampanya' in src.lower():
                    if not src.startswith('http'):
                        src = "https://kurumsal.sokmarket.com.tr" + src
                    save_to_firebase("ŞOK", f"عروض شوك - صفحة {count}", src)
                    count += 1
        else:
            print(f"❌ فشل سحب عروض ŞOK (كود الاستجابة: {response.status_code})")
    except Exception as e:
        print(f"💥 خطأ في كشط ŞOK: {e}")

def save_json_file():
    """حفظ كافة العروض المسحوبة في ملف offers.json"""
    try:
        with open("offers.json", "w", encoding="utf-8") as f:
            json.dump(all_scraped_items, f, ensure_ascii=False, indent=2)
        print(f"\n📁 تم حفظ {len(all_scraped_items)} عرضاً بنجاح في ملف offers.json!")
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ ملف offers.json: {e}")

# 🚀 تشغيل الكاشط لجميع المتاجر متتالية
if __name__ == "__main__":
    print("🎬 بدء تشغيل نظام جلب العروض التلقائي الشامل...")
    scrape_bim()
    scrape_a101()
    scrape_sok()
    save_json_file()
    print("\n🏁 تم الانتهاء من تحديث كافة المتاجر بنجاح!")

