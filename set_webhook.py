"""
Istanbul Cafe - Telegram Webhook & Bot Sozlash Skripti
Ushbu skript Telegram botini Vercel ga ulash, bot profilini yangilash yoki Webhookni bekor qilish uchun xizmat qiladi.

Foydalanish:
1. Webhook ulash va bot profilini to'liq sozlash:
   python set_webhook.py https://loyihangiz.vercel.app

2. Webhookni bekor qilish (lokal polling rejimiga qaytish):
   python set_webhook.py --delete

3. Webhook va bot holatini tekshirish:
   python set_webhook.py --info
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN", "8780942618:AAEM8JdnmV2vPyoFrYGIm7dbd7Z964zsaxg").strip()

if not TOKEN:
    print("[XATO] .env faylida BOT_TOKEN topilmadi!")
    sys.exit(1)


def get_webhook_info():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
        r = requests.get(url, timeout=10)
        print("=== TELEGRAM WEBHOOK HOLATI ===")
        print(r.json())
        me_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        r_me = requests.get(me_url, timeout=10)
        print("=== BOT PROFILI ===")
        print(r_me.json())
    except Exception as e:
        print(f"[XATO] Telegram bilan bog'lanib bo'lmadi: {e}")


def delete_webhook():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        r = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        print("=== WEBHOOK BEKOR QILINDI ===")
        print(r.json())
        print("[OK] Endi botni o'zingizda 'python istanbul_cafe_bot.py' orqali ishga tushirishingiz mumkin.")
    except Exception as e:
        print(f"[XATO] Webhookni o'chirib bo'lmadi: {e}")


def set_webhook(domain: str):
    domain = domain.strip().rstrip("/")
    if not domain.startswith("https://"):
        domain = "https://" + domain.replace("http://", "")

    webhook_url = f"{domain}/api/webhook"
    print("=" * 60)
    print(f"WEBHOOK URL: {webhook_url}")
    print(f"WEB APP URL: {domain}")
    print("=" * 60)

    # 1. setWebhook
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
        r = requests.post(url, json={"url": webhook_url, "drop_pending_updates": True}, timeout=10)
        data = r.json()
        if data.get("ok"):
            print("[1/5] Telegram Webhook muvaffaqiyatli o'rnatildi!")
        else:
            print(f"[XATO] Webhook o'rnatilmadi: {data}")
    except Exception as e:
        print(f"[XATO] setWebhook so'rovida xatolik: {e}")

    # 2. setChatMenuButton
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/setChatMenuButton"
        payload = {
            "menu_button": {
                "type": "web_app",
                "text": "🍽 Buyurtma",
                "web_app": {"url": domain}
            }
        }
        r = requests.post(url, json=payload, timeout=10)
        print(f"[2/5] MenuButton (🍽 Buyurtma) o'rnatildi: {r.json().get('ok')}")
    except Exception as e:
        print(f"[XATO] setChatMenuButton so'rovida xatolik: {e}")

    # 3. setMyName
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyName", json={"name": "Istanbul Cafe"}, timeout=10)
        print(f"[3/5] Bot nomi 'Istanbul Cafe' ga o'rnatildi: {r.json().get('ok')}")
    except Exception as e:
        print(f"[XATO] setMyName xatosi: {e}")

    # 4. setMyDescription
    try:
        desc = (
            "☕ Istanbul Cafe rasmiy boti!\n\n"
            "🍔 Burgerlar\n"
            "🥙 Mazali lavashlar\n"
            "🍕 Issiq pitsalar\n"
            "🌭 Hot-doglar\n"
            "🥩 Doner va kebablar\n"
            "🥤 Muzdek ichimliklar\n\n"
            "Buyurtma berish uchun /start bosing yoki quyidagi '🍽 Buyurtma' tugmasidan foydalaning!"
        )
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyDescription", json={"description": desc}, timeout=10)
        print(f"[4/5] Bot tavsifi yangilandi: {r.json().get('ok')}")
    except Exception as e:
        print(f"[XATO] setMyDescription xatosi: {e}")

    # 5. setMyCommands
    try:
        commands = [
            {"command": "start", "description": "☕ Menyu va buyurtma berish"},
            {"command": "admin", "description": "📊 Admin Boshqaruv Paneli"}
        ]
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands", json={"commands": commands}, timeout=10)
        print(f"[5/5] Bot komandalari (/start, /admin) o'rnatildi: {r.json().get('ok')}")
    except Exception as e:
        print(f"[XATO] setMyCommands xatosi: {e}")

    print("\n[TAYYOR] Istanbul Cafe Telegram boti Vercel bilan to'liq ulandi!")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        get_webhook_info()
        sys.exit(0)

    arg = sys.argv[1]
    if arg == "--delete":
        delete_webhook()
    elif arg == "--info":
        get_webhook_info()
    else:
        set_webhook(arg)
