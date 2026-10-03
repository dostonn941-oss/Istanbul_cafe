import os
import html
import asyncio
import logging
import requests
from typing import Optional
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# .env yuklash
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import supabase_db

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================
# SOZLAMALAR (SETTINGS)
# ==========================
TOKEN = os.environ.get("BOT_TOKEN", "8728959771:AAE7gczpAq26lFuHMQfigxwzF6n3Ix6_06Y")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8469252037"))
DEFAULT_RENDER_URL = "https://istanbul-cafe.onrender.com"
WEB_APP_URL = (os.environ.get("WEB_URL") or os.environ.get("RENDER_EXTERNAL_URL") or DEFAULT_RENDER_URL).strip()
TUNNEL_PROCESS = None
ACTUAL_FLASK_PORT = None

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jtzuytfxeakexupudxoy.supabase.co").strip()
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or "sb_publishable_0yEdTo2GGH0slSNwSB91sA_Zt8p75Xb"
).strip()

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable topilmadi! "
        "Render dashboard -> Environment bo'limiga BOT_TOKEN qo'shing."
    )

tg_application = None
MAIN_LOOP = None

# ==========================
# MENYU MA'LUMOTLARI (Telegram va Veb uchun - Emojilar bilan)
# ==========================
MENU_ITEMS = {
    "bg1": ("🍔 Istanbul Burger", "36 000 so'm", 36000, "burger"),
    "bg2": ("🍔 Istanbul Cheese Burger", "32 000 so'm", 32000, "burger"),
    "bg3": ("🍔 Istanbul Big Burger", "38 000 so'm", 38000, "burger"),
    "bg4": ("🍔 Crispy Chicken Burger", "28 000 so'm", 28000, "burger"),
    "lv1": ("🥙 Istanbul Lavash (Mol go'shti)", "32 000 so'm", 32000, "lavash"),
    "lv2": ("🥙 Istanbul Pishloqli Lavash", "35 000 so'm", 35000, "lavash"),
    "lv3": ("🥙 Istanbul Tovuqli Lavash", "28 000 so'm", 28000, "lavash"),
    "lv4": ("🥙 Tandir Doner Lavash", "30 000 so'm", 30000, "lavash"),
    "hd1": ("🌭 Istanbul Klassik Hot-Dog", "18 000 so'm", 18000, "hotdog"),
    "hd2": ("🌭 Istanbul Pishloqli Hot-Dog", "22 000 so'm", 22000, "hotdog"),
    "hd3": ("🌭 Istanbul Double Hot-Dog", "25 000 so'm", 25000, "hotdog"),
    "pz1": ("🍕 Istanbul Maxsus Pizza", "55 000 so'm", 55000, "pizza"),
    "pz2": ("🍕 Pepperoni Supreme", "50 000 so'm", 50000, "pizza"),
    "pz3": ("🍕 BBQ Chicken Pizza", "48 000 so'm", 48000, "pizza"),
    "pz4": ("🍕 4 Pishloqli Pizza", "52 000 so'm", 52000, "pizza"),
    "kb1": ("🥩 Istanbul Doner Kebab", "28 000 so'm", 28000, "kebab"),
    "kb2": ("🥩 Iskender Kebab", "38 000 so'm", 38000, "kebab"),
    "kb3": ("🥩 Adana Kebab", "32 000 so'm", 32000, "kebab"),
    "kb4": ("🥩 Tovuq Shish Kebab", "28 000 so'm", 28000, "kebab"),
    "sn1": ("🍟 Fri kartoshkasi", "15 000 so'm", 15000, "drinks"),
    "sn2": ("🍗 Qarsildoq Naggets (6 dona)", "18 000 so'm", 18000, "drinks"),
    "ot4": ("🥤 Coca-Cola 0.5L", "10 000 so'm", 10000, "drinks"),
    "ot5": ("🥤 Fanta Orange 0.5L", "10 000 so'm", 10000, "drinks"),
    "ot6": ("🥤 Muzdek Turk Ayrani", "7 000 so'm", 7000, "drinks"),
}

CATEGORY_NAMES = {
    "burger": "🍔 Burgerlar",
    "lavash": "🥙 Lavash va Doner",
    "hotdog": "🌭 Hot-doglar",
    "pizza": "🍕 Pitsalar",
    "kebab": "🥩 Doner & Kebablar",
    "drinks": "🥤 Ichimliklar va gazaklar",
}

PAYMENT_OPTIONS = {
    "pay_cash": "💵 Naqd pul",
    "pay_click": "💳 Click / Plastik karta",
}

def fmt_price(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so'm"


def get_category_sticker(cat_key: str) -> str:
    """Kategoriyadan uning birinchi emojisi (stikerini) ajratib oladi."""
    cat_text = CATEGORY_NAMES.get(cat_key, "").strip()
    if not cat_text:
        return "🍽"
    parts = cat_text.split(" ", 1)
    if parts and any(ord(c) > 127 for c in parts[0]):
        return parts[0]
    return "🍽"


def ensure_dish_sticker(name: str, cat_key: str, custom_sticker: str = "") -> str:
    """Taom nomiga kategoriya yoki berilgan stikerni avtomatik biriktiradi."""
    name = (name or "").strip()
    if not name:
        return name
    # Agar nom boshida allaqachon emoji (stiker) bo'lsa, o'zgartirmaymiz
    if ord(name[0]) > 127:
        return name
    sticker = custom_sticker.strip() if custom_sticker else get_category_sticker(cat_key)
    if not sticker:
        sticker = get_category_sticker(cat_key)
    return f"{sticker} {name}".strip()


MENU_FILE = os.path.join(os.path.dirname(__file__), "menu.json")

def load_menu():
    global MENU_ITEMS, CATEGORY_NAMES
    try:
        items, categories = supabase_db.get_menu()
        if items:
            MENU_ITEMS = items
        if categories:
            CATEGORY_NAMES = categories
    except Exception:
        logger.exception("Menyuni yuklashda xatolik")

def save_menu():
    try:
        supabase_db.save_menu_to_local(MENU_ITEMS, CATEGORY_NAMES)
    except Exception:
        logger.exception("menu.json yozishda xatolik")

# Dastlabki menyuni yuklab olish
load_menu()

# ==========================
# SOZLAMALAR (SETTINGS)
# ==========================
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
CAFE_SETTINGS = {
    "card_number": os.environ.get("PAYME_CARD", "8600 1234 5678 9012"),
    "card_owner": os.environ.get("PAYME_OWNER", "Istanbul Cafe"),
    "is_open": True,
    "cafe_name": "Istanbul Cafe",
}

def load_settings():
    global CAFE_SETTINGS, PAYME_CARD, PAYME_OWNER
    try:
        CAFE_SETTINGS = supabase_db.get_settings()
        PAYME_CARD = CAFE_SETTINGS.get("card_number", "8600 1234 5678 9012")
        PAYME_OWNER = CAFE_SETTINGS.get("card_owner", "Istanbul Cafe")
    except Exception:
        logger.exception("Sozlamalarni yuklashda xatolik")

def save_settings():
    try:
        supabase_db.save_settings(CAFE_SETTINGS)
    except Exception:
        logger.exception("settings saqlashda xatolik")

PAYME_CARD = "8600 1234 5678 9012"
PAYME_OWNER = "Istanbul Cafe"
load_settings()


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Koordinatalarni manzil matniga aylantiradi."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
            headers={"User-Agent": "IstanbulCafeBot/2.0"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            display_name = data.get("display_name", "")
            address = data.get("address", {})
            road = address.get("road") or address.get("street") or ""
            house_number = address.get("house_number", "")
            suburb = address.get("suburb") or address.get("neighbourhood") or address.get("residential") or ""
            city = address.get("city") or address.get("town") or address.get("village") or address.get("county") or ""
            parts = [p for p in [city, suburb, road, house_number] if p]
            if parts:
                return ", ".join(parts)
            return display_name if display_name else None
    except Exception:
        pass
    return None


# ==========================
# FLASK VEB ILOVASI
# ==========================
flask_app = Flask(__name__)

@flask_app.after_request
def add_cors_and_security_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    # Telegram WebApp iframe ichida to'siqsiz ochilishi uchun
    response.headers.pop("X-Frame-Options", None)
    return response


@flask_app.route("/healthz")
def health_check():
    return jsonify({"status": "ok", "service": "istanbul-cafe"}), 200


@flask_app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@flask_app.route('/<path:path>', methods=['OPTIONS'])
def options_preflight(path):
    return "", 204

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


@flask_app.route("/")
def index():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Istanbul Cafe</h1><p>Veb-sahifa topilmadi.</p>"


@flask_app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)


@flask_app.route("/api/menu")
def api_menu():
    items = []
    for item_id, (name, price_text, price_num, cat) in MENU_ITEMS.items():
        items.append({
            "id": item_id,
            "name": name,
            "price_text": price_text,
            "price": price_num,
            "category": cat,
            "category_name": CATEGORY_NAMES.get(cat, cat),
            "category_sticker": get_category_sticker(cat)
        })
    return jsonify({"success": True, "items": items, "categories": CATEGORY_NAMES})


@flask_app.route("/api/reverse-geocode")
def api_reverse_geocode():
    lat_val = request.args.get("lat")
    lon_val = request.args.get("lon")
    if not lat_val or not lon_val:
        return jsonify({"success": False, "error": "lat va lon parametrlari kerak"}), 400
    try:
        lat = float(lat_val)
        lon = float(lon_val)
        addr = reverse_geocode(lat, lon)
        if not addr:
            addr = f"Koordinata: {lat:.5f}, {lon:.5f}"
        return jsonify({"success": True, "address": addr, "lat": lat, "lon": lon})
    except Exception:
        return jsonify({"success": True, "address": f"Koordinata: {lat_val}, {lon_val}", "lat": lat_val, "lon": lon_val})


def send_telegram_message_sync(chat_id: int, text: str, retries: int = 3, timeout: int = 15) -> bool:
    if not TOKEN:
        return False
    import time
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=timeout
            )
            if r.status_code == 200:
                return True
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                logger.warning(f"Telegramga xabar yuborishda xatolik (chat_id: {chat_id}): {e}")
    return False


def send_telegram_photo_sync(chat_id: int, caption: str, photo_bytes: bytes, retries: int = 3, timeout: int = 20) -> bool:
    if not TOKEN:
        return False
    import time
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("receipt.jpg", photo_bytes, "image/jpeg")},
                timeout=timeout
            )
            if r.status_code == 200:
                return True
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                logger.warning(f"Telegramga rasm yuborishda xatolik: {e}")
    return False


def dispatch_order_notifications(admin_msg: str, customer_msg: Optional[str] = None, customer_id: Optional[int] = None, photo_bytes: Optional[bytes] = None):
    import threading
    def _worker():
        if photo_bytes:
            send_telegram_photo_sync(ADMIN_ID, admin_msg, photo_bytes)
        else:
            send_telegram_message_sync(ADMIN_ID, admin_msg)
            
        if customer_msg and customer_id and str(customer_id) != str(ADMIN_ID):
            send_telegram_message_sync(customer_id, customer_msg)

    threading.Thread(target=_worker, daemon=True).start()


@flask_app.route("/api/order", methods=["POST"])
def api_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Ma'lumot topilmadi"}), 400

    items = data.get("items")
    if not items or not isinstance(items, list):
        return jsonify({"success": False, "error": "Savatda mahsulot yo'q"}), 400

    phone = (data.get("phone") or "").strip()
    if not phone:
        return jsonify({"success": False, "error": "Telefon raqami kiritilmagan"}), 400

    service = html.escape(str(data.get("service", "delivery")))
    location = (data.get("location") or "").strip()
    if service == "delivery" and not location:
        return jsonify({"success": False, "error": "Yetkazib berish manzili kiritilmagan"}), 400
    if not location:
        location = "Filialdan olib ketish"

    def esc(v):
        return html.escape(str(v))

    lines = []
    total = 0
    for it in items:
        it_name = esc(it.get("name", "-"))
        it_qty = int(it.get("qty", 1) or 1)
        it_price = int(it.get("price", 0) or 0)
        line_total = it_qty * it_price
        total += line_total
        lines.append(f"• {it_name} x{it_qty} — {fmt_price(line_total)}")

    items_text = "\n".join(lines)
    service_label = "Yetkazib berish" if service == "delivery" else "Olib ketish"

    lat = data.get("lat")
    lng = data.get("lng")
    maps_line = ""
    if lat is not None and lng is not None:
        try:
            maps_url = f"https://maps.google.com/?q={float(lat)},{float(lng)}"
            maps_line = f"\nXarita: {maps_url}"
        except (TypeError, ValueError):
            maps_line = ""

    receipt_b64 = data.get("receipt_b64")
    receipt_url = None
    photo_bytes = None

    order_id = 1
    import datetime
    import base64
    import time

    if receipt_b64:
        try:
            if "," in receipt_b64:
                header, b64_str = receipt_b64.split(",", 1)
            else:
                b64_str = receipt_b64
            photo_bytes = base64.b64decode(b64_str)
            img_filename = f"receipt_{int(time.time()*1000)}.jpg"
            receipt_url = supabase_db.upload_receipt(photo_bytes, img_filename)
        except Exception:
            logger.exception("Chek rasmini yuklashda xatolik")

    payment_val = data.get("payment", "-")
    order_obj = {
        "status": "new",
        "timestamp": datetime.datetime.now().isoformat(),
        "customer": data.get("name", "Mijoz"),
        "phone": phone,
        "service": service,
        "location": location,
        "payment": payment_val,
        "card_number": PAYME_CARD if ("Click" in payment_val or "Payme" in payment_val or "Plastik" in payment_val) else None,
        "card_owner": PAYME_OWNER if ("Click" in payment_val or "Payme" in payment_val or "Plastik" in payment_val) else None,
        "payment_confirmed": bool(receipt_url),
        "receipt_url": receipt_url,
        "items": items,
        "total": total,
        "lat": lat,
        "lng": lng,
        "tg_user_id": data.get("tg_user_id")
    }
    order_id = supabase_db.create_order(order_obj)

    admin_msg = (
        f"🍽 <b>ISTANBUL CAFE - YANGI BUYURTMA (№{order_id})</b>\n"
        f"{'<i>To\'lov cheki (screenshot) biriktirilgan</i>\n' if receipt_url else ''}\n"
        f"<b>Mahsulotlar:</b>\n{items_text}\n\n"
        f"<b>Jami:</b> {fmt_price(total)}\n\n"
        f"<b>Mijoz:</b> {esc(data.get('name', 'Mijoz'))}\n"
        f"<b>Tel:</b> {esc(phone)}\n"
        f"<b>Xizmat turi:</b> {service_label}\n"
        f"<b>Manzil:</b> {esc(location)}"
        f"{maps_line}\n"
        f"<b>To'lov:</b> {esc(data.get('payment', '-'))}\n"
        f"<b>Karta:</b> {PAYME_CARD} ({esc(PAYME_OWNER)})"
    )

    tg_user_id = data.get("tg_user_id")
    cust_msg = None
    if tg_user_id:
        if service == "pickup":
            service_note = "Taomingiz tayyor bo'lgach, filialimizdan olib ketishingiz mumkin."
        else:
            service_note = "Operator tez orada buyurtmangizni tasdiqlaydi va taomingiz yetkazib beriladi."

        cust_msg = (
            f"<b>Hurmatli {esc(data.get('name', 'Mijoz'))}, buyurtmangiz qabul qilindi!</b>\n\n"
            f"<b>Buyurtma raqami:</b> #{order_id}\n"
            f"<b>Buyurtmangiz:</b>\n{items_text}\n\n"
            f"<b>Jami:</b> {fmt_price(total)}\n"
            f"<b>Xizmat:</b> {service_label}\n"
            f"<b>Manzil:</b> {esc(location)}\n"
            f"<b>To'lov turi:</b> {esc(data.get('payment', '-'))}\n\n"
            f"{service_note} Rahmat!"
        )

    dispatch_order_notifications(admin_msg, cust_msg, tg_user_id, photo_bytes)

    return jsonify({"success": True, "message": "Buyurtmangiz qabul qilindi!", "order_id": order_id})


# ==========================
# ADMIN BOSHQARUV PANELI (FLASK ROUTES)
# ==========================
ADMIN_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "templates", "admin.html")

def get_admin_html_template() -> str:
    if os.path.exists(ADMIN_TEMPLATE_FILE):
        with open(ADMIN_TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin Panel shabloni topilmadi.</h1>"


@flask_app.route("/admin")
def admin_page():
    return get_admin_html_template()


@flask_app.route("/api/admin/orders")
def api_admin_orders():
    try:
        orders = supabase_db.get_orders()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        logger.exception("Orders o'qishda xatolik")
        return jsonify({"success": False, "error": str(e)}), 500


@flask_app.route("/api/admin/order/<int:order_id>/status", methods=["POST"])
def api_admin_order_status(order_id: int):
    import threading

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "error": "Status ko'rsatilmadi"}), 400

    target_order = supabase_db.update_order_status(order_id, new_status)
    if not target_order:
        return jsonify({"success": False, "error": "Buyurtma topilmadi"}), 404

    # Mijozga status o'zgarishi haqida xabar
    cust_tg_id = target_order.get("tg_user_id")
    if cust_tg_id:
        srv = str(target_order.get("service", "")).lower()
        loc = str(target_order.get("location", "")).lower()
        is_pickup = (srv == "pickup" or "olib" in srv or "olib ketish" in loc or "filial" in loc)

        if is_pickup:
            status_texts = {
                "cooking": "Buyurtmangiz qabul qilindi va oshxonada tayyorlanmoqda.",
                "delivering": "Buyurtmangiz olib ketishga tayyor! Filialimizdan olib ketishingiz mumkin.",
                "completed": "Buyurtmangiz topshirildi. Xaridingiz uchun rahmat!",
                "cancelled": "Buyurtmangiz bekor qilindi. Savollaringiz bo'lsa biz bilan bog'laning.",
            }
        else:
            status_texts = {
                "cooking": "Buyurtmangiz qabul qilindi va oshxonada tayyorlanmoqda.",
                "delivering": "Taomingiz tayyorlandi va kuryer manzil tomon yo'lga chiqdi.",
                "completed": "Buyurtmangiz yetkazib berildi. Xaridingiz uchun rahmat!",
                "cancelled": "Buyurtmangiz bekor qilindi. Savollaringiz bo'lsa biz bilan bog'laning.",
            }
        st_msg = status_texts.get(new_status)
        if st_msg:
            full_st_msg = f"<b>Buyurtma holati yangilandi (№{order_id}):</b>\n\n{st_msg}"
            threading.Thread(
                target=send_telegram_message_sync,
                args=(cust_tg_id, full_st_msg),
                daemon=True
            ).start()

    return jsonify({"success": True, "message": "Holat yangilandi", "status": new_status})


@flask_app.route("/api/admin/order/<int:order_id>/delete", methods=["POST", "DELETE"])
def api_admin_order_delete(order_id: int):
    ok = supabase_db.delete_order(order_id)
    if ok:
        return jsonify({"success": True, "message": f"№{order_id} buyurtma muvaffaqiyatli o'chirildi!"})
    return jsonify({"success": False, "error": "Buyurtma topilmadi"}), 404


@flask_app.route("/api/admin/supabase-status", methods=["GET"])
def api_admin_supabase_status():
    status = supabase_db.check_supabase_connection()
    return jsonify({"success": True, "supabase": status})


@flask_app.route("/api/admin/menu", methods=["GET"])
def api_admin_menu():
    items = []
    for item_id, (name, price_text, price_num, cat) in MENU_ITEMS.items():
        items.append({
            "id": item_id,
            "name": name,
            "price": price_num,
            "price_text": price_text,
            "category": cat,
            "category_name": CATEGORY_NAMES.get(cat, cat),
            "category_sticker": get_category_sticker(cat)
        })
    return jsonify({
        "success": True,
        "items": items,
        "categories": CATEGORY_NAMES
    })


@flask_app.route("/api/admin/menu/item", methods=["POST"])
def api_admin_save_menu_item():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    price = data.get("price")
    category = (data.get("category") or "").strip()
    item_id = (data.get("id") or "").strip()
    custom_sticker = (data.get("sticker") or "").strip()

    if not name or price is None or not category:
        return jsonify({"success": False, "error": "Nomi, narxi va toifasi to'ldirilishi shart!"}), 400

    try:
        price_num = int(price)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Narx to'g'ri son bo'lishi kerak"}), 400

    # Taomga kategoriya yoki berilgan stikerni avtomatik biriktiramiz
    name = ensure_dish_sticker(name, category, custom_sticker=custom_sticker)

    if not item_id:
        import time
        item_id = f"it_{int(time.time()*1000)}"

    MENU_ITEMS[item_id] = (name, fmt_price(price_num), price_num, category)
    supabase_db.save_menu_item(item_id, name, price_num, category)
    save_menu()
    return jsonify({
        "success": True,
        "message": "Taom muvaffaqiyatli saqlandi!",
        "item_id": item_id,
        "name": name
    })


@flask_app.route("/api/admin/menu/item/<string:item_id>/delete", methods=["POST", "DELETE"])
@flask_app.route("/api/admin/menu/item/<string:item_id>", methods=["DELETE"])
def api_admin_delete_menu_item(item_id: str):
    if item_id in MENU_ITEMS:
        del MENU_ITEMS[item_id]
        supabase_db.delete_menu_item(item_id)
        save_menu()
        return jsonify({"success": True, "message": "Taom muvaffaqiyatli o'chirildi!"})
    return jsonify({"success": False, "error": "Taom topilmadi"}), 404


@flask_app.route("/api/admin/menu/category", methods=["POST"])
def api_admin_save_category():
    global CATEGORY_NAMES
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    sticker = (data.get("sticker") or "").strip()
    cat_id = (data.get("id") or "").strip().lower()

    if not name:
        return jsonify({"success": False, "error": "Kategoriya nomi kiritilishi shart!"}), 400

    # Agar nom boshida emoji bo'lmasa va stiker tanlangan bo'lsa, ularni birlashtiramiz
    if sticker and not any(ord(c) > 127 for c in name[:2]):
        full_name = f"{sticker} {name}".strip()
    else:
        full_name = name

    # ID bo'lmasa, slug yoki vaqt belgisi orqali kalit yaratamiz
    if not cat_id:
        import time, re
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')
        if slug and len(slug) >= 2 and slug not in CATEGORY_NAMES:
            cat_id = slug
        else:
            cat_id = f"cat_{int(time.time())}"

    CATEGORY_NAMES[cat_id] = full_name
    supabase_db.save_category(cat_id, full_name, sticker)
    save_menu()
    return jsonify({
        "success": True,
        "message": "Kategoriya muvaffaqiyatli saqlandi!",
        "category": {
            "id": cat_id,
            "name": full_name,
            "sticker": get_category_sticker(cat_id)
        },
        "categories": CATEGORY_NAMES
    })


@flask_app.route("/api/admin/menu/category/<string:cat_id>/delete", methods=["POST", "DELETE"])
@flask_app.route("/api/admin/menu/category/<string:cat_id>", methods=["DELETE"])
def api_admin_delete_category(cat_id: str):
    global CATEGORY_NAMES, MENU_ITEMS
    if cat_id in CATEGORY_NAMES:
        if len(CATEGORY_NAMES) <= 1:
            return jsonify({"success": False, "error": "Eng kamida bitta kategoriya qolishi shart!"}), 400

        del CATEGORY_NAMES[cat_id]
        supabase_db.delete_category(cat_id)
        # Ushbu toifadagi taomlarni boshqa qolgan toifaga o'tkazish
        remaining_cat = next(iter(CATEGORY_NAMES.keys()))
        for item_id, item_val in list(MENU_ITEMS.items()):
            dish_name, price_str, price_num, c = item_val
            if c == cat_id:
                MENU_ITEMS[item_id] = (dish_name, price_str, price_num, remaining_cat)
                supabase_db.save_menu_item(item_id, dish_name, price_num, remaining_cat)
        save_menu()
        return jsonify({
            "success": True,
            "message": "Kategoriya muvaffaqiyatli o'chirildi!",
            "categories": CATEGORY_NAMES
        })
    return jsonify({"success": False, "error": "Kategoriya topilmadi"}), 404


@flask_app.route("/api/admin/settings", methods=["GET"])
def api_admin_get_settings():
    return jsonify({
        "success": True,
        "settings": CAFE_SETTINGS
    })


@flask_app.route("/api/admin/settings", methods=["POST"])
def api_admin_save_settings():
    global PAYME_CARD, PAYME_OWNER
    data = request.get_json(silent=True) or {}
    card_number = (data.get("card_number") or "").strip()
    card_owner = (data.get("card_owner") or "").strip()
    is_open = data.get("is_open", True)
    cafe_name = (data.get("cafe_name") or "").strip()

    if card_number:
        CAFE_SETTINGS["card_number"] = card_number
        PAYME_CARD = card_number
    if card_owner:
        CAFE_SETTINGS["card_owner"] = card_owner
        PAYME_OWNER = card_owner
    if cafe_name:
        CAFE_SETTINGS["cafe_name"] = cafe_name
    CAFE_SETTINGS["is_open"] = bool(is_open)

    save_settings()
    return jsonify({
        "success": True,
        "message": "Sozlamalar muvaffaqiyatli saqlandi!",
        "settings": CAFE_SETTINGS
    })


# ==========================
# TELEGRAM BOT LOGIKASI
# ==========================
def get_start_keyboard(user_id: Optional[int] = None):
    web_url = WEB_APP_URL if (WEB_APP_URL and WEB_APP_URL.startswith("https://")) else DEFAULT_RENDER_URL
    buttons = [
        [KeyboardButton("🍽 Menular")]
    ]
    if web_url:
        buttons.append([KeyboardButton("🌐 Sayt orqali buyurtma", web_app=WebAppInfo(url=web_url))])
    else:
        buttons.append([KeyboardButton("🌐 Sayt orqali buyurtma")])

    if user_id and int(user_id) == ADMIN_ID:
        if web_url:
            buttons.append([KeyboardButton("📊 Admin Panel", web_app=WebAppInfo(url=f"{web_url}/admin"))])
        else:
            buttons.append([KeyboardButton("📊 Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def safe_reply_text(message, text: str, **kwargs):
    for attempt in range(1, 5):
        try:
            return await message.reply_text(text, **kwargs)
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(1.0)
            else:
                logger.error(f"Xabarni yuborib bo'lmadi: {e}")


async def safe_edit_text(message, text: str, **kwargs):
    for attempt in range(1, 5):
        try:
            return await message.edit_text(text, **kwargs)
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(1.0)
            else:
                logger.error(f"Xabarni tahrirlab bo'lmadi: {e}")


async def safe_send_message(bot, chat_id, text: str, **kwargs):
    for attempt in range(1, 5):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(1.0)
            else:
                logger.error(f"Xabar yuborib bo'lmadi: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    is_admin = (uid == ADMIN_ID)

    welcome_text = (
        "☕ <b>Istanbul Cafe botiga xush kelibsiz!</b>\n\n"
        "🍽 <b>Menular</b> — Telegram ichida qisqa menyu orqali buyurtma berish.\n"
        "🌐 <b>Sayt orqali buyurtma</b> — Fotosuratli to'liq menyu orqali qulay buyurtma berish! 🍔 🍕 🥙 🌭"
    )
    if is_admin:
        welcome_text += "\n\n👑 <b>Siz tizim administratorisiz!</b>\nAdmin Panel orqali barcha tushgan buyurtmalarni boshqarishingiz mumkin."

    await safe_reply_text(
        update.message,
        welcome_text,
        reply_markup=get_start_keyboard(user_id=uid),
        parse_mode="HTML"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await safe_reply_text(update.message, "Bu bo'lim faqat bot administratori uchun!")
        return

    web_url = WEB_APP_URL if (WEB_APP_URL and WEB_APP_URL.startswith("https://")) else DEFAULT_RENDER_URL
    admin_url = f"{web_url}/admin"
    
    buttons = [
        [InlineKeyboardButton("📊 Admin Panelni ochish (Web App)", web_app=WebAppInfo(url=admin_url))],
        [InlineKeyboardButton("🌐 Brauzerda ochish", url=admin_url)]
    ]
    inline_markup = InlineKeyboardMarkup(buttons)

    await safe_reply_text(
        update.message,
        f"☕ <b>Istanbul Cafe — Admin Boshqaruv Paneli:</b>\n\n"
        f"Havola: <a href=\"{admin_url}\">{admin_url}</a>",
        reply_markup=inline_markup,
        parse_mode="HTML"
    )


def build_categories_keyboard():
    buttons = []
    for cat_key, cat_name in CATEGORY_NAMES.items():
        buttons.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_key}")])
    return InlineKeyboardMarkup(buttons)


async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["cart"] = {}
    await safe_reply_text(
        update.message,
        "🍽 <b>Kategoriyani tanlang:</b>\nTaomlarni tanlab bo'lgach <b>«✅ Buyurtma berish»</b> tugmasini bosing.",
        reply_markup=build_categories_keyboard(),
        parse_mode="HTML",
    )


def cart_summary_line(cart: dict) -> str:
    if not cart:
        return "🛒 <i>Savat: bo'sh</i>"
    count = sum(c["qty"] for c in cart.values())
    total = sum(c["qty"] * c["price_num"] for c in cart.values())
    return f"🛒 <b>Savatda:</b> {count} ta mahsulot — <b>{fmt_price(total)}</b>"


def build_category_items_keyboard(cat_key: str, cart: dict):
    buttons = []
    for item_id, (name, price_text, price_num, cat) in MENU_ITEMS.items():
        if cat == cat_key:
            qty = cart.get(item_id, {}).get("qty", 0)
            label = f"{name} — {price_text}"
            if qty > 0:
                buttons.append([
                    InlineKeyboardButton(f"➕ {name} (x{qty})", callback_data=f"add_{item_id}"),
                    InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_{item_id}")
                ])
            else:
                buttons.append([InlineKeyboardButton(label, callback_data=f"add_{item_id}")])

    nav_row = [InlineKeyboardButton("◀️ Kategoriyalar", callback_data="back_categories")]
    if cart:
        nav_row.append(InlineKeyboardButton("🗑 Tozalash", callback_data="clear_cart"))
    buttons.append(nav_row)

    if cart:
        buttons.append([InlineKeyboardButton("✅ Buyurtma berish", callback_data="finish_select")])

    return InlineKeyboardMarkup(buttons)


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_key = query.data.replace("cat_", "")
    cart = context.user_data.setdefault("cart", {})

    title = CATEGORY_NAMES.get(cat_key, "Menyu")
    text = f"<b>{title}</b>\n\n{cart_summary_line(cart)}\n\nTaomni tanlang:"
    await safe_edit_text(query.message, text, reply_markup=build_category_items_keyboard(cat_key, cart), parse_mode="HTML")
    context.user_data["current_cat"] = cat_key


async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = context.user_data.setdefault("cart", {})
    text = f"<b>Kategoriyani tanlang:</b>\n\n{cart_summary_line(cart)}"
    await safe_edit_text(query.message, text, reply_markup=build_categories_keyboard(), parse_mode="HTML")


async def add_item_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.replace("add_", "")
    item = MENU_ITEMS.get(item_id)
    if not item:
        await query.answer("Topilmadi", show_alert=True)
        return

    name, price_text, price_num, cat = item
    cart = context.user_data.setdefault("cart", {})
    if item_id not in cart:
        cart[item_id] = {"name": name, "price_text": price_text, "price_num": price_num, "qty": 0}
    cart[item_id]["qty"] += 1

    await query.answer(f"Qo'shildi: {name}")

    title = CATEGORY_NAMES.get(cat, "Menyu")
    text = f"<b>{title}</b>\n\n{cart_summary_line(cart)}\n\nTaomni tanlang:"
    await safe_edit_text(query.message, text, reply_markup=build_category_items_keyboard(cat, cart), parse_mode="HTML")


async def remove_item_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.replace("del_", "")
    cart = context.user_data.get("cart", {})
    if item_id in cart:
        name = cart[item_id]["name"]
        if cart[item_id]["qty"] > 1:
            cart[item_id]["qty"] -= 1
            await query.answer(f"1 ta kamaytirildi: {name}")
        else:
            del cart[item_id]
            await query.answer(f"O'chirildi: {name}")
    else:
        await query.answer()

    cat = context.user_data.get("current_cat", "pizza")
    title = CATEGORY_NAMES.get(cat, "Menyu")
    text = f"<b>{title}</b>\n\n{cart_summary_line(cart)}\n\nTaomni tanlang:"
    await safe_edit_text(query.message, text, reply_markup=build_category_items_keyboard(cat, cart), parse_mode="HTML")


async def clear_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["cart"] = {}
    await query.answer("Savat tozalandi")
    cat = context.user_data.get("current_cat", "pizza")
    title = CATEGORY_NAMES.get(cat, "Menyu")
    text = f"<b>{title}</b>\n\n{cart_summary_line({})}"
    await safe_edit_text(query.message, text, reply_markup=build_category_items_keyboard(cat, {}), parse_mode="HTML")


# ==========================================
# BUYURTMA BOSQICHLARI (LOKATSIYADAN AVVAL XIZMAT TURI)
# ==========================================
async def finish_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi taomlarni tanlab bo'lgach birinchi bo'lib Xizmat turini so'raydi."""
    query = update.callback_query
    cart = context.user_data.get("cart", {})
    if not cart:
        await query.answer("Savatingiz bo'sh, avval taom tanlang.", show_alert=True)
        return

    await query.answer()
    context.user_data["awaiting"] = "service_choice"

    summary = "\n".join(
        f"• {html.escape(c['name'])} x{c['qty']} — {fmt_price(c['qty'] * c['price_num'])}"
        for c in cart.values()
    )
    total = sum(c["qty"] * c["price_num"] for c in cart.values())

    buttons = [
        [InlineKeyboardButton("🛵 Yetkazib berish", callback_data="service_delivery")],
        [InlineKeyboardButton("🛍 Olib ketish", callback_data="service_pickup")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="clear_cart")]
    ]

    await safe_edit_text(
        query.message,
        f"<b>Sizning tanlovingiz:</b>\n{summary}\n\n<b>Jami:</b> {fmt_price(total)}\n\n"
        f"Buyurtmani qanday qabul qilasiz? Xizmat turini tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xizmat turi tanlanganda ishlaydi."""
    query = update.callback_query
    await query.answer()

    choice = query.data  # "service_delivery" yoki "service_pickup"
    
    # 1. AGAR OLIB KETISH TANLANSA — GPS UMUMAN SO'RALMAYDI, TO'G'RIDAN TELEFON VA TO'LOV
    if choice == "service_pickup":
        context.user_data["order_service"] = "pickup"
        context.user_data["order_location"] = "Filialdan olib ketish"
        context.user_data["order_lat"] = None
        context.user_data["order_lon"] = None
        context.user_data["awaiting"] = "phone"

        contact_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Telefon raqamimni yuborish", request_contact=True)],
                [KeyboardButton("❌ Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await safe_edit_text(
            query.message,
            "Xizmat turi: <b>🛍 Olib ketish</b> tanlandi.\n(GPS lokatsiya talab qilinmaydi)",
            parse_mode="HTML"
        )
        await safe_reply_text(
            query.message,
            "📱 Telefon raqamingizni yuboring (tugmani bosing yoki yozing):",
            reply_markup=contact_keyboard,
        )

    # 2. AGAR YETKAZIB BERISH TANLANSA — DARHOL GPS LOKATSIYA SO'RALADI
    elif choice == "service_delivery":
        context.user_data["order_service"] = "delivery"
        context.user_data["awaiting"] = "location"

        await safe_edit_text(
            query.message,
            "Xizmat turi: <b>🛵 Yetkazib berish</b> tanlandi.",
            parse_mode="HTML"
        )
        await safe_reply_text(
            query.message,
            "Yetkazib berish manzilini tanlang:\n\n"
            "1. 📍 <b>Turgan joyim (GPS)</b> — Hozirgi joylashuvingizni yuborish uchun pastdagi tugmani bosing\n"
            "2. ✍️ <b>Boshqa manzilni kiritish</b> — Manzilni qo'lda yozib jo'natish",
            reply_markup=build_location_keyboard(),
            parse_mode="HTML"
        )


def build_location_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📍 Turgan joyim (GPS)", request_location=True)],
            [KeyboardButton("✍️ Boshqa manzilni kiritish")],
            [KeyboardButton("❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqami kelganda ishlaydi."""
    if context.user_data.get("awaiting") != "phone":
        return
    phone = update.message.contact.phone_number
    context.user_data["order_phone"] = phone
    context.user_data["awaiting"] = "payment"

    buttons = [[InlineKeyboardButton(label, callback_data=key)] for key, label in PAYMENT_OPTIONS.items()]
    await safe_reply_text(
        update.message,
        f"✅ Telefon raqami qabul qilindi: {phone}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await safe_reply_text(
        update.message,
        "💳 <b>To'lov turini tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


async def location_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GPS lokatsiya yuborilganda ishlaydi."""
    if context.user_data.get("awaiting") != "location":
        return

    loc = update.message.location
    lat, lon = loc.latitude, loc.longitude

    address = reverse_geocode(lat, lon)
    if not address:
        address = f"Koordinata: {lat:.5f}, {lon:.5f}"

    context.user_data["order_location"] = address
    context.user_data["order_lat"] = lat
    context.user_data["order_lon"] = lon

    # Agar telefon oldin berilmagan bo'lsa telefon so'rash
    if not context.user_data.get("order_phone"):
        context.user_data["awaiting"] = "phone"
        contact_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Telefon raqamimni yuborish", request_contact=True)],
                [KeyboardButton("❌ Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await safe_reply_text(
            update.message,
            f"📍 Manzil qabul qilindi: <b>{html.escape(address)}</b>\n\nEndi 📱 telefon raqamingizni yuboring:",
            reply_markup=contact_keyboard,
            parse_mode="HTML"
        )
    else:
        context.user_data["awaiting"] = "payment"
        buttons = [[InlineKeyboardButton(label, callback_data=key)] for key, label in PAYMENT_OPTIONS.items()]
        await safe_reply_text(
            update.message,
            f"📍 Manzil qabul qilindi: <b>{html.escape(address)}</b>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await safe_reply_text(
            update.message,
            "💳 <b>To'lov turini tanlang:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )


async def text_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Matnli xabarlarni yo'naltiradi."""
    text = (update.message.text or "").strip()

    if text in ["Menyu", "🍽 Menyu", "🍽 Menular"]:
        await open_menu(update, context)
        return

    if text.startswith("Admin") or text.startswith("📊 Admin"):
        await admin_command(update, context)
        return

    if text in ["Bekor qilish", "❌ Bekor qilish"]:
        context.user_data.clear()
        await safe_reply_text(
            update.message,
            "❌ Buyurtma bekor qilindi.",
            reply_markup=get_start_keyboard(update.effective_user.id if update.effective_user else None)
        )
        return

    if text.startswith("Sayt") or text.startswith("🌐 Sayt"):
        url_text = WEB_APP_URL if (WEB_APP_URL and WEB_APP_URL.startswith("https://")) else DEFAULT_RENDER_URL
        inline_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Saytni ochish (Web App)", web_app=WebAppInfo(url=url_text))],
            [InlineKeyboardButton("🌐 Brauzerda ochish", url=url_text)]
        ])
        msg_text = f"🌐 <b>Istanbul Cafe veb-sayti:</b>\n\nHavola: <a href=\"{url_text}\">{url_text}</a>\n\nQuyidagi tugma orqali fotosuratli qulay menyuni ochishingiz mumkin:"
        await safe_reply_text(
            update.message,
            msg_text,
            reply_markup=inline_markup,
            parse_mode="HTML"
        )
        return

    awaiting = context.user_data.get("awaiting")

    if awaiting == "phone":
        context.user_data["order_phone"] = text
        context.user_data["awaiting"] = "payment"
        buttons = [[InlineKeyboardButton(label, callback_data=key)] for key, label in PAYMENT_OPTIONS.items()]
        await safe_reply_text(
            update.message,
            f"✅ Telefon raqami qabul qilindi: {html.escape(text)}",
            reply_markup=ReplyKeyboardRemove(),
        )
        await safe_reply_text(
            update.message,
            "💳 <b>To'lov turini tanlang:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    if awaiting == "location":
        if "boshqa manzil" in text.lower():
            context.user_data["awaiting"] = "location_manual"
            await safe_reply_text(
                update.message,
                "Yetkazib berish manzilini to'liq yozib yuboring:\n(Masalan: Amir Temur ko'chasi 10-uy)",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        context.user_data["order_location"] = text
        context.user_data["awaiting"] = "phone"
        contact_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("Telefon raqamimni yuborish", request_contact=True)],
                [KeyboardButton("Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await safe_reply_text(
            update.message,
            f"Manzil qabul qilindi: {html.escape(text)}\n\nEndi telefon raqamingizni yuboring:",
            reply_markup=contact_keyboard,
        )
        return

    if awaiting == "location_manual":
        context.user_data["order_location"] = text
        context.user_data["awaiting"] = "phone"
        contact_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("Telefon raqamimni yuborish", request_contact=True)],
                [KeyboardButton("Bekor qilish")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await safe_reply_text(
            update.message,
            f"Manzil qabul qilindi: {html.escape(text)}\n\nEndi telefon raqamingizni yuboring:",
            reply_markup=contact_keyboard,
        )
        return

    if awaiting == "payme_screenshot":
        await safe_reply_text(
            update.message,
            f"<b>To'lov chekini (screenshot rasmini) yuboring!</b>\n\n"
            f"Karta raqami: <code>{PAYME_CARD}</code>\n"
            f"Karta egasi: {html.escape(PAYME_OWNER)}\n\n"
            f"Pul o'tkazgandan so'ng, chek rasmini ushbu chatga jo'nating.",
            parse_mode="HTML",
        )
        return


async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if context.user_data.get("awaiting") != "payment":
        return

    payment_key = query.data
    payment_label = PAYMENT_OPTIONS.get(payment_key, "-")
    context.user_data["order_payment_label"] = payment_label
    context.user_data["order_payment_key"] = payment_key

    if payment_key == "pay_click":
        context.user_data["awaiting"] = "payme_screenshot"
        cart = context.user_data.get("cart", {})
        total = sum(c["qty"] * c["price_num"] for c in cart.values())

        await safe_edit_text(
            query.message,
            f"<b>Click / Plastik karta orqali to'lov</b>\n\n"
            f"To'lov miqdori: <b>{fmt_price(total)}</b>\n\n"
            f"Quyidagi kartaga o'tkazing:\n"
            f"<code>{PAYME_CARD}</code>\n"
            f"Karta egasi: <b>{html.escape(PAYME_OWNER)}</b>\n\n"
            f"Pul o'tkazgandan so'ng <b>to'lov cheki (screenshot rasmi)ni</b> ushbu chatga yuboring.",
            parse_mode="HTML",
        )
        return

    await _finalize_telegram_order(update, context)


async def payme_screenshot_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz Click/Payme screenshot yuborganda ishlaydi."""
    if context.user_data.get("awaiting") != "payme_screenshot":
        return

    photo = update.message.photo
    document = update.message.document

    if not photo and not document:
        await safe_reply_text(
            update.message,
            "Iltimos, to'lov screenshotini rasm sifatida yuboring!",
            parse_mode="HTML",
        )
        return

    user = update.effective_user
    client_name = user.full_name if user else "Mijoz"
    cart = context.user_data.get("cart", {})
    phone = context.user_data.get("order_phone", "-")
    service = context.user_data.get("order_service", "delivery")
    location = context.user_data.get("order_location", "Filialdan olib ketish" if service == "pickup" else "-")
    lat = context.user_data.get("order_lat")
    lon = context.user_data.get("order_lon")
    payment_label = context.user_data.get("order_payment_label", "Click / Plastik karta")
    service_label = "Yetkazib berish" if service == "delivery" else "Olib ketish"

    def esc(v):
        return html.escape(str(v))

    lines = [
        f"• {esc(c['name'])} x{c['qty']} — {fmt_price(c['qty'] * c['price_num'])}"
        for c in cart.values()
    ]
    total = sum(c["qty"] * c["price_num"] for c in cart.values())
    items_text = "\n".join(lines) if lines else "-"
    maps_line = f"\nXarita: https://maps.google.com/?q={lat},{lon}" if lat is not None and lon is not None else ""

    admin_caption = (
        f"<b>CLICK / PLASTIK TO'LOV CHEKI KELDI</b>\n\n"
        f"🍽 <b>ISTANBUL CAFE — YANGI BUYURTMA (Telegram orqali)</b>\n\n"
        f"<b>Mahsulotlar:</b>\n{items_text}\n\n"
        f"<b>Jami:</b> {fmt_price(total)}\n"
        f"<b>Mijoz:</b> {esc(client_name)}\n"
        f"<b>Tel:</b> {esc(phone)}\n"
        f"<b>Xizmat turi:</b> {service_label}\n"
        f"<b>Manzil:</b> {esc(location)}{maps_line}\n"
        f"<b>To'lov:</b> {esc(payment_label)}\n"
        f"<b>Karta:</b> <code>{PAYME_CARD}</code> ({html.escape(PAYME_OWNER)})"
    )

    order_id = 1
    receipt_url = None
    import datetime, time

    try:
        tg_file_obj = None
        if photo:
            tg_file_obj = await photo[-1].get_file()
        elif document:
            tg_file_obj = await document.get_file()
        
        if tg_file_obj:
            img_filename = f"receipt_{int(time.time()*1000)}.jpg"
            p_bytes = await tg_file_obj.download_as_bytearray()
            receipt_url = supabase_db.upload_receipt(bytes(p_bytes), img_filename)
    except Exception:
        logger.exception("Telegram rasmini serverga saqlashda xatolik")

    order_items = [
        {"name": c["name"], "qty": c["qty"], "price": c["price_num"]}
        for c in cart.values()
    ]
    new_order = {
        "status": "new",
        "timestamp": datetime.datetime.now().isoformat(),
        "customer": client_name,
        "phone": phone,
        "service": service,
        "location": location,
        "payment": payment_label,
        "card_number": PAYME_CARD,
        "card_owner": PAYME_OWNER,
        "payment_confirmed": True,
        "receipt_url": receipt_url,
        "items": order_items,
        "total": total,
        "lat": lat,
        "lng": lon,
        "tg_user_id": user.id if user else None,
    }
    order_id = supabase_db.create_order(new_order)

    try:
        if photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo[-1].file_id,
                caption=admin_caption,
                parse_mode="HTML",
            )
        elif document:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=document.file_id,
                caption=admin_caption,
                parse_mode="HTML",
            )
    except Exception:
        await safe_send_message(context.bot, ADMIN_ID, admin_caption, parse_mode="HTML")

    await safe_reply_text(
        update.message,
        f"<b>To'lovingiz qabul qilindi va buyurtmangiz rasmiylashtirildi!</b>\n\n"
        f"Buyurtma raqami: <b>#{order_id}</b>\n"
        f"<b>Buyurtmangiz:</b>\n{items_text}\n\n"
        f"<b>Jami:</b> {fmt_price(total)}\n"
        f"<b>Xizmat:</b> {service_label}\n"
        f"<b>To'lov:</b> {esc(payment_label)}\n\n"
        f"Admin tasdiqlashi kutilmoqda. Rahmat!",
        parse_mode="HTML",
        reply_markup=get_start_keyboard(user.id if user else None),
    )

    context.user_data.clear()


async def _finalize_telegram_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naqd to'lov orqali buyurtmani rasmiylashtiradi."""
    query = update.callback_query
    message = query.message if query else update.message

    payment_label = context.user_data.get("order_payment_label", "Naqd pul")
    cart = context.user_data.get("cart", {})
    phone = context.user_data.get("order_phone", "-")
    service = context.user_data.get("order_service", "delivery")
    location = context.user_data.get("order_location", "Filialdan olib ketish" if service == "pickup" else "-")
    lat = context.user_data.get("order_lat")
    lon = context.user_data.get("order_lon")
    service_label = "Yetkazib berish" if service == "delivery" else "Olib ketish"

    user = update.effective_user
    client_name = user.full_name if user else "Mijoz"

    def esc(v):
        return html.escape(str(v))

    lines = [
        f"• {esc(c['name'])} x{c['qty']} — {fmt_price(c['qty'] * c['price_num'])}"
        for c in cart.values()
    ]
    total = sum(c["qty"] * c["price_num"] for c in cart.values())
    items_text = "\n".join(lines) if lines else "-"

    maps_line = f"\nXarita: https://maps.google.com/?q={lat},{lon}" if lat is not None and lon is not None else ""

    msg = (
        f"🍽 <b>ISTANBUL CAFE - YANGI BUYURTMA (Telegram orqali)</b>\n\n"
        f"<b>Mahsulotlar:</b>\n{items_text}\n\n"
        f"<b>Jami narx:</b> {fmt_price(total)}\n\n"
        f"<b>Mijoz:</b> {esc(client_name)}\n"
        f"<b>Tel:</b> {esc(phone)}\n"
        f"<b>Xizmat turi:</b> {service_label}\n"
        f"<b>Manzil:</b> {esc(location)}"
        f"{maps_line}\n"
        f"<b>To'lov:</b> {esc(payment_label)}"
    )

    order_id = 1
    import datetime
    order_items = [
        {"name": c["name"], "qty": c["qty"], "price": c["price_num"]}
        for c in cart.values()
    ]
    new_order = {
        "status": "new",
        "timestamp": datetime.datetime.now().isoformat(),
        "customer": client_name,
        "phone": phone,
        "service": service,
        "location": location,
        "payment": payment_label,
        "items": order_items,
        "total": total,
        "lat": lat,
        "lng": lon,
        "tg_user_id": user.id if user else None,
        "card_number": None,
        "card_owner": None,
    }
    order_id = supabase_db.create_order(new_order)

    try:
        await safe_send_message(context.bot, ADMIN_ID, msg, parse_mode="HTML")

        await safe_edit_text(
            message,
            f"<b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"Buyurtma raqami: <b>#{order_id}</b>\n"
            f"{items_text}\n\n"
            f"<b>Jami:</b> {fmt_price(total)}\n"
            f"<b>Xizmat:</b> {service_label}\n"
            f"<b>Manzil:</b> {esc(location)}\n"
            f"<b>To'lov:</b> {esc(payment_label)}\n\n"
            f"Operator tez orada buyurtmangizni tasdiqlaydi. Rahmat!",
            parse_mode="HTML",
        )
    except Exception:
        await safe_edit_text(message, "Xatolik yuz berdi, qaytadan urinib ko'ring.")

    context.user_data.clear()
    await safe_send_message(
        context.bot,
        update.effective_chat.id,
        "Yana buyurtma berish uchun Menyuni tanlang:",
        reply_markup=get_start_keyboard(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    from telegram.error import Conflict
    if isinstance(context.error, Conflict):
        logger.warning("Boshqa bot nusxasi ochilgan bo'lishi mumkin (Conflict). Avtomatik tiklanmoqda...")
        return
    if isinstance(context.error, (TimedOut, NetworkError)):
        logger.warning(f"Telegram tarmog'ida kechikish (Timeout): {context.error}")
        return
    logger.error("Bot ichida xatolik yuz berdi", exc_info=context.error)


# ==========================
# ASOSIY PROGRAMMANI ISHGA TUSHIRISH
# ==========================
def run_flask_server(port: int = 10000):
    global ACTUAL_FLASK_PORT
    from werkzeug.serving import make_server
    try:
        server = make_server('0.0.0.0', port, flask_app, threaded=True)
        ACTUAL_FLASK_PORT = port
        logger.info(f"Veb-server http://0.0.0.0:{port} portida ishga tushdi!")
        server.serve_forever()
    except OSError as err:
        logger.warning(f"Port {port} band bo'lishi mumkin ({err}). 5000-port sinab ko'rilmoqda...")
        try:
            server = make_server('0.0.0.0', 5000, flask_app, threaded=True)
            ACTUAL_FLASK_PORT = 5000
            logger.info(f"Veb-server http://0.0.0.0:5000 portida ishga tushdi!")
            server.serve_forever()
        except Exception as e2:
            logger.error(f"Veb-serverni ishga tushirishda xatolik: {e2}")


def start_tunnel_worker(port: int = 10000):
    global WEB_APP_URL, TUNNEL_PROCESS
    import sys
    env_url = (os.environ.get("WEB_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    if env_url.startswith("https://"):
        WEB_APP_URL = env_url
        logger.info(f"Maxsus / Render HTTPS havola o'rnatilgan: {WEB_APP_URL}")
        return

    # Render bulut muhitida (Linux) tashqi tunnel ochish shart emas
    if os.environ.get("RENDER"):
        if env_url:
            WEB_APP_URL = env_url
        logger.info(f"Render muhiti aniqlandi. WEB_APP_URL: {WEB_APP_URL}")
        return

    import subprocess
    import re
    import time

    for _ in range(30):
        if ACTUAL_FLASK_PORT is not None:
            break
        time.sleep(0.5)

    target_port = ACTUAL_FLASK_PORT if ACTUAL_FLASK_PORT is not None else port
    cf_path = os.path.join(os.path.dirname(__file__), "cloudflared.exe")

    while True:
        if sys.platform == "win32" and os.path.exists(cf_path):
            try:
                proc = subprocess.Popen(
                    [cf_path, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{target_port}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                TUNNEL_PROCESS = proc
                found = False
                for line in proc.stderr:
                    if not found:
                        m = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                        if m:
                            WEB_APP_URL = m.group(0)
                            found = True
                            logger.info(f"CLOUDFLARE HTTPS: {WEB_APP_URL}")
                proc.wait()
            except Exception as e_cf:
                logger.warning(f"Cloudflare tunnel: {e_cf}")

        try:
            proc = subprocess.Popen(
                ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=20", f"-R0:localhost:{target_port}", "-T", "a.pinggy.io"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            TUNNEL_PROCESS = proc
            found = False
            for line in proc.stdout:
                if not found:
                    if "dashboard.pinggy.io" in line:
                        continue
                    m = re.search(r'https://[a-zA-Z0-9\-]+\.(?:free\.pinggy\.net|run\.pinggy-free\.link|pinggy\.link)', line)
                    if m:
                        WEB_APP_URL = m.group(0)
                        found = True
                        logger.info(f"PINGGY HTTPS: {WEB_APP_URL}")
            proc.wait()
        except Exception as e:
            logger.warning(f"Pinggy tunnel: {e}")

        time.sleep(3)


def setup_telegram_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(back_to_categories, pattern="^back_categories$"))
    app.add_handler(CallbackQueryHandler(add_item_to_cart, pattern="^add_"))
    app.add_handler(CallbackQueryHandler(remove_item_from_cart, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(clear_cart_callback, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(finish_selection, pattern="^finish_select$"))
    app.add_handler(CallbackQueryHandler(service_selected, pattern="^service_"))
    app.add_handler(CallbackQueryHandler(payment_selected, pattern="^pay_"))
    app.add_handler(MessageHandler(filters.CONTACT, contact_received))
    app.add_handler(MessageHandler(filters.LOCATION, location_received))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, payme_screenshot_received))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_router))
    app.add_error_handler(error_handler)


# ==============================================================================
# TELEGRAM WEBHOOK (VERCEL SERVERLESS VA CLOUD UCHUN)
# ==============================================================================

@flask_app.route("/api/webhook", methods=["POST"])
def telegram_webhook():
    """Telegram Webhook orqali yangilanishlarni qabul qilish (Serverless / Vercel uchun)."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"status": "ignored", "reason": "empty"}), 200

        global tg_application
        if tg_application is None:
            request_config = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
            tg_application = ApplicationBuilder().token(TOKEN).request(request_config).build()
            setup_telegram_handlers(tg_application)

        update = Update.de_json(data, tg_application.bot)
        if update:
            async def _process():
                if not getattr(tg_application, "_initialized", False):
                    await tg_application.initialize()
                await tg_application.process_update(update)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_process())
                else:
                    loop.run_until_complete(_process())
            except RuntimeError:
                asyncio.run(_process())

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception(f"Webhook processing xatoligi: {e}")
        return jsonify({"status": "error", "error": str(e)}), 200


@flask_app.route("/api/set-webhook", methods=["GET", "POST"])
def set_telegram_webhook():
    """Telegram Webhookni avtomatik Vercel domeniga ulash."""
    custom_url = request.args.get("url")
    if custom_url:
        webhook_url = custom_url.rstrip("/")
        if not webhook_url.endswith("/api/webhook"):
            webhook_url += "/api/webhook"
    else:
        host = request.host_url.rstrip("/")
        if host.startswith("http://"):
            host = "https://" + host[7:]
        webhook_url = f"{host}/api/webhook"

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            json={"url": webhook_url, "drop_pending_updates": True},
            timeout=10
        )
        res_data = r.json()
        return jsonify({
            "success": r.status_code == 200 and res_data.get("ok", False),
            "webhook_url": webhook_url,
            "telegram_response": res_data
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@flask_app.route("/api/delete-webhook", methods=["GET", "POST"])
def delete_telegram_webhook():
    """Telegram Webhookni bekor qilish (Lokal polling rejimiga o'tish uchun)."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/deleteWebhook",
            json={"drop_pending_updates": True},
            timeout=10
        )
        return jsonify({"success": True, "telegram_response": r.json()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



def keep_alive_worker():
    """Render bepul servisi uxlab qolmasligi uchun har 8 daqiqada o'zini ping qiladi."""
    import time
    while True:
        time.sleep(480)
        try:
            target_url = (os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEB_URL") or DEFAULT_RENDER_URL).strip()
            if target_url and target_url.startswith("https://"):
                requests.get(f"{target_url}/healthz", timeout=10)
        except Exception:
            pass


async def main():
    global tg_application, MAIN_LOOP
    import threading

    MAIN_LOOP = asyncio.get_running_loop()
    port = int(os.environ.get("PORT", 10000))

    flask_thread = threading.Thread(target=run_flask_server, args=(port,), daemon=True)
    flask_thread.start()

    tunnel_thread = threading.Thread(target=start_tunnel_worker, args=(port,), daemon=True)
    tunnel_thread.start()

    keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
    keep_alive_thread.start()

    request_config = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0,
    )
    tg_application = ApplicationBuilder().token(TOKEN).request(request_config).build()
    setup_telegram_handlers(tg_application)

    while True:
        try:
            async with tg_application:
                await tg_application.initialize()
                await tg_application.start()
                await tg_application.updater.start_polling(drop_pending_updates=True)
                logger.info("Telegram bot muvaffaqiyatli ishga tushdi!")

                active_url = WEB_APP_URL if (WEB_APP_URL and WEB_APP_URL.startswith("https://")) else DEFAULT_RENDER_URL
                if active_url and active_url.startswith("https://"):
                    try:
                        await tg_application.bot.set_chat_menu_button(
                            menu_button=MenuButtonWebApp(text="🍽 Buyurtma", web_app=WebAppInfo(url=active_url))
                        )
                        logger.info(f"Telegram WebApp menyu tugmasi o'rnatildi: {active_url}")
                    except Exception as e_mb:
                        logger.warning(f"Telegram MenuButton o'rnatishda ogohlantirish: {e_mb}")

                stop_signal = asyncio.Event()
                await stop_signal.wait()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            err_str = str(e)
            if "Conflict" in err_str or "terminated by other getUpdates request" in err_str:
                logger.critical("CONFLICT XATOLIGI: Bot tokenidan boshqa joyda foydalanilmoqda!")
                break
            logger.error(f"Telegram bot polling ogohlantirishi: {e}")
            await asyncio.sleep(10)
            tg_application = ApplicationBuilder().token(TOKEN).request(request_config).build()
            setup_telegram_handlers(tg_application)


import atexit

def cleanup():
    global TUNNEL_PROCESS
    if TUNNEL_PROCESS:
        try:
            TUNNEL_PROCESS.kill()
        except Exception:
            pass

atexit.register(cleanup)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        cleanup()
        logger.info("Bot to'xtatildi.")