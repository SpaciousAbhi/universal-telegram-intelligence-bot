# Heroku Deployment

## Required Resources

- Heroku app with a worker dyno
- MongoDB Atlas database
- Telegram bot token from BotFather
- Owner Telegram ID

## Config Vars

Set only these required values in Heroku config:

- `BOT_TOKEN`
- `OWNER_ID`
- `MONGO_URI`

Accepted aliases:

- Bot token: `BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, or `TOKEN`
- Owner ID: `OWNER_ID`, `ADMIN_ID`, or `BOT_OWNER_ID`
- Mongo URL: `MONGO_URI`, `MONGO_URL`, `MONGO_DB_URL`, `MONGO_DBURL`, `MONGODB_URI`, `MONGODB_URL`, or `MONGODBURL`

Everything else has a code default:

- `DB_NAME=telegram_intelligence_bot`
- `SUPPORT_URL=https://t.me/support`
- `GROUP_COOLDOWN_SECONDS=20`
- `DEFAULT_TIMEZONE=UTC`
- `PREMIUM_PLANS_JSON` with 30/90/365 day Stars plans
- `REFERRAL_REWARD_DAYS=3`

After the bot is running, open `/admin` → `Settings` to set:

- Support URL
- Log channel ID

These admin settings are stored in MongoDB and do not require Heroku config changes.

Do not commit real secrets.

## Process

The `Procfile` starts the bot as a worker:

```text
worker: python -m app.main
```

Polling is used by default for simplicity. Do not run multiple worker dynos with the same Telegram token unless the polling strategy is redesigned.

## Pre-Deploy Checks

```powershell
python -m compileall app
python -m pytest
```

After deploy, inspect:

```powershell
heroku ps -a <app>
heroku logs --tail -a <app>
```

## Operational Notes

- MongoDB indexes are created on startup.
- The bot registers only `/start` and `/admin` as visible commands.
- The first deploy needs only `BOT_TOKEN`, `OWNER_ID`, and `MONGO_URI`.
- Support URL and log channel can be managed from `/admin` → `Settings`.
- Telegram Stars premium invoices use `XTR` and an empty provider token for digital services.
- Payment history stores `telegram_payment_charge_id` for future support/refund workflows.
- Errors are stored with an error code and traceback in MongoDB.
