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
2. PostgreSQL plugin qo'shing → `DATABASE_URL` avtomatik ulanadi
3. Env: `BOT_TOKEN`, `ADMIN_IDS`, `SETUP_MODE=1` (test — lichka)
4. Guruh tayyor bo‘lgach: `REVIEW_GROUP_ID`, `RETURN_GROUP_ID`, `SETUP_MODE=0`
5. Deploy — `Procfile`: `alembic upgrade head` + `worker: python -m app.main`

## Buyruqlar

- Teruvchi: `📦 Tekshiruvga yuborish`
- Admin: `/daily`, `/monthly`

## Repo

https://github.com/davlatbekkhasanov-spec/kanstik_tekshiruv_bot
