"""
Istanbul Cafe - Telegram Webhook Sozlash Skripti
Ushbu skript Telegram botini Vercel ga ulash yoki Webhookni bekor qilish uchun xizmat qiladi.

Foydalanish:
1. Webhook ulash:
   python set_webhook.py https://loyihangiz.vercel.app

2. Webhookni bekor qilish (lokal polling rejimiga qaytish):
   python set_webhook.py --delete

3. Webhook holatini tekshirish:
   python set_webhook.py --info
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not TOKEN:
    print("[XATO] .env faylida BOT_TOKEN topilmadi!")
    sys.exit(1)


def get_webhook_info():
    url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    r = requests.get(url)
    print("=== TELEGRAM WEBHOOK HOLATI ===")
    print(r.json())


def delete_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    r = requests.post(url, json={"drop_pending_updates": True})
    print("=== WEBHOOK BEKOR QILINDI ===")
    print(r.json())
    print("[OK] Endi botni o'zingizda 'python istanbul_cafe_bot.py' orqali ishga tushirishingiz mumkin.")


def set_webhook(domain: str):
    domain = domain.strip().rstrip("/")
    if not domain.startswith("https://"):
        domain = "https://" + domain.replace("http://", "")

    webhook_url = f"{domain}/api/webhook"
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    r = requests.post(url, json={"url": webhook_url, "drop_pending_updates": True})
    data = r.json()

    print("=" * 60)
    print(f"WEBHOOK URL: {webhook_url}")
    print("=" * 60)
    if data.get("ok"):
        print("[MUVAFFAQINATLI] Telegram bot Vercel serveriga muvaffaqiyatli ulandi!")
        print(f"Javob: {data.get('description')}")
        print("\nMini App WebApp tugmasini ham Vercel domeniga o'rnatish:")
        set_menu_btn(domain)
    else:
        print("[XATO] Webhook ulanmadi:")
        print(data)


def set_menu_btn(domain: str):
    url = f"https://api.telegram.org/bot{TOKEN}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "🍽 Buyurtma",
            "web_app": {
                "url": domain
            }
        }
    }
    r = requests.post(url, json=payload)
    print(f"MenuButton (🍽 Buyurtma) o'rnatish natijasi: {r.json()}")


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
