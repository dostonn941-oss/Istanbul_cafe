"""
Istanbul Cafe - Supabase Ma'lumotlar Bazasi Moduli
Supabase REST API (PostgREST) va Storage bilan to'g'ridan-to'g'ri integratsiya.
Lokal fayllar (menu.json, orders.json, settings.json) zaxira (fallback) sifatida avtomatik ishlatiladi.
"""

import os
import json
import logging
import requests
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)

# ==========================
# SUPABASE KONFIGURATSIYASI
# ==========================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jtzuytfxeakexupudxoy.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or "sb_publishable_0yEdTo2GGH0slSNwSB91sA_Zt8p75Xb"
).strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_FILE = os.path.join(BASE_DIR, "menu.json")
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def get_headers(prefer: Optional[str] = None) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def fmt_price(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so'm"


def ensure_dish_sticker(name: str, cat_key: str, custom_sticker: str = "") -> str:
    name = (name or "").strip()
    if not name:
        return name
    if ord(name[0]) > 127:
        return name
    sticker = custom_sticker.strip() if custom_sticker else "🍽"
    return f"{sticker} {name}".strip()


# ==============================================================================
# BAZA HOLATINI TEKSHIRISH (HEALTH CHECK)
# ==============================================================================

def check_supabase_connection() -> dict:
    """Supabase ulanishi va jadvallar mavjudligini tekshiradi."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"connected": False, "error": "SUPABASE_URL yoki SUPABASE_KEY topilmadi"}

    status = {
        "connected": False,
        "auth_ok": False,
        "tables": {
            "menu_categories": False,
            "menu_items": False,
            "orders": False,
            "cafe_settings": False
        },
        "storage": False
    }

    try:
        # Auth / API tekshirish
        auth_res = requests.get(f"{SUPABASE_URL}/auth/v1/health", headers=get_headers(), timeout=5)
        if auth_res.status_code == 200:
            status["auth_ok"] = True
            status["connected"] = True

        # Jadvallarni tekshirish
        for table in status["tables"].keys():
            res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=1", headers=get_headers(), timeout=5)
            if res.status_code == 200:
                status["tables"][table] = True
            else:
                status["tables"][table] = False

        # Storage tekshirish
        st_res = requests.get(f"{SUPABASE_URL}/storage/v1/bucket", headers=get_headers(), timeout=5)
        if st_res.status_code == 200:
            buckets = [b.get("id") for b in st_res.json() if isinstance(b, dict)]
            status["storage"] = "receipts" in buckets
    except Exception as e:
        status["error"] = str(e)

    return status


# ==============================================================================
# MENYU VA KATEGORIYALAR (MENU & CATEGORIES)
# ==============================================================================

def get_menu() -> Tuple[Dict[str, Tuple[str, str, int, str]], Dict[str, str]]:
    """
    Menyu va kategoriyalarni qaytaradi.
    Supabase jadvallaridan o'qishga harakat qiladi, aks holda menu.json dan oladi.
    """
    categories: Dict[str, str] = {}
    items: Dict[str, Tuple[str, str, int, str]] = {}

    supabase_success = False
    try:
        # 1. Supabase'dan kategoriyalarni olish
        cat_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/menu_categories?select=*&order=sort_order.asc",
            headers=get_headers(),
            timeout=5
        )
        if cat_res.status_code == 200:
            cat_data = cat_res.json()
            if isinstance(cat_data, list) and len(cat_data) > 0:
                for c in cat_data:
                    cat_id = c.get("id")
                    cat_name = c.get("name")
                    if cat_id and cat_name:
                        categories[cat_id] = cat_name

        # 2. Supabase'dan taomlarni olish
        item_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/menu_items?select=*&order=id.asc",
            headers=get_headers(),
            timeout=5
        )
        if item_res.status_code == 200:
            item_data = item_res.json()
            if isinstance(item_data, list) and len(item_data) > 0:
                for it in item_data:
                    it_id = str(it.get("id"))
                    name = it.get("name", "")
                    price = int(it.get("price", 0))
                    cat = it.get("category", "other")
                    items[it_id] = (name, fmt_price(price), price, cat)
                supabase_success = True
    except Exception as e:
        logger.warning(f"Supabase menyuni o'qishda ogohlantirish: {e}")

    # Agar Supabase bo'sh yoki xatolik bersa, menu.json dan olamiz
    if not supabase_success or not items:
        if os.path.exists(MENU_FILE):
            try:
                with open(MENU_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "categories" in data and isinstance(data["categories"], dict):
                        categories = data["categories"]
                    if "items" in data and isinstance(data["items"], dict):
                        new_items = {}
                        for k, v in data["items"].items():
                            p_num = int(v.get("price", 0))
                            cat = v.get("category", "other")
                            name = v.get("name", "")
                            new_items[k] = (name, fmt_price(p_num), p_num, cat)
                        if new_items:
                            items = new_items
            except Exception:
                logger.exception("menu.json o'qishda xatolik")

    return items, categories


def save_menu_to_local(items: dict, categories: dict):
    """Lokal menu.json ga saqlash."""
    try:
        data = {
            "categories": categories,
            "items": {}
        }
        for k, (name, price_str, price_num, cat) in items.items():
            data["items"][k] = {
                "name": name,
                "price": price_num,
                "category": cat
            }
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("menu.json yozishda xatolik")


def save_menu_item(item_id: str, name: str, price: int, category: str) -> bool:
    """Taomni Supabase va lokal faylga saqlaydi (upsert)."""
    # 1. Supabase ga saqlash
    try:
        payload = {
            "id": item_id,
            "name": name,
            "price": price,
            "category": category,
            "is_available": True
        }
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/menu_items",
            headers=get_headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
            timeout=5
        )
        if res.status_code in (200, 201):
            logger.info(f"Supabase: Taom saqlandi: {item_id}")
    except Exception as e:
        logger.warning(f"Supabase ga taom saqlashda xatolik: {e}")

    return True


def delete_menu_item(item_id: str) -> bool:
    """Taomni Supabase va lokal fayldan o'chiradi."""
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/menu_items?id=eq.{item_id}",
            headers=get_headers(prefer="return=representation"),
            timeout=5
        )
        if res.status_code in (200, 204):
            logger.info(f"Supabase: Taom o'chirildi: {item_id}")
    except Exception as e:
        logger.warning(f"Supabase dan taom o'chirishda xatolik: {e}")

    return True


def save_category(cat_id: str, name: str, sticker: str = "") -> bool:
    """Kategoriyani Supabase ga saqlaydi."""
    try:
        payload = {
            "id": cat_id,
            "name": name,
            "sticker": sticker
        }
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/menu_categories",
            headers=get_headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
            timeout=5
        )
        if res.status_code in (200, 201):
            logger.info(f"Supabase: Kategoriya saqlandi: {cat_id}")
    except Exception as e:
        logger.warning(f"Supabase ga kategoriya saqlashda xatolik: {e}")

    return True


def delete_category(cat_id: str) -> bool:
    """Kategoriyani Supabase dan o'chiradi."""
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/menu_categories?id=eq.{cat_id}",
            headers=get_headers(prefer="return=representation"),
            timeout=5
        )
        if res.status_code in (200, 204):
            logger.info(f"Supabase: Kategoriya o'chirildi: {cat_id}")
    except Exception as e:
        logger.warning(f"Supabase dan kategoriya o'chirishda xatolik: {e}")

    return True


# ==============================================================================
# SOZLAMALAR (SETTINGS)
# ==============================================================================

def get_settings() -> dict:
    """Kafe sozlamalarini oladi."""
    default_settings = {
        "card_number": os.environ.get("PAYME_CARD", "8600 1234 5678 9012"),
        "card_owner": os.environ.get("PAYME_OWNER", "Istanbul Cafe"),
        "is_open": True,
        "cafe_name": "Istanbul Cafe",
    }

    # 1. Supabase dan olish
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/cafe_settings?id=eq.1&select=*",
            headers=get_headers(),
            timeout=5
        )
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                row = data[0]
                return {
                    "card_number": row.get("card_number") or default_settings["card_number"],
                    "card_owner": row.get("card_owner") or default_settings["card_owner"],
                    "is_open": bool(row.get("is_open", True)),
                    "cafe_name": row.get("cafe_name") or default_settings["cafe_name"],
                }
    except Exception as e:
        logger.warning(f"Supabase sozlamalarini olishda xatolik: {e}")

    # 2. Lokal settings.json dan olish
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                if isinstance(local_data, dict):
                    default_settings.update(local_data)
        except Exception:
            pass

    return default_settings


def save_settings(settings_data: dict) -> bool:
    """Sozlamalarni Supabase va lokal faylga saqlaydi."""
    # Lokalga saqlash
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("settings.json saqlashda xatolik")

    # Supabase ga saqlash
    try:
        payload = {
            "id": 1,
            "card_number": settings_data.get("card_number"),
            "card_owner": settings_data.get("card_owner"),
            "is_open": bool(settings_data.get("is_open", True)),
            "cafe_name": settings_data.get("cafe_name", "Istanbul Cafe")
        }
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/cafe_settings",
            headers=get_headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
            timeout=5
        )
        if res.status_code in (200, 201):
            logger.info("Supabase: Sozlamalar saqlandi")
            return True
    except Exception as e:
        logger.warning(f"Supabase ga sozlamalar saqlashda xatolik: {e}")

    return True


# ==============================================================================
# BUYURTMALAR (ORDERS)
# ==============================================================================

def get_orders() -> List[dict]:
    """
    Barcha buyurtmalarni yangisidan eskisiga qarab saralab qaytaradi.
    """
    # 1. Supabase dan olish
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/orders?select=*&order=id.desc",
            headers=get_headers(),
            timeout=6
        )
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                # Formatlash
                for o in data:
                    if "items" in o and isinstance(o["items"], str):
                        try:
                            o["items"] = json.loads(o["items"])
                        except Exception:
                            pass
                return data
    except Exception as e:
        logger.warning(f"Supabase buyurtmalarini olishda ogohlantirish: {e}")

    # 2. Lokal orders.json dan olish
    orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
                for idx, o in enumerate(orders, 1):
                    if not o.get("id"):
                        o["id"] = idx
                    if not o.get("status"):
                        o["status"] = "new"
        except Exception:
            logger.exception("orders.json o'qishda xatolik")

    orders.reverse()
    return orders


def create_order(order_data: dict) -> int:
    """
    Yangi buyurtma yaratadi. Supabase ga saqlab, yangi ID ni qaytaradi.
    Lokal orders.json ga ham zaxira sifatida yozadi.
    """
    assigned_id = None

    # Supabase ga yuborish
    try:
        insert_payload = {
            "status": order_data.get("status", "new"),
            "timestamp": order_data.get("timestamp"),
            "customer": order_data.get("customer", "Mijoz"),
            "phone": order_data.get("phone", ""),
            "service": order_data.get("service", "pickup"),
            "location": order_data.get("location", ""),
            "payment": order_data.get("payment", ""),
            "card_number": order_data.get("card_number"),
            "card_owner": order_data.get("card_owner"),
            "payment_confirmed": bool(order_data.get("payment_confirmed", False)),
            "receipt_url": order_data.get("receipt_url"),
            "items": order_data.get("items", []),
            "total": int(order_data.get("total", 0)),
            "lat": order_data.get("lat"),
            "lng": order_data.get("lng"),
            "tg_user_id": order_data.get("tg_user_id")
        }
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/orders",
            headers=get_headers(prefer="return=representation"),
            json=insert_payload,
            timeout=7
        )
        if res.status_code in (200, 201):
            created_rows = res.json()
            if isinstance(created_rows, list) and len(created_rows) > 0:
                assigned_id = created_rows[0].get("id")
                logger.info(f"Supabase: Yangi buyurtma yaratildi (ID: #{assigned_id})")
    except Exception as e:
        logger.warning(f"Supabase ga buyurtma yozishda xatolik: {e}")

    # Lokal orders.json ga ham yozib qo'yamiz
    try:
        local_orders = []
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    local_orders = json.load(f)
            except Exception:
                local_orders = []

        if assigned_id is None:
            assigned_id = len(local_orders) + 1

        order_data["id"] = assigned_id
        local_orders.append(order_data)

        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(local_orders, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("orders.json ga saqlashda xatolik")

    return assigned_id or 1


def update_order_status(order_id: int, new_status: str) -> Optional[dict]:
    """
    Buyurtma holatini yangilaydi (new, cooking, delivering, completed, cancelled).
    Yangilangan buyurtma obyektini qaytaradi.
    """
    updated_order = None

    # 1. Supabase da yangilash
    try:
        res = requests.patch(
            f"{SUPABASE_URL}/rest/v1/orders?id=eq.{order_id}",
            headers=get_headers(prefer="return=representation"),
            json={"status": new_status},
            timeout=6
        )
        if res.status_code == 200:
            rows = res.json()
            if isinstance(rows, list) and len(rows) > 0:
                updated_order = rows[0]
                logger.info(f"Supabase: Buyurtma #{order_id} holati yangilandi -> {new_status}")
    except Exception as e:
        logger.warning(f"Supabase da buyurtma yangilashda ogohlantirish: {e}")

    # 2. Lokal orders.json da ham yangilash
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            found_idx = None
            for idx, o in enumerate(raw, 1):
                if o.get("id") == order_id or idx == order_id:
                    o["id"] = order_id
                    o["status"] = new_status
                    found_idx = idx
                    if not updated_order:
                        updated_order = o
                    break

            if found_idx is not None:
                with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(raw, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("orders.json yangilashda xatolik")

    return updated_order


def delete_order(order_id: int) -> bool:
    """Buyurtmani Supabase va lokal orders.json dan o'chiradi."""
    # 1. Supabase dan o'chirish
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/orders?id=eq.{order_id}",
            headers=get_headers(prefer="return=representation"),
            timeout=6
        )
        if res.status_code in (200, 204):
            logger.info(f"Supabase: Buyurtma #{order_id} o'chirildi")
    except Exception as e:
        logger.warning(f"Supabase dan buyurtma o'chirishda ogohlantirish: {e}")

    # 2. Lokal orders.json dan o'chirish
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            new_orders = []
            for idx, o in enumerate(raw, 1):
                cur_id = o.get("id") or idx
                if cur_id != order_id:
                    new_orders.append(o)

            with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(new_orders, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("orders.json dan o'chirishda xatolik")

    return True


# ==============================================================================
# STORAGE (TO'LOV CHEKLARINI YUKLASH)
# ==============================================================================

def upload_receipt(photo_bytes: bytes, filename: str) -> str:
    """
    To'lov chekini Supabase Storage 'receipts' bucketiga yuklaydi.
    Agar Supabase Storage ishlamasa, lokal /uploads/ papkasiga saqlaydi.
    Qaytaradi: rasmga to'g'ridan-to'g'ri URL yoki lokal nisbiy yo'l (/uploads/filename).
    """
    # 1. Lokalga doim zaxira sifatida saqlaymiz
    local_path = os.path.join(UPLOADS_DIR, filename)
    try:
        with open(local_path, "wb") as f:
            f.write(photo_bytes)
    except Exception:
        logger.exception("Lokal chek rasmini saqlashda xatolik")

    # 2. Supabase Storage ga yuklash
    try:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/receipts/{filename}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "image/jpeg",
            "x-upsert": "true"
        }
        res = requests.post(upload_url, headers=headers, data=photo_bytes, timeout=10)
        if res.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/receipts/{filename}"
            logger.info(f"Chek Supabase Storage ga muvaffaqiyatli yuklandi: {public_url}")
            return public_url
        else:
            logger.warning(f"Supabase Storage ga yuklash kodi: {res.status_code} - {res.text[:100]}")
    except Exception as e:
        logger.warning(f"Supabase Storage ga rasm yuklashda ogohlantirish: {e}")

    # Agar Supabase muvaffaqiyatsiz bo'lsa, lokal URL
    return f"/uploads/{filename}"
