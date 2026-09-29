# Korolevskiy Center Bot & Web Management

Korolevskiy Center uchun Telegram Bot, Veb Menyu (WebApp) va Admin Boshqaruv Paneli.

## Xususiyatlari
- 🤖 **Telegram Bot**: Taomlarni ko'rish, savatga qo'shish va buyurtma berish.
- 📱 **Telegram WebApp**: Interaktiv va zamonaviy mobil menyu orqali qulay buyurtma.
- 💼 **Admin Panel**: Real vaqt rejimida tushumlar, kunlik buyurtmalar, taomlar va toifalar boshqaruvi.
- 💳 **To'lovlar**: Payme / Click orqali to'lov cheklarini yuklash va tasdiqlash.
- ⚡ **Supabase Cloud DB**: Bulutli PostgreSQL ma'lumotlar bazasi va to'lov cheklari uchun Cloud Storage.
- 🛡 **Avtomatik Fallback**: Agar internet yoki baza vaqtincha uzilsa, lokal zaxiradan uzluksiz ishlash kafolati.

## Supabase Bazani Sozlash (1 marta qilinadi)
1. [Supabase Dashboard](https://supabase.com/dashboard) ga kiring va loyihangizni oching.
2. Chap menyudan **SQL Editor** bo'limiga o'ting.
3. Loyihadagi `supabase_schema.sql` fayli ichidagi barcha kodni nusxalang va SQL Editor oynasiga joylashtirib, **"Run"** tugmasini bosing.
4. Jadvallar (`orders`, `menu_items`, `menu_categories`, `cafe_settings`) va storage bucket (`receipts`) avtomatik yaratiladi!

## Ishga tushirish
1. Bog'liqliklarni o'rnating:
```bash
pip install -r requirements.txt
```

2. `.env` faylida kalitlar to'g'riligini tekshiring:
```env
BOT_TOKEN=8728959771:AAE7gczpAq26lFuHMQfigxwzF6n3Ix6_06Y
ADMIN_ID=8469252037
SUPABASE_URL=https://jtzuytfxeakexupudxoy.supabase.co
SUPABASE_KEY=sb_publishable_0yEdTo2GGH0slSNwSB91sA_Zt8p75Xb
PORT=10000
```

3. Serverni ishga tushiring:
```bash
python istanbul_cafe_bot.py
```
