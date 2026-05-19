# Heroku Deployment

## Required Resources

- Heroku app with a worker dyno
- MongoDB Atlas database
- Telegram bot token from BotFather
- Owner Telegram ID

## Config Vars

Set these in Heroku config:

- `BOT_TOKEN`
- `OWNER_ID`
- `MONGO_URI`
- `DB_NAME`
- `LOG_CHANNEL_ID`
- `SUPPORT_URL`
- `GROUP_COOLDOWN_SECONDS`
- `DEFAULT_TIMEZONE`
- `PREMIUM_PLANS_JSON`
- `REFERRAL_REWARD_DAYS`

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
- Telegram Stars premium invoices use `XTR` and an empty provider token for digital services.
- Payment history stores `telegram_payment_charge_id` for future support/refund workflows.
- Errors are stored with an error code and traceback in MongoDB.

