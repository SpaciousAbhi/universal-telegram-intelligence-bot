VISIBLE_COMMANDS = {
    "start": "Open your Telegram profile report",
    "admin": "Owner control center",
}

PAYMENT_SUPPORT_COMMAND = "paysupport"

CALLBACK_MAX_BYTES = 64
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024

MAIN_MENU = [
    ("👤 My Info", "u:me"),
    ("🔍 Analyze Message", "u:analyze"),
    ("💾 Saved Reports", "u:saved"),
    ("⭐ Premium", "u:premium"),
    ("🎁 Referral", "u:referral"),
    ("❓ Help", "u:help"),
    ("📞 Support", "u:support"),
]

ADMIN_SECTIONS = [
    ("📊 Dashboard", "a:dash"),
    ("👥 Users", "a:users"),
    ("⭐ Premium Users", "a:premium"),
    ("🎁 Referrals", "a:refs"),
    ("📢 Broadcast", "a:bcast"),
    ("🔐 Force Subscribe", "a:fsub"),
    ("🚫 Ban / Unban", "a:ban"),
    ("📁 Reports", "a:reports"),
    ("💳 Payments", "a:payments"),
    ("📜 Logs", "a:logs"),
    ("⚠️ Errors", "a:errors"),
    ("📤 Export Data", "a:export"),
    ("⚙️ Settings", "a:settings"),
]

HELP_TOPICS = [
    ("Private chat guide", "h:private"),
    ("Group guide", "h:group"),
    ("Forwarded message guide", "h:forward"),
    ("Reply message guide", "h:reply"),
    ("Media/file report guide", "h:media"),
    ("Raw data guide", "h:raw"),
    ("Export guide", "h:export"),
    ("Premium guide", "h:premium"),
    ("Referral guide", "h:referral"),
]

