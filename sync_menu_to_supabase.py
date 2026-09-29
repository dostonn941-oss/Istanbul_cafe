import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "https://jtzuytfxeakexupudxoy.supabase.co").rstrip("/")
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "sb_publishable_0yEdTo2GGH0slSNwSB91sA_Zt8p75Xb").strip()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation"
}

def sync():
    print("=" * 60)
    print("ISTANBUL CAFE -> SUPABASE MENYU YUKLASH")
    print(f"Supabase URL: {SUPABASE_URL}")
    print("=" * 60)

    # 1. Baza holatini tekshirish
    test_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/menu_categories?select=id&limit=1",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        timeout=10
    )

    if test_res.status_code == 404:
        print("\n[OGOHLANTIRISH] 'menu_categories' jadvali Supabase'da hali yaratilmagan!")
        print("Sababi: Supabase REST API (Publishable key) orqali jadval yaratish mumkin emas.")
        print("Jadvallarni yaratish uchun quyidagi 1 martalik amalni bajaring:")
        print("1. https://supabase.com/dashboard ga kiring va loyihangizni oching.")
        print("2. Chap menyudan 'SQL Editor' bo'limiga kiring.")
        print("3. Loyihadagi 'supabase_schema.sql' fayli ichidagi barcha SQL kodni nusxalab, 'Run' tugmasini bosing.")
        print("4. Shundan so'ng ushbu skriptni qayta ishga tushiring: python sync_menu_to_supabase.py")
        return False

    if test_res.status_code not in (200, 206):
        print(f"\n[XATOLIK] Supabase'ga ulanib bo'lmadi! Status: {test_res.status_code}")
        print(f"Javob: {test_res.text}")
        return False

    print("\n[OK] Supabase jadvallari mavjud. Menyu yuklanmoqda...")

    # 2. menu.json dan o'qish
    with open("menu.json", "r", encoding="utf-8") as f:
        menu_data = json.load(f)

    categories = menu_data.get("categories", {})
    items = menu_data.get("items", {})

    # 3. Kategoriyalarni yuklash
    cat_payload = []
    order = 1
    for cat_id, cat_name in categories.items():
        sticker = cat_name.split()[0] if cat_name else "🍽"
        cat_payload.append({
            "id": cat_id,
            "name": cat_name,
            "sticker": sticker,
            "sort_order": order
        })
        order += 1

    cat_res = requests.post(
        f"{SUPABASE_URL}/rest/v1/menu_categories",
        headers=HEADERS,
        json=cat_payload,
        timeout=10
    )
    if cat_res.status_code in (200, 201):
        print(f"[OK] {len(cat_payload)} ta kategoriya Supabase'ga yuklandi!")
    else:
        print(f"[XATO] Kategoriyalarni yuklashda xatolik: {cat_res.status_code} - {cat_res.text}")

    # 4. Taomlarni yuklash
    item_payload = []
    for item_id, item_info in items.items():
        item_payload.append({
            "id": item_id,
            "name": item_info.get("name"),
            "price": item_info.get("price"),
            "category": item_info.get("category"),
            "is_available": True
        })

    item_res = requests.post(
        f"{SUPABASE_URL}/rest/v1/menu_items",
        headers=HEADERS,
        json=item_payload,
        timeout=10
    )
    if item_res.status_code in (200, 201):
        print(f"[OK] {len(item_payload)} ta taom Supabase'ga yuklandi!")
    else:
        print(f"[XATO] Taomlarni yuklashda xatolik: {item_res.status_code} - {item_res.text}")

    print("\n[MUVOFAQIYATLI] Istanbul Cafe menyusi Supabase bilan to'liq ulandi!")
    return True

if __name__ == "__main__":
    sync()
