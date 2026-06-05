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

1. PostgreSQL plugin qo'shing
2. Env: `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`, `SETUP_MODE=1` (test — lichka)
3. Guruh tayyor bo‘lgach: `REVIEW_GROUP_ID`, `RETURN_GROUP_ID`, `SETUP_MODE=0`
3. Deploy — `Procfile` avtomatik `alembic upgrade head` + bot

## Buyruqlar

- Teruvchi: `📦 Tekshiruvga yuborish`
- Admin: `/daily`, `/monthly`

## Repo

https://github.com/davlatbekkhasanov-spec/kanstik_tekshiruv_bot
