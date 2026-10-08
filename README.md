# Istanbul Cafe Bot & Web Management

Istanbul Cafe uchun Telegram Bot, Veb Menyu (WebApp) va Admin Boshqaruv Paneli.

## Xususiyatlari
- 🤖 **Telegram Bot**: Taomlarni ko'rish, savatga qo'shish va buyurtma berish (`@Istanbul_cafe_bot`).
- 📱 **Telegram WebApp**: Interaktiv va zamonaviy mobil menyu orqali qulay buyurtma.
- 💼 **Admin Panel**: Real vaqt rejimida tushumlar, kunlik buyurtmalar, taomlar va toifalar boshqaruvi (`/admin`).
- 💳 **To'lovlar**: Payme / Click orqali to'lov cheklarini yuklash va tasdiqlash.
- ⚡ **Supabase Cloud DB**: Bulutli PostgreSQL ma'lumotlar bazasi va to'lov cheklari uchun Cloud Storage.
- 🛡 **Avtomatik Fallback**: Agar internet yoki baza vaqtincha uzilsa, lokal zaxiradan uzluksiz ishlash kafolati.
- 🚀 **Vercel Serverless Ready**: Hech qanday server xarajatlarisiz Vercel-da 24/7 ishlash.

## Vercel-da Ishga Tushirish (Serverless Webhook)
1. GitHub repozitoriyasini Vercel-ga ulang (`dostonn941-oss/istanbul_bot`).
2. Environment Variables (ixtiyoriy, avtomatik standart qiymatlar ham mavjud):
   - `BOT_TOKEN`: `8780942618:AAEM8JdnmV2vPyoFrYGIm7dbd7Z964zsaxg`
   - `ADMIN_ID`: `8469252037`
   - `SUPABASE_URL`: `https://gjbxlcdjvvlahudfdabj.supabase.co`
   - `SUPABASE_KEY`: `sb_publishable_FK_hBF3B_c3YBgq9nxySzA_DE8iAohw`
3. Deploy tugagach, loyihangiz Vercel domeniga ega bo'ladi (masalan: `https://loyihangiz.vercel.app`).
4. **Telegram Botni Vercel-ga ulash (1 bosishda):**
   - Brauzeringizda oching: `https://loyihangiz.vercel.app/api/set-webhook`
   - YOKI Admin panelga kiring (`https://loyihangiz.vercel.app/admin`), **Sozlamalar** bo'limiga o'ting va **"⚡ Webhookni ushbu Vercel domeniga ulash"** tugmasini bosing.
   - Barcha sozlamalar (Webhook, WebApp menyu tugmasi, bot tavsifi, `/start` va `/admin` komandalari) avtomatik o'rnatiladi!

## Supabase Bazani Sozlash
1. [Supabase Dashboard](https://supabase.com/dashboard) ga kiring va loyihangizni oching.
2. Chap menyudan **SQL Editor** bo'limiga o'ting.
3. Loyihadagi `supabase_schema.sql` fayli ichidagi kodni ishga tushiring.
4. Menyu taomlarini bazaga sinxronlash uchun:
```bash
python sync_menu_to_supabase.py
```

## Lokal Kompyuterda Ishga Tushirish
1. Bog'liqliklarni o'rnating:
```bash
pip install -r requirements.txt
```

2. Agar avval Vercel webhook ulangan bo'lsa, lokal polling uchun uni bekor qiling:
```bash
python set_webhook.py --delete
```

3. Bot va veb-serverni ishga tushiring:
```bash
python istanbul_cafe_bot.py
```
