# Universal Telegram Identity & Message Intelligence Bot

Heroku-ready Telegram bot built with Python, aiogram v3, and MongoDB.

The bot is button-first and English-only. Users can open `/start`, send or forward supported Telegram messages/media, and receive clean identity/message/file reports with honest privacy limitation labels. Owner tools are available through `/admin`.

## Features

- User Identity Card on `/start`
- Auto-detected reports for messages, forwards, replies, groups, forum topics, channels, and media
- Simple report first, advanced details behind buttons, raw developer data for premium users
- Truth Engine explanations for Telegram IDs, message IDs, file IDs, usernames, and hidden sources
- Privacy labels for hidden/private/not-provided/no-access fields
- Premium system with Telegram Stars payments using `XTR`
- Referral rewards and premium-day activation
- Saved reports, exports, report comparison, and file vault service foundations
- Owner-only admin command center
- Force subscription gate that only shows missing channels
- Broadcast progress model with sent/failed/blocked/invalid/remaining counters
- MongoDB storage for users, reports, raw data, payments, referrals, bans, broadcasts, logs, errors, settings, force-sub channels, file vault, and compare sessions

## Local Setup

1. Create a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in the three required values:

```env
BOT_TOKEN=your_bot_token
OWNER_ID=your_numeric_telegram_id
MONGO_URI=your_mongodb_atlas_uri
```

All other values have defaults. Support URL and log channel can be configured later from `/admin` -> `Settings`.

Accepted aliases are also supported: `TELEGRAM_BOT_TOKEN` for the bot token, `ADMIN_ID` for owner ID, and `MONGO_DB_URL` / `MONGODB_URI` for MongoDB.
4. Run:

```powershell
python -m app.main
```

Only `/start` and `/admin` are registered as visible bot commands. `/paysupport` is implemented because Telegram requires payment support for Stars transactions.

## Data Policy

Reports and raw data are stored in MongoDB for bot operation, exports, admin diagnostics, and premium saved-report features. They are not publicly visible, and normal users do not browse report history unless premium saved reports are enabled.

## Telegram Limits

The bot never claims it can reveal hidden forwarded senders, private channels, deleted users, protected content, inaccessible permissions, or fields not provided by the Bot API. Unavailable fields are marked with a clear reason.
