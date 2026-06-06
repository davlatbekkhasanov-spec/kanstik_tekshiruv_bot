# kanstik_tekshiruv_bot

Omborda terilgan yuklarni qayta tekshirish — Telegram bot (aiogram 3 + PostgreSQL).

## O'rnatish

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.main
```

## Railway

1. **Service type: Worker** (Web emas — polling bot port ochmaydi)
2. PostgreSQL plugin → bot servisida **Reference variable**:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (qo'lda copy emas!)
3. Env: `BOT_TOKEN`, `ADMIN_IDS=1432810519,7703650930`, `SETUP_MODE=1` (test — lichka)
4. Jamoa ro‘yxati `app/employee_registry.py` da — boshqa botlar bilan bir xil
5. Guruh tayyor bo‘lgach:
   - `REVIEW_GROUP_ID` — tekshiruvchilar guruhi (navbat, tasdiqlash)
   - `RETURN_GROUP_ID` — teruvchilar guruhi (xato «tuzating»)
   - `SETUP_MODE=0`
6. Deploy — migration **faqat bot ishga tushganda** (build vaqtida emas)
7. Railway **Build Command** bo'sh bo'lsin (agar `alembic upgrade head` qo'yilgan bo'lsa — o'chiring)

## Ish oqimi (SETUP_MODE=0)

1. Teruvchi **lichasidan** yuboradi → **tekshiruv guruhiga** tushadi
2. Tekshiruvchi guruhda **qabul qiladi** → tekshiruv **uning lichkasida** davom etadi
3. Xato bo‘lsa → **teruvchi guruhi** + **teruvchi lichkasi**; tekshiruvchi lichkasi yopiladi
4. Teruvchi **tuzatdim** bosadi → **tekshiruv guruhiga** tasdiqlash
5. Guruhda tasdiqlansa — tugaydi; **yana xato** bo‘lsa — teruvchiga qaytadi

## Buyruqlar

- Teruvchi: `📦 Tekshiruvga yuborish`
- Admin: `/daily`, `/monthly`

## Repo

https://github.com/davlatbekkhasanov-spec/kanstik_tekshiruv_bot
