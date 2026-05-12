import logging
import os
import json
import re
import sqlite3
import asyncio
import urllib.request
import urllib.parse
import urllib.error
import json as _json
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    JobQueue
)

# ══════════════════════════════════════════════
#   HOLIDAY DEFINITIONS
# ══════════════════════════════════════════════
HOLIDAYS = {
    (1, 1):   "New Year's Day",
    (4, 18):  "Good Friday",
    (4, 21):  "Easter Monday",
    (5, 1):   "Labour Day",
    (6, 1):   "Madaraka Day",
    (10, 10): "Huduma Day",
    (10, 20): "Mashujaa Day",
    (12, 12): "Jamhuri Day",
    (12, 25): "Christmas Day",
    (12, 26): "Boxing Day",
}

HOLIDAY_QUOTES = {
    "New Year's Day":   "🎆 New year, new wins! Wishing you a prosperous year ahead from *Skyline Technologies*! 🚀",
    "Good Friday":      "✝️ Reflecting on grace and renewal this Good Friday. From all of us at *Skyline Technologies*, wishing you peace. 🕊",
    "Easter Monday":    "🐣 Happy Easter! May this season bring you joy and new beginnings. — *Skyline Technologies* 🌸",
    "Labour Day":       "💪 Happy Labour Day! Celebrating every hardworking soul out there. Keep building! — *Skyline Technologies* 🏗",
    "Madaraka Day":     "🇰🇪 Happy Madaraka Day! We celebrate freedom and the spirit of progress. — *Skyline Technologies* ✊",
    "Huduma Day":       "🤝 Happy Huduma Day! Service and dedication define us. — *Skyline Technologies* 🌟",
    "Mashujaa Day":     "🦁 Happy Mashujaa Day! We honour our heroes. Courage builds nations. — *Skyline Technologies* 🇰🇪",
    "Jamhuri Day":      "🎉 Happy Jamhuri Day! Here's to Kenya's greatness — past, present and future. — *Skyline Technologies* 🌍",
    "Christmas Day":    "🎄 Merry Christmas! Wishing you love, joy and blessings this festive season. — *Skyline Technologies* 🎁",
    "Boxing Day":       "🎁 Happy Boxing Day! Hope you're enjoying the holiday season. — *Skyline Technologies* 🎉",
}

DAILY_QUOTES = [
    "💡 *Quote of the Day:* \"Success is not final; failure is not fatal: it is the courage to continue that counts.\" — Churchill",
    "🚀 *Daily Motivation:* \"The best time to plant a tree was 20 years ago. The second best time is now.\"",
    "🌟 *Skyline Wisdom:* \"Digital solutions that elevate your business start with one bold step.\"",
    "💎 *Daily Gem:* \"Work hard in silence, let your success be your noise.\"",
    "🔥 *Today's Fire:* \"Don't watch the clock; do what it does. Keep going.\" — Sam Levenson",
    "🌍 *African Proverb:* \"If you want to go fast, go alone. If you want to go far, go together.\"",
    "⚡ *Tech Thought:* \"Innovation is seeing what everybody has seen and thinking what nobody has thought.\"",
    "🏆 *Champion Mindset:* \"Champions aren't made in the gyms. Champions are made from something deep inside them.\"",
    "🌈 *Positivity:* \"Every day is a new beginning. Take a deep breath, smile, and start again.\"",
    "💪 *Hustle Quote:* \"Your limitation — it's only your imagination. Push beyond it today!\"",
]

def escape_md(text: str) -> str:
    for char in ['_', '*', '`', '[']:
        text = text.replace(char, f'\\{char}')
    return text

# ══════════════════════════════════════════════
#   CONFIG — EDIT THESE
# ══════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8589728931:AAFTJDW94p_BOTr-q6AXua-hunOXmbXNSDQ")
ADMIN_ID     = int(os.environ.get("ADMIN_ID", "6105493227"))

BOT_NAME     = "Dev Clin"
BOT_HANDLE   = "@DevClinBot"
COMPANY      = "Skyline Technologies"
TAGLINE      = "Elevating Digital Solutions"

WELCOME_MSG  = (
    "👋 Welcome to *Dev Clin* — your digital store powered by *Skyline Technologies!*\n\n"
    "🏙 _Elevating Digital Solutions_\n\n"
    "What would you like to do today? 👇"
)

# ══════════════════════════════════════════════
#   M-PESA PAYMENT CONFIG
# ══════════════════════════════════════════════
MPESA_RECEIVER_NAME   = "Clinton Oduor"
MPESA_RECEIVER_NUMBER = "0743810633"
PAYBILL_NAME          = "Skyline Technologies"

def get_mpesa_settings():
    """Read M-Pesa settings from DB, fall back to defaults."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings WHERE key IN ('mpesa_name','mpesa_number')")
        rows = dict(c.fetchall())
        conn.close()
        name = rows.get("mpesa_name", MPESA_RECEIVER_NAME)
        number = rows.get("mpesa_number", MPESA_RECEIVER_NUMBER)
        return name, number
    except:
        return MPESA_RECEIVER_NAME, MPESA_RECEIVER_NUMBER

# Me button
ME_LINK  = "https://yourportfolio.com"
ME_LABEL = "👤 Me"
ME_BIO   = "Built by Dev Clin 🚀\nSkyline Technologies — Elevating Digital Solutions"

CYBER_IMAGE  = "https://i.postimg.cc/CLHFDLbK/Gemini-Generated-Image-avf6o5avf6o5avf6.png"

ADMIN_TG  = "@yourusername"
WHATSAPP  = "https://wa.me/234XXXXXXXXX"
INSTAGRAM = "https://instagram.com/skyline_tech"

# ══════════════════════════════════════════════
#   DATABASE SETUP
# ══════════════════════════════════════════════
DB_PATH = "devclin.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT,
        category TEXT,
        price TEXT,
        price_value REAL,
        type TEXT,
        desc TEXT,
        link TEXT,
        icon TEXT,
        active INTEGER DEFAULT 1,
        image_url TEXT DEFAULT '',
        original_price REAL DEFAULT 0,
        drop_price REAL DEFAULT 0
    )''')

    # Migrate existing products table to add new columns if missing
    try:
        c.execute("ALTER TABLE products ADD COLUMN image_url TEXT DEFAULT ''")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN original_price REAL DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN drop_price REAL DEFAULT 0")
    except: pass

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id TEXT PRIMARY KEY,
        label TEXT,
        icon TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        joined_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        product_id TEXT,
        product_name TEXT,
        amount TEXT,
        status TEXT DEFAULT "pending",
        mpesa_msg TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        from_name TEXT,
        to_user_id INTEGER,
        message TEXT,
        direction TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # New tables
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        product_id TEXT,
        product_name TEXT,
        rating INTEGER,
        review TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bot_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        rating INTEGER,
        review TEXT,
        created_at TEXT
    )''')

    # Seed default settings
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_name', 'Clinton Oduor')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_number', '0743810633')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('ai_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('downloader_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('admin_logo_url', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('bot_banner_url', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('group_chat_link', '')")

    # Table for persistent user states (survives restarts)
    c.execute('''CREATE TABLE IF NOT EXISTS user_states_db (
        user_id INTEGER PRIMARY KEY,
        state INTEGER,
        extra TEXT,
        updated_at TEXT
    )''')

    conn.commit()
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        default_products = [
            ("p1","School Notes Bundle","education","KSh 500",500,"PDF","Complete notes for SS1–SS3. All subjects covered.","","📚",1),
            ("p2","Business Plan Template","education","KSh 800",800,"DOCX","Professional business plan template. Editable Word format.","","📄",1),
            ("p3","Android VPN App","apps","KSh 1,200",1200,"APK","Premium VPN for Android. Fast, secure, unlimited data.","","📱",1),
            ("p4","Afrobeats Mix 2024","music","KSh 300",300,"MP3","Hot afrobeats collection — 30 tracks, 45 minutes.","","🎵",1),
            ("p5","Tech Tutorial Series","videos","KSh 2,000",2000,"MP4","Full coding tutorial series. Python, Web Dev & more.","","🎬",1),
            ("p6","Galaxy Tab A9","gadgets","KSh 85,000",85000,"PRODUCT","Samsung Galaxy Tab A9 — brand new sealed box. Fast delivery.","","💻",1),
        ]
        c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)", default_products)

    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_cats = [
            ("education","📚 Education","📚"),
            ("apps","📱 Apps / APK","📱"),
            ("music","🎵 Music","🎵"),
            ("videos","🎬 Videos","🎬"),
            ("gadgets","💻 Gadgets","💻"),
            ("documents","📄 Documents","📄"),
        ]
        c.executemany("INSERT INTO categories VALUES (?,?,?)", default_cats)

    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_PATH)

def set_user_state(user_id: int, state: int, extra: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_states_db (user_id, state, extra, updated_at) VALUES (?,?,?,?)",
        (user_id, state, extra, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    user_states[user_id] = state

def get_user_state(user_id: int):
    if user_id in user_states:
        return user_states[user_id]
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT state, extra FROM user_states_db WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        if row:
            user_states[user_id] = row[0]
            if row[1]:
                pending_payments[user_id] = row[1]
            return row[0]
    except:
        pass
    return None

def clear_user_state(user_id: int):
    user_states.pop(user_id, None)
    try:
        conn = get_db()
        conn.execute("DELETE FROM user_states_db WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def get_settings() -> dict:
    """Read all settings from DB."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings")
        rows = c.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except:
        return {}

def get_api_setting(key: str, env_fallback: str = "") -> str:
    """Read an API key from settings DB, falling back to env var."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return row[0].strip()
    except:
        pass
    return os.environ.get(env_fallback, "")

def register_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?)",
              (user.id, user.username or "", user.full_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_products(category=None, active_only=True):
    conn = get_db()
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM products WHERE category=? AND active=?", (category, 1 if active_only else 0))
    else:
        q = "SELECT * FROM products WHERE active=1" if active_only else "SELECT * FROM products"
        c.execute(q)
    rows = c.fetchall()
    conn.close()
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active","image_url","original_price","drop_price"]
    # Pad rows that don't have the new columns
    result = []
    for r in rows:
        d = dict(zip(keys[:len(r)], r))
        for k in keys:
            if k not in d:
                d[k] = 0 if k in ("original_price","drop_price") else ""
        result.append(d)
    return result

def get_product(prod_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (prod_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active","image_url","original_price","drop_price"]
    d = dict(zip(keys[:len(row)], row))
    for k in keys:
        if k not in d:
            d[k] = 0 if k in ("original_price","drop_price") else ""
    return d

def get_categories():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM categories")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "label": r[1], "icon": r[2]} for r in rows]

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, full_name FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def save_order(user, product, mpesa_msg="", status="pending"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id,username,full_name,product_id,product_name,amount,status,mpesa_msg,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (user.id, user.username or "", user.full_name,
               product["id"], product["name"], product["price"],
               status, mpesa_msg, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def log_message(from_id, from_name, to_id, message, direction):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user_id,from_name,to_user_id,message,direction,created_at) VALUES (?,?,?,?,?,?)",
              (from_id, from_name, to_id, message, direction, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
#   CONVERSATION STATES
# ══════════════════════════════════════════════
AWAIT_MPESA_MSG      = 1
AWAIT_REPLY_TARGET   = 2
AWAIT_REPLY_MSG      = 3
AWAIT_BROADCAST      = 4
AWAIT_YT_SEARCH      = 11
AWAIT_TIKTOK_LINK    = 12
AWAIT_FB_LINK        = 13
AWAIT_SPOTIFY_SEARCH = 14
AWAIT_YTMUSIC_SEARCH = 15
AWAIT_DL_LINK        = 16
AWAIT_AI_CHAT        = 17
AWAIT_PRODUCT_RATING = 18
AWAIT_BOT_RATING     = 19

# Pending payments: {user_id: product_id}
pending_payments = {}
# Admin reply targets: {admin_id: target_user_id}
admin_reply_targets = {}
# Per-user state tracking
user_states = {}      # user_id -> state constant
user_dl_platform = {} # user_id -> platform name for downloader
# Pending ratings: {user_id: {"product_id": ..., "rating": ...}}
pending_ratings = {}
# Pending bot ratings: {user_id: {"rating": ...}}
pending_bot_ratings = {}

def get_banner_url():
    """Get bot banner URL from settings, fall back to CYBER_IMAGE."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key='bot_banner_url'")
        row = c.fetchone()
        conn.close()
        if row and row[0].strip():
            return row[0].strip()
    except:
        pass
    return CYBER_IMAGE

def get_group_link():
    """Get group chat link from settings."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key='group_chat_link'")
        row = c.fetchone()
        conn.close()
        if row and row[0].strip():
            return row[0].strip()
    except:
        pass
    return ""

# ══════════════════════════════════════════════
#   LOGGING
# ══════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#   HELPERS
# ══════════════════════════════════════════════
def me_button():
    return InlineKeyboardButton(ME_LABEL, url=ME_LINK)

def back_home_row():
    return [InlineKeyboardButton("🏠 Main Menu", callback_data="home")]

def me_row():
    return [me_button(), InlineKeyboardButton("📞 Contact", callback_data="contact")]

async def send_cyber_footer(update_or_query, context, caption, keyboard):
    banner = get_banner_url()
    full_caption = f"{caption}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    markup = InlineKeyboardMarkup(keyboard)

    # Case 1: it's a CallbackQuery object
    if hasattr(update_or_query, 'edit_message_media'):
        try:
            await update_or_query.edit_message_media(
                media=InputMediaPhoto(media=banner, caption=full_caption, parse_mode="Markdown"),
                reply_markup=markup
            )
            return
        except Exception:
            pass
        # Fallback: try edit text
        try:
            await update_or_query.edit_message_caption(
                caption=full_caption, parse_mode="Markdown", reply_markup=markup
            )
            return
        except Exception:
            pass
        # Fallback: send new message via message object on the query
        try:
            await update_or_query.message.reply_photo(
                photo=banner, caption=full_caption,
                parse_mode="Markdown", reply_markup=markup
            )
            return
        except Exception as e:
            logger.error(f"send_cyber_footer (query) all fallbacks failed: {e}")
        return

    # Case 2: it's an Update object (from /start command)
    try:
        if update_or_query.message:
            await update_or_query.message.reply_photo(
                photo=banner, caption=full_caption,
                parse_mode="Markdown", reply_markup=markup
            )
            return
    except Exception as e:
        logger.error(f"send_cyber_footer (update) failed: {e}")


async def start_from_query(query, context):
    """Show main menu from a callback query (button press)."""
    user_states.pop(query.from_user.id, None)
    group_link = get_group_link()
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu")],
        [InlineKeyboardButton("🔗 Links",       callback_data="links"),
         InlineKeyboardButton("ℹ About",        callback_data="about")],
        [InlineKeyboardButton("📞 Contact",     callback_data="contact"),
         InlineKeyboardButton("⭐ Rate Us",      callback_data="bot_rate")],
        [InlineKeyboardButton("💬 Group Chat",  url=group_link if group_link else "https://t.me/")],
        [me_button()],
    ]
    await send_cyber_footer(query, context, WELCOME_MSG, keyboard)

# ══════════════════════════════════════════════
#   M-PESA VERIFICATION  (name check REMOVED)
#   Only amount + phone number must match
# ══════════════════════════════════════════════
def parse_mpesa_message(msg: str, expected_amount: float):
    """
    Parse an M-Pesa Send Money confirmation SMS and verify:
    - Receiver phone number matches configured number
    - Amount matches expected product price
    Name check is intentionally NOT performed.
    Returns (True, details_dict) or (False, error_reason)
    """
    receiver_name, receiver_number = get_mpesa_settings()

    # ── Phone number check ──────────────────────────────────────────────
    number_clean = receiver_number.replace("+", "").replace(" ", "")
    number_254   = "254" + number_clean[-9:] if not number_clean.startswith("254") else number_clean
    number_07    = "0" + number_clean[-9:]

    if number_clean not in msg and number_254 not in msg and number_07 not in msg:
        return False, f"❌ Receiver number *{receiver_number}* not found in the message."

    # ── Amount check ────────────────────────────────────────────────────
    amount_match = re.search(r'[Kk][Ss][Hh]\.?\s*([\d,]+\.?\d*)', msg)
    if not amount_match:
        amount_match = re.search(r'([\d,]+\.\d{2})', msg)

    if not amount_match:
        return False, "❌ Could not read the amount from the message."

    amount_str = amount_match.group(1).replace(",", "")
    try:
        paid_amount = float(amount_str)
    except ValueError:
        return False, "❌ Could not parse the amount from the message."

    if abs(paid_amount - expected_amount) > 1:
        return False, (
            f"❌ Amount mismatch. Expected *KSh {expected_amount:,.0f}* "
            f"but found *KSh {paid_amount:,.0f}* in the message."
        )

    # ── Extract extras ──────────────────────────────────────────────────
    date_match    = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', msg)
    date_str      = date_match.group(0) if date_match else "N/A"
    receipt_match = re.search(r'\b([A-Z0-9]{8,12})\b', msg)
    receipt       = receipt_match.group(1) if receipt_match else "N/A"

    return True, {
        "amount":   paid_amount,
        "date":     date_str,
        "receiver": receiver_name,
        "number":   receiver_number,
        "receipt":  receipt,
    }

# ══════════════════════════════════════════════
#   ⬇️ DOWNLOADER BOT MENU
# ══════════════════════════════════════════════
async def show_downloader_menu(query, context):
    text = (
        "⬇️ *Downloader Bot*\n\n"
        "Download content from your favourite platforms!\n\n"
        "Choose a platform 👇"
    )
    buttons = [
        [InlineKeyboardButton("▶️ YouTube",       callback_data="dl_youtube"),
         InlineKeyboardButton("🎵 YouTube Music", callback_data="dl_ytmusic")],
        [InlineKeyboardButton("🎵 Spotify",       callback_data="dl_spotify"),
         InlineKeyboardButton("📱 TikTok",        callback_data="dl_tiktok")],
        [InlineKeyboardButton("📘 Facebook",      callback_data="dl_facebook")],
        back_home_row(),
        me_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def prompt_downloader(query, context, platform: str, state: int):
    user_id = query.from_user.id
    set_user_state(user_id, state, platform)
    user_dl_platform[user_id] = platform

    platform_labels = {
        "youtube":  "▶️ YouTube",
        "ytmusic":  "🎵 YouTube Music",
        "spotify":  "🎵 Spotify",
        "tiktok":   "📱 TikTok",
        "facebook": "📘 Facebook",
    }
    label = platform_labels.get(platform, platform.title())

    text = (
        f"⬇️ *{label} Downloader*\n\n"
        f"Paste the link below and I'll download it for you 👇\n\n"
        f"_Example:_ `https://www.{platform}.com/...`"
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="downloader_menu")]]
    await send_cyber_footer(query, context, text, buttons)

async def handle_downloader_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Download via cobalt.tools and send the file."""
    user = update.effective_user
    platform = user_dl_platform.pop(user.id, "media")
    user_states.pop(user.id, None)

    platform_labels = {
        "youtube":  "▶️ YouTube",
        "ytmusic":  "🎵 YouTube Music",
        "spotify":  "🎵 Spotify",
        "tiktok":   "📱 TikTok",
        "facebook": "📘 Facebook",
    }
    label = platform_labels.get(platform, platform.title())

    wait_msg = await update.message.reply_text(
        f"⬇️ Downloading from {label}... please wait ⏳\n"
        "_This may take a few seconds_",
        parse_mode="Markdown"
    )

    result = await download_media_cobalt(url)

    await wait_msg.delete()

    if "error" in result:
        buttons = [
            [InlineKeyboardButton("🔁 Try Again", callback_data=f"dl_{platform}")],
            [InlineKeyboardButton("⬇️ Downloader Menu", callback_data="downloader_menu")],
            back_home_row(),
        ]
        await update.message.reply_text(
            f"❌ *Download Failed*\n\n{result['error']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    dl_url  = result.get("url", "")
    fname   = result.get("filename", "media")

    try:
        # Detect if audio or video by filename extension
        if fname.endswith(".mp3") or fname.endswith(".m4a") or fname.endswith(".ogg"):
            await update.message.reply_audio(
                audio=dl_url,
                title=fname,
                caption=f"🎵 Downloaded from {label}\n\n_{BOT_NAME} | {COMPANY}_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_video(
                video=dl_url,
                caption=f"📥 Downloaded from {label}\n\n_{BOT_NAME} | {COMPANY}_",
                parse_mode="Markdown"
            )
    except Exception as e:
        # Fallback: send as URL if Telegram can't handle the file
        buttons = [
            [InlineKeyboardButton("📥 Open Download Link", url=dl_url)],
            back_home_row(),
        ]
        await update.message.reply_text(
            f"✅ *Download ready!*\n\nTap the button below to open/save your file from {label}.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# ══════════════════════════════════════════════
#   🤖 AI ASSISTANT MENU
# ══════════════════════════════════════════════
async def show_ai_menu(query, context):
    text = (
        "🤖 *AI Assistant*\n\n"
        "Powered by Claude AI 🧠\n\n"
        "Ask me anything! I can help with:\n"
        "• Questions & answers\n"
        "• Writing & editing\n"
        "• Math & coding\n"
        "• General advice\n\n"
        "Tap *Start Chat* to begin 👇"
    )
    buttons = [
        [InlineKeyboardButton("💬 Start AI Chat", callback_data="ai_start")],
        [InlineKeyboardButton("🗑 Clear History",  callback_data="ai_clear")],
        back_home_row(),
        me_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def prompt_ai_chat(query, context):
    user_id = query.from_user.id
    set_user_state(user_id, AWAIT_AI_CHAT)
    text = (
        "🤖 *AI Chat Active*\n\n"
        "Go ahead — type your question or message below 👇\n\n"
        "_Type /start at any time to return to the main menu._"
    )
    buttons = [[InlineKeyboardButton("❌ End Chat", callback_data="home")]]
    await send_cyber_footer(query, context, text, buttons)

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    """Send message to Claude and reply."""
    user = update.effective_user

    # Maintain history
    history = ai_history.get(user.id, [])
    thinking = await update.message.reply_text("🤖 Thinking... ⏳")

    reply = await ask_claude(user_message, history)

    # Update history (keep last 10 turns to avoid token bloat)
    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": reply})
    ai_history[user.id] = history[-20:]  # last 10 pairs

    await thinking.delete()

    buttons = [
        [InlineKeyboardButton("❌ End Chat", callback_data="home"),
         InlineKeyboardButton("🗑 Clear History", callback_data="ai_clear")],
    ]
    await update.message.reply_text(
        f"🤖 *AI Assistant*\n\n{reply}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ══════════════════════════════════════════════
#   SERVICES
# ══════════════════════════════════════════════
SERVICES = [
    {"name": "Web Development",  "price": "KSh 15,000+", "desc": "Full websites & web apps built from scratch.",  "icon": "🌐", "link": WHATSAPP},
    {"name": "Bot Development",  "price": "KSh 10,000+", "desc": "Telegram & WhatsApp bots with full features.", "icon": "🤖", "link": WHATSAPP},
    {"name": "Graphic Design",   "price": "KSh 3,000+",  "desc": "Logos, flyers, banners & brand identity.",     "icon": "🎨", "link": WHATSAPP},
    {"name": "App Installation", "price": "KSh 500",     "desc": "Remote installation & setup of any app.",      "icon": "📲", "link": WHATSAPP},
]

async def show_services(query, context):
    text = "🛠 *Our Services*\n\n"
    for s in SERVICES:
        text += f"{s['icon']} *{s['name']}* — {s['price']}\n_{s['desc']}_\n\n"

    buttons = [
        [InlineKeyboardButton(f"📩 Order: {s['name']}", url=s["link"])] for s in SERVICES
    ]
    buttons.append(back_home_row())
    buttons.append(me_row())
    # Send as new message so the current one stays visible
    banner = get_banner_url()
    full_caption = f"{text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    try:
        await query.message.reply_photo(
            photo=banner,
            caption=full_caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"show_services error: {e}")

# ══════════════════════════════════════════════
#   LINKS / ABOUT / CONTACT
# ══════════════════════════════════════════════
async def show_links(query, context):
    text = "🔗 *Our Links*\n\nFind us on all platforms 👇"
    buttons = [
        [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP)],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        [InlineKeyboardButton("✈ Telegram Channel", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        back_home_row(),
        me_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def show_about(query, context):
    text = (
        f"ℹ *About {BOT_NAME}*\n\n"
        f"🏙 *{COMPANY}*\n_{TAGLINE}_\n\n"
        f"We offer:\n• 📦 Digital products\n• 🎓 Educational materials\n"
        f"• 💻 Tech gadgets\n• 🛠 Development services\n"
        f"• ⬇️ Media downloader\n• 🤖 AI Assistant\n\n"
        f"📲 Bot: {BOT_HANDLE}\n📞 Admin: {ADMIN_TG}"
    )
    buttons = [
        [InlineKeyboardButton("🛍 Shop Now", callback_data="shop")],
        back_home_row(),
        me_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def show_contact(query, context):
    text = (
        f"📞 *Contact Us*\n\nWe're always available to help!\n\n"
        f"💬 WhatsApp: {WHATSAPP}\n✈ Telegram: {ADMIN_TG}\n📸 Instagram: {INSTAGRAM}\n\n"
        f"_Response time: Usually within minutes_ ⚡"
    )
    buttons = [
        [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP),
         InlineKeyboardButton("✈ Telegram DM", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        back_home_row(),
        [me_button()],
    ]
    await send_cyber_footer(query, context, text, buttons)

# ══════════════════════════════════════════════
#   ADMIN COMMANDS
# ══════════════════════════════════════════════
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Admin only.")
            return
        return await func(update, context)
    return wrapper

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔧 *Admin Panel — Dev Clin*\n\n"
        "Commands available:\n\n"
        "📦 *Products:*\n"
        "`/addproduct` — Add new product\n"
        "`/listproducts` — View all products\n"
        "`/editlink <id> <link>` — Update product link\n"
        "`/toggleproduct <id>` — Enable/disable product\n\n"
        "📂 *Categories:*\n"
        "`/addcategory <id> <icon> <label>` — Add category\n"
        "`/listcategories` — List categories\n\n"
        "📢 *Broadcast:*\n"
        "`/broadcast` — Send message to all users\n\n"
        "💬 *Clients:*\n"
        "`/users` — List all users\n"
        "`/msg <user_id> <message>` — Message a user\n"
        "`/orders` — View recent orders\n\n"
        "📊 *Stats:*\n"
        "`/stats` — Bot statistics"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='verified'")
    verified_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM products WHERE active=1")
    active_products = c.fetchone()[0]
    conn.close()

    text = (
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: *{total_users}*\n"
        f"📦 Active Products: *{active_products}*\n"
        f"🛒 Total Orders: *{total_orders}*\n"
        f"✅ Verified Payments: *{verified_orders}*\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_products(active_only=False)
    if not products:
        await update.message.reply_text("No products found.")
        return
    text = "📦 *All Products:*\n\n"
    for p in products:
        status = "✅" if p["active"] else "❌"
        text += f"{status} `{p['id']}` {p['icon']} *{p['name']}* — {p['price']}\nCategory: {p['category']} | Link: {'Set ✅' if p['link'] else 'Not set ❌'}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/editlink <product_id> <link>`", parse_mode="Markdown")
        return
    prod_id = args[0]
    link = " ".join(args[1:])
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET link=? WHERE id=?", (link, prod_id))
    affected = c.rowcount
    conn.commit()
    conn.close()
    if affected:
        await update.message.reply_text(f"✅ Link updated for product `{prod_id}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Product `{prod_id}` not found.", parse_mode="Markdown")

@admin_only
async def admin_toggle_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/toggleproduct <product_id>`", parse_mode="Markdown")
        return
    prod_id = args[0]
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT active FROM products WHERE id=?", (prod_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text(f"❌ Product `{prod_id}` not found.", parse_mode="Markdown")
        conn.close()
        return
    new_status = 0 if row[0] else 1
    c.execute("UPDATE products SET active=? WHERE id=?", (new_status, prod_id))
    conn.commit()
    conn.close()
    status_label = "✅ Enabled" if new_status else "❌ Disabled"
    await update.message.reply_text(f"{status_label} product `{prod_id}`.", parse_mode="Markdown")

@admin_only
async def admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *Add New Product*\n\n"
        "Send product details in this format:\n\n"
        "`/newproduct id|name|category|price|price_value|type|icon|description`\n\n"
        "Example:\n"
        "`/newproduct p7|Python Course|videos|KSh 1500|1500|MP4|🎓|Full Python programming course`",
        parse_mode="Markdown"
    )

@admin_only
async def admin_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args)
    parts = args.split("|")
    if len(parts) < 8:
        await update.message.reply_text("❌ Invalid format. Use: `id|name|category|price|price_value|type|icon|description`", parse_mode="Markdown")
        return
    pid, name, cat, price, price_val, ptype, icon, desc = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    try:
        price_val = float(price_val)
    except:
        price_val = 0.0
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (pid, name, cat, price, price_val, ptype, desc, "", icon, 1))
        conn.commit()
        await update.message.reply_text(f"✅ Product *{name}* added successfully!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    conn.close()

@admin_only
async def admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: `/addcategory <id> <icon> <label>`\nExample: `/addcategory ebooks 📖 E-Books`", parse_mode="Markdown")
        return
    cat_id = args[0]
    icon = args[1]
    label = " ".join(args[2:])
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories VALUES (?,?,?)", (cat_id, f"{icon} {label}", icon))
        conn.commit()
        await update.message.reply_text(f"✅ Category *{label}* added!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    conn.close()

@admin_only
async def admin_list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories()
    text = "📂 *Categories:*\n\n"
    for c in cats:
        text += f"{c['icon']} `{c['id']}` — {c['label']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users yet.")
        return
    text = f"👥 *All Users ({len(users)}):*\n\n"
    for u in users[:30]:
        uname = f"@{u[1]}" if u[1] else "no username"
        text += f"• `{u[0]}` — {u[2]} ({uname})\n"
    if len(users) > 30:
        text += f"\n_...and {len(users)-30} more_"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id,full_name,product_name,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No orders yet.")
        return
    text = "🛒 *Recent Orders:*\n\n"
    for r in rows:
        status_emoji = "✅" if r[4] == "verified" else "⏳"
        text += f"{status_emoji} `{r[0]}` — {r[1]}\n📦 {r[2]} | {r[3]}\n📅 {r[5][:10]}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/msg <user_id> <your message>`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    message = " ".join(args[1:])
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💬 *Message from Admin ({BOT_NAME}):*\n\n{message}\n\n_Reply to this message to respond._",
            parse_mode="Markdown"
        )
        log_message(ADMIN_ID, "Admin", target_id, message, "admin_to_user")
        await update.message.reply_text(f"✅ Message sent to user `{target_id}`.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}")

@admin_only
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/broadcast <your message>`\n\nThis sends the message to ALL bot users.",
            parse_mode="Markdown"
        )
        return
    message = " ".join(args)
    users = get_all_users()
    sent = 0
    failed = 0
    await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=f"📢 *Announcement from {BOT_NAME}:*\n\n{message}\n\n_{COMPANY}_",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Broadcast complete!\n📤 Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════
#   MESSAGE HANDLER  (M-Pesa + music/dl/AI + user replies)
# ══════════════════════════════════════════════
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    state = get_user_state(user.id)

    # ── M-Pesa verification ────────────────────────────────────────────
    if state == AWAIT_MPESA_MSG or user.id in pending_payments:
        prod_id = pending_payments.get(user.id)
        prod = get_product(prod_id) if prod_id else None
        if not prod:
            pending_payments.pop(user.id, None)
            user_states.pop(user.id, None)
            return

        ok, result = parse_mpesa_message(text, prod["price_value"])

        if ok:
            del pending_payments[user.id]
            user_states.pop(user.id, None)
            save_order(user, prod, mpesa_msg=text, status="verified")

            receipt_no  = result.get("receipt", "N/A")
            paid_amount = result["amount"]
            pay_date    = result["date"]
            recv_name, recv_num = get_mpesa_settings()

            # ── Receipt block shown to user ──────────────────────────────
            receipt_text = (
                f"🧾 *PAYMENT RECEIPT*\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🏪 *{COMPANY}*\n"
                f"📦 Product: *{prod['name']}*\n"
                f"💰 Amount: *KSh {paid_amount:,.0f}*\n"
                f"📅 Date: {pay_date}\n"
                f"🧾 M-Pesa Ref: `{receipt_no}`\n"
                f"📱 Sent to: {recv_num}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"✅ Payment confirmed. Thank you, {user.first_name}! 🎉"
            )

            admin_msg = (
                f"✅ *PAYMENT VERIFIED!*\n\n"
                f"👤 User: {user.full_name}\n"
                f"🔗 Handle: @{user.username or 'N/A'}\n"
                f"🆔 ID: `{user.id}`\n\n"
                f"📦 Product: *{prod['name']}*\n"
                f"💰 Amount Paid: *KSh {paid_amount:,.0f}*\n"
                f"🧾 Receipt: `{receipt_no}`\n"
                f"📅 Date: {pay_date}\n\n"
                f"M-Pesa msg:\n`{escape_md(text[:200])}`\n\n"
                f"{'✅ File link set — auto-sent to user.' if prod['link'] else '⚠️ No file link set. Send manually with /msg!'}"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Admin notify failed: {e}")

            if prod["link"]:
                # Send receipt first
                await update.message.reply_text(receipt_text, parse_mode="Markdown")
                # Then send the file immediately
                try:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=prod["link"],
                        caption=(
                            f"📦 *{prod['name']}*\n\n"
                            f"Here is your file! Enjoy 🚀\n\n"
                            f"_{BOT_NAME} | {COMPANY}_"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    # If not a document try sending as text link
                    try:
                        await context.bot.send_message(
                            chat_id=user.id,
                            text=f"📎 *Your download link:*\n{prod['link']}\n\n_{BOT_NAME} | {COMPANY}_",
                            parse_mode="Markdown"
                        )
                    except Exception as e2:
                        logger.error(f"File send error: {e2}")

                # Confirmation card with shop more button
                confirm = (
                    f"✅ *File Sent!*\n\n"
                    f"Check the message above 👆 for your file.\n\n"
                    f"📦 *{prod['name']}*\n"
                    f"🧾 Ref: `{receipt_no}`"
                )
                buttons = [
                    [InlineKeyboardButton("🛍 Shop More", callback_data="shop"),
                     InlineKeyboardButton("🏠 Home", callback_data="home")],
                    [me_button()],
                ]
                await update.message.reply_photo(
                    photo=CYBER_IMAGE,
                    caption=f"{confirm}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                # Send rating request after 2 seconds
                await asyncio.sleep(2)
                await send_product_rating_request(context, user.id, user.username or "", user.full_name, prod)
            else:
                # No link — receipt + notify user admin will deliver
                await update.message.reply_text(receipt_text, parse_mode="Markdown")
                confirm = (
                    f"✅ *Payment Confirmed!*\n\n"
                    f"Your receipt is above ☝️\n\n"
                    f"📦 *{prod['name']}*\n\n"
                    f"The admin has been notified and will deliver your item shortly. ⏳\n"
                    f"If you don't hear back in 10 minutes, contact us 👇"
                )
                buttons = [
                    [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                    [InlineKeyboardButton("🏠 Home", callback_data="home")],
                    [me_button()],
                ]
                await update.message.reply_photo(
                    photo=CYBER_IMAGE,
                    caption=f"{confirm}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                # Send rating request after 3 seconds
                await asyncio.sleep(3)
                await send_product_rating_request(context, user.id, user.username or "", user.full_name, prod)
        else:
            # ── Detailed warning message for wrong payment details ───────
            error_detail = result  # e.g. "❌ Amount mismatch..." or "❌ Phone not found..."
            recv_name, recv_num = get_mpesa_settings()

            # Determine what specifically went wrong
            if "number" in error_detail.lower() or "phone" in error_detail.lower() or "receiver" in error_detail.lower():
                hint = (
                    f"⚠️ *Wrong phone number detected!*\n\n"
                    f"Make sure you sent to:\n"
                    f"📱 *{recv_num}* ({recv_name})\n\n"
                    f"Then paste that confirmation SMS here again."
                )
            elif "amount" in error_detail.lower() or "mismatch" in error_detail.lower():
                hint = (
                    f"⚠️ *Wrong amount detected!*\n\n"
                    f"This product costs *{prod['price']}*.\n"
                    f"The SMS you sent shows a different amount.\n\n"
                    f"Did you pay the exact amount? If yes, make sure you paste the correct SMS."
                )
            elif "could not read" in error_detail.lower() or "could not parse" in error_detail.lower():
                hint = (
                    f"⚠️ *Could not read the M-Pesa message.*\n\n"
                    f"Please paste the *full* M-Pesa confirmation SMS exactly as you received it from Safaricom."
                )
            else:
                hint = f"⚠️ *Verification failed.* Please check the details and try again."

            fail_text = (
                f"❌ *Payment Not Verified*\n\n"
                f"{error_detail}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{hint}\n\n"
                f"*Expected payment details:*\n"
                f"📱 Phone: *{recv_num}*\n"
                f"💰 Amount: *{prod['price']}*\n\n"
                f"Paste the correct M-Pesa SMS below, or tap Cancel to go back."
            )
            buttons = [
                [InlineKeyboardButton("🔄 Try Again — Paste SMS", callback_data=f"paid_{prod_id}")],
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")],
            ]
            await update.message.reply_photo(
                photo=CYBER_IMAGE,
                caption=f"{fail_text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            # Keep user in pending state so they can paste again
            pending_payments[user.id] = prod_id
            user_states[user.id] = AWAIT_MPESA_MSG
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"⚠️ *Failed payment attempt*\n"
                        f"👤 {user.full_name} (@{user.username or 'N/A'}) `{user.id}`\n"
                        f"📦 {prod['name']}\n"
                        f"🔴 Reason: {error_detail}\n\n"
                        f"Message:\n`{escape_md(text[:200])}`"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        return

    # ── Downloader link ────────────────────────────────────────────────
    if state in (AWAIT_TIKTOK_LINK, AWAIT_FB_LINK, AWAIT_DL_LINK,
                 AWAIT_YT_SEARCH, AWAIT_YTMUSIC_SEARCH, AWAIT_SPOTIFY_SEARCH):
        await handle_downloader_link(update, context, text)
        return

    # ── AI Chat ────────────────────────────────────────────────────────
    if state == AWAIT_AI_CHAT:
        await handle_ai_chat(update, context, text)
        return

    # ── Product rating review ──────────────────────────────────────────
    if state == AWAIT_PRODUCT_RATING:
        data = pending_ratings.pop(user.id, {})
        prod_id = data.get("product_id", "")
        stars = data.get("rating", 5)
        review = text if text.lower() != "skip" else "(No review)"
        clear_user_state(user.id)
        await save_and_broadcast_product_review(context, user, prod_id, stars, review)
        prod = get_product(prod_id)
        pname = prod["name"] if prod else prod_id
        star_str = "⭐" * stars
        await update.message.reply_text(
            f"🙏 *Thank you for your review!*\n\n"
            f"📦 {pname}\n"
            f"Rating: {star_str} ({stars}/5)\n"
            f"💬 _{review}_\n\n"
            f"Your feedback helps us improve! 🚀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
        return

    # ── Bot rating review ──────────────────────────────────────────────
    if state == AWAIT_BOT_RATING:
        data = pending_bot_ratings.pop(user.id, {})
        stars = data.get("rating", 5)
        review = text if text.lower() != "skip" else "(No review)"
        clear_user_state(user.id)
        await save_and_broadcast_bot_review(context, user, stars, review)
        star_str = "⭐" * stars
        await update.message.reply_text(
            f"🙏 *Thank you for rating {BOT_NAME}!*\n\n"
            f"Rating: {star_str} ({stars}/5)\n"
            f"💬 _{review}_\n\n"
            f"We appreciate your feedback! 💚",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
        return

    # Admin shortcut — only when no active state
    if user.id == ADMIN_ID and state is None and user.id not in pending_payments:
        await update.message.reply_text(
            "👋 Use /admin for the admin panel or /msg <user_id> <message> to contact a user.",
            parse_mode="Markdown"
        )
        return

    # ── Default: forward to admin ──────────────────────────────────────
    log_message(user.id, user.full_name, ADMIN_ID, text, "user_to_admin")
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💬 *Message from user:*\n\n"
                f"👤 {user.full_name} (@{user.username or 'N/A'})\n"
                f"🆔 `{user.id}`\n\n"
                f"📩 {text}\n\n"
                f"_Reply with:_ `/msg {user.id} <your reply>`"
            ),
            parse_mode="Markdown"
        )
    except:
        pass

    await update.message.reply_text(
        f"💬 Your message has been forwarded to the admin.\n\nOr use /start to open the menu.\n\n_{BOT_NAME} | {COMPANY}_",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════
#   CALLBACK ROUTER
# ══════════════════════════════════════════════
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "home":
        user_states.pop(user_id, None)
        await start_from_query(query, context)

    elif data == "shop":
        await show_shop(query, context)
    elif data == "services":
        await show_services(query, context)
    elif data == "links":
        await show_links(query, context)
    elif data == "about":
        await show_about(query, context)
    elif data == "contact":
        await show_contact(query, context)
    elif data == "bot_rate":
        await show_bot_rating(query, context)

    elif data.startswith("cat_"):
        await show_category(query, context, data[4:])
    elif data.startswith("prod_"):
        await show_product(query, context, data[5:])
    elif data.startswith("paid_"):
        await payment_initiate(query, context, data[5:])

    # ── Downloader ─────────────────────────────────────────────────────
    elif data == "downloader_menu":
        await show_downloader_menu(query, context)
    elif data == "dl_youtube":
        await prompt_downloader(query, context, "youtube", AWAIT_YT_SEARCH)
    elif data == "dl_ytmusic":
        await prompt_downloader(query, context, "ytmusic", AWAIT_YTMUSIC_SEARCH)
    elif data == "dl_spotify":
        await prompt_downloader(query, context, "spotify", AWAIT_SPOTIFY_SEARCH)
    elif data == "dl_tiktok":
        await prompt_downloader(query, context, "tiktok", AWAIT_TIKTOK_LINK)
    elif data == "dl_facebook":
        await prompt_downloader(query, context, "facebook", AWAIT_FB_LINK)

    # ── AI ─────────────────────────────────────────────────────────────
    elif data == "ai_menu":
        await show_ai_menu(query, context)
    elif data == "ai_start":
        await prompt_ai_chat(query, context)
    elif data == "ai_clear":
        ai_history.pop(user_id, None)
        user_states.pop(user_id, None)
        await query.edit_message_caption(
            caption="🗑 *AI chat history cleared!*\n\nStart fresh 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Start AI Chat", callback_data="ai_start")],
                back_home_row(),
            ])
        )

    # ── Product rating ─────────────────────────────────────────────────
    elif data.startswith("prate_skip_"):
        # format: prate_skip_{prod_id}_{stars}
        parts = data.split("_", 4)
        prod_id = parts[2]
        stars = int(parts[3])
        clear_user_state(user_id)
        pending_ratings.pop(user_id, None)
        await save_and_broadcast_product_review(context, query.from_user, prod_id, stars, "(No review)")
        await query.edit_message_caption(
            caption=f"✅ *Rating saved!* {'⭐' * stars}\n\nThank you! 🙏",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
    elif data.startswith("prate_"):
        # format: prate_{prod_id}_{stars}
        parts = data.split("_", 2)
        prod_id = parts[1]
        stars = int(parts[2])
        await handle_product_rating_star(query, context, prod_id, stars)

    # ── Bot rating ─────────────────────────────────────────────────────
    elif data.startswith("brate_skip_"):
        stars = int(data.split("_")[2])
        clear_user_state(user_id)
        pending_bot_ratings.pop(user_id, None)
        await save_and_broadcast_bot_review(context, query.from_user, stars, "(No review)")
        await query.edit_message_caption(
            caption=f"✅ *Rating saved!* {'⭐' * stars}\n\nThank you! 🙏",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
    elif data.startswith("brate_"):
        stars = int(data.split("_")[1])
        await handle_bot_rating_star(query, context, stars)

# ══════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
#   /myorders — USER ORDER HISTORY
# ══════════════════════════════════════════════
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT product_name, amount, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15",
        (user.id,)
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "🛒 *My Orders*\n\nYou haven't made any orders yet.\n\nUse /start to browse the shop!",
            parse_mode="Markdown"
        )
        return

    text = f"🛒 *My Orders* — {user.first_name}\n\n"
    for r in rows:
        status_icon = "✅" if r[2] == "verified" else "⏳"
        text += f"{status_icon} *{r[0]}*\n💰 {r[1]} | 📅 {r[3][:10]}\n\n"

    buttons = [[InlineKeyboardButton("🛍 Shop More", callback_data="shop"),
                InlineKeyboardButton("🏠 Home", callback_data="home")]]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ══════════════════════════════════════════════
#   REFERRAL SYSTEM
# ══════════════════════════════════════════════
async def my_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE username LIKE ?", (f"ref_{user.id}_%",))
    # Simple count from referral tracking via start param
    conn.close()

    text = (
        f"🔗 *Your Referral Link*\n\n"
        f"Share this link with friends! When they join and make a purchase, you earn credit.\n\n"
        f"`{ref_link}`\n\n"
        f"_Tap the link above to copy it_ 👆\n\n"
        f"Contact admin to claim your referral rewards! 🎁"
    )
    buttons = [
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}&text=Check+out+{BOT_NAME}+for+digital+products!")],
        [InlineKeyboardButton("📞 Claim Reward", url=f"https://t.me/{ADMIN_TG.replace('@','')}"),
         InlineKeyboardButton("🏠 Home", callback_data="home")],
    ]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ══════════════════════════════════════════════
#   INLINE MODE — @BotUsername search products
# ══════════════════════════════════════════════
from telegram import InlineQueryResultArticle, InputTextMessageContent
import uuid as _uuid

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.inline_query.query.strip().lower()
    all_products = get_products(active_only=True)

    if query_text:
        matches = [p for p in all_products if query_text in p["name"].lower() or query_text in p["desc"].lower()]
    else:
        matches = all_products[:8]

    results = []
    for p in matches[:10]:
        recv_name, recv_num = get_mpesa_settings()
        desc_text = (
            f"{p['icon']} {p['name']}\n"
            f"💰 {p['price']} | 📁 {p['type']}\n\n"
            f"{p['desc']}\n\n"
            f"To buy:\n📱 M-Pesa Send Money to {recv_num} ({recv_name})\n"
            f"Then open @{(await context.bot.get_me()).username} and confirm payment."
        )
        results.append(
            InlineQueryResultArticle(
                id=str(_uuid.uuid4()),
                title=f"{p['icon']} {p['name']} — {p['price']}",
                description=p["desc"][:80],
                input_message_content=InputTextMessageContent(
                    message_text=desc_text,
                    parse_mode=None
                )
            )
        )

    await update.inline_query.answer(results, cache_time=30)

# ══════════════════════════════════════════════
#   Handle /start with referral param
# ══════════════════════════════════════════════
async def start_with_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    user_states.pop(user.id, None)

    # Check for referral
    if context.args and context.args[0].startswith("ref_"):
        ref_id = context.args[0].replace("ref_", "")
        try:
            ref_id_int = int(ref_id)
            if ref_id_int != user.id:
                try:
                    await context.bot.send_message(
                        chat_id=ref_id_int,
                        text=f"🎉 *{user.first_name}* just joined via your referral link!\n\nContact admin to claim your reward 👇",
                        parse_mode="Markdown"
                    )
                except:
                    pass
        except:
            pass

    group_link = get_group_link()
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu")],
        [InlineKeyboardButton("🔗 Links",       callback_data="links"),
         InlineKeyboardButton("ℹ About",        callback_data="about")],
        [InlineKeyboardButton("📞 Contact",     callback_data="contact"),
         InlineKeyboardButton("⭐ Rate Us",      callback_data="bot_rate")],
        [InlineKeyboardButton("💬 Group Chat",  url=group_link if group_link else "https://t.me/")],
        [me_button()],
    ]
    await send_cyber_footer(update, context, WELCOME_MSG, keyboard)

# ══════════════════════════════════════════════
#   ⭐ RATING — PRODUCT
# ══════════════════════════════════════════════
async def send_product_rating_request(context, user_id: int, username: str, full_name: str, product: dict):
    """Send a rating request to a user after purchase."""
    banner = get_banner_url()
    text = (
        f"⭐ *Rate Your Purchase*\n\n"
        f"Thanks for purchasing *{product['name']}*, {full_name.split()[0]}! 🎉\n\n"
        f"How would you rate this product?\n\n"
        f"Tap a star to rate 👇"
    )
    buttons = [
        [
            InlineKeyboardButton("⭐", callback_data=f"prate_{product['id']}_1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"prate_{product['id']}_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"prate_{product['id']}_3"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"prate_{product['id']}_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"prate_{product['id']}_5"),
        ],
        [InlineKeyboardButton("⏭ Skip", callback_data="home")],
    ]
    try:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=banner,
            caption=f"{text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Rating request send error: {e}")

async def show_bot_rating(query, context):
    """Show bot/market rating prompt."""
    banner = get_banner_url()
    text = (
        f"⭐ *Rate {BOT_NAME} | {COMPANY}*\n\n"
        f"We value your feedback! How would you rate your overall experience?\n\n"
        f"Tap a star to rate 👇"
    )
    buttons = [
        [
            InlineKeyboardButton("⭐", callback_data="brate_1"),
            InlineKeyboardButton("⭐⭐", callback_data="brate_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data="brate_3"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="brate_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="brate_5"),
        ],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ]
    await send_cyber_footer(query, context, text, buttons)

async def handle_product_rating_star(query, context, prod_id: str, stars: int):
    """User tapped a star for a product rating — ask for written review."""
    user = query.from_user
    pending_ratings[user.id] = {"product_id": prod_id, "rating": stars}
    set_user_state(user.id, AWAIT_PRODUCT_RATING, f"{prod_id}|{stars}")
    prod = get_product(prod_id)
    pname = prod["name"] if prod else prod_id
    star_str = "⭐" * stars
    text = (
        f"{star_str} *{stars}/5 — Nice!*\n\n"
        f"Now write a short review for *{pname}*:\n\n"
        f"_(or type 'skip' to skip the review)_"
    )
    buttons = [[InlineKeyboardButton("⏭ Skip Review", callback_data=f"prate_skip_{prod_id}_{stars}")]]
    await send_cyber_footer(query, context, text, buttons)

async def handle_bot_rating_star(query, context, stars: int):
    """User tapped a star for bot rating — ask for written review."""
    user = query.from_user
    pending_bot_ratings[user.id] = {"rating": stars}
    set_user_state(user.id, AWAIT_BOT_RATING, str(stars))
    star_str = "⭐" * stars
    text = (
        f"{star_str} *{stars}/5 — Thank you!*\n\n"
        f"Write a short review about *{BOT_NAME}* or your experience:\n\n"
        f"_(or type 'skip' to skip)_"
    )
    buttons = [[InlineKeyboardButton("⏭ Skip Review", callback_data=f"brate_skip_{stars}")]]
    await send_cyber_footer(query, context, text, buttons)

async def save_and_broadcast_product_review(context, user, prod_id: str, stars: int, review: str):
    """Save product review and broadcast to admin + group."""
    prod = get_product(prod_id)
    pname = prod["name"] if prod else prod_id
    star_str = "⭐" * stars

    conn = get_db()
    conn.execute(
        "INSERT INTO ratings (user_id,username,full_name,product_id,product_name,rating,review,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (user.id, user.username or "", user.full_name, prod_id, pname, stars, review, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    banner = get_banner_url()
    group_link = get_group_link()

    admin_text = (
        f"⭐ *New Product Review!*\n\n"
        f"👤 {user.full_name} (@{user.username or 'N/A'})\n"
        f"📦 Product: *{pname}*\n"
        f"Rating: {star_str} ({stars}/5)\n\n"
        f"💬 Review: _{review}_"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
    except:
        pass

    # Send to group chat as forwarded review
    if group_link and "t.me/" in group_link:
        group_username = group_link.split("t.me/")[-1].strip("/")
        group_msg = (
            f"⭐ *New Review by {user.full_name}*\n\n"
            f"📦 *{pname}*\n"
            f"Rating: {star_str} ({stars}/5)\n\n"
        )
        try:
            await context.bot.send_photo(
                chat_id=f"@{group_username}",
                photo=banner,
                caption=(
                    f"{group_msg}"
                    f"💬 _{review}_\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"{ME_BIO}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Group review post failed: {e}")

async def save_and_broadcast_bot_review(context, user, stars: int, review: str):
    """Save bot review and broadcast to admin panel + group."""
    star_str = "⭐" * stars

    conn = get_db()
    conn.execute(
        "INSERT INTO bot_ratings (user_id,username,full_name,rating,review,created_at) VALUES (?,?,?,?,?,?)",
        (user.id, user.username or "", user.full_name, stars, review, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    banner = get_banner_url()
    group_link = get_group_link()

    admin_text = (
        f"⭐ *New Bot Review!*\n\n"
        f"👤 {user.full_name} (@{user.username or 'N/A'})\n"
        f"Rating: {star_str} ({stars}/5)\n\n"
        f"💬 Review: _{review}_"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
    except:
        pass

    if group_link and "t.me/" in group_link:
        group_username = group_link.split("t.me/")[-1].strip("/")
        group_msg = (
            f"⭐ *{user.full_name} just rated {BOT_NAME}!*\n\n"
            f"Rating: {star_str} ({stars}/5)\n\n"
        )
        try:
            await context.bot.send_photo(
                chat_id=f"@{group_username}",
                photo=banner,
                caption=(
                    f"{group_msg}"
                    f"💬 _{review}_\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"{ME_BIO}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Group bot review post failed: {e}")

# ══════════════════════════════════════════════
#   📅 SCHEDULED JOBS — Holiday & Daily Quotes
# ══════════════════════════════════════════════
async def daily_quote_job(context: ContextTypes.DEFAULT_TYPE):
    """Send daily quote to all users every morning."""
    import random
    today = date.today()
    holiday_key = (today.month, today.day)
    holiday_name = HOLIDAYS.get(holiday_key)

    all_users = get_all_users()
    if not all_users:
        return

    banner = get_banner_url()

    if holiday_name:
        # It's a holiday — send special broadcast with 25% offer
        quote = HOLIDAY_QUOTES.get(holiday_name, f"🎉 Happy {holiday_name}! From *Skyline Technologies*.")
        products = get_products(active_only=True)

        offer_lines = ""
        for p in products[:5]:
            orig = p.get("original_price") or p.get("price_value", 0)
            if orig > 0:
                drop = orig * 0.75
                offer_lines += f"• {p['icon']} *{p['name']}* — ~~KSh {orig:,.0f}~~ → *KSh {drop:,.0f}* 🎉\n"

        msg = (
            f"🎊 *Happy {holiday_name}!* 🎊\n\n"
            f"{quote}\n\n"
            f"{'━━━━━━━━━━━━━━━━' if offer_lines else ''}\n"
            f"{'🎁 *Holiday Special Offers (25% OFF):*' if offer_lines else ''}\n"
            f"{offer_lines}\n"
            f"{'Use /start to shop now! 🛍' if offer_lines else ''}\n\n"
            f"_— {COMPANY}_"
        )
        for u in all_users:
            try:
                await context.bot.send_photo(
                    chat_id=u[0],
                    photo=banner,
                    caption=f"{msg}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                    parse_mode="Markdown"
                )
            except:
                pass
    else:
        # Regular day — send daily quote
        import random
        quote = random.choice(DAILY_QUOTES)
        msg = f"{quote}\n\n_— {COMPANY}_"
        for u in all_users:
            try:
                await context.bot.send_message(
                    chat_id=u[0],
                    text=msg,
                    parse_mode="Markdown"
                )
            except:
                pass

# ══════════════════════════════════════════════
#   📢 NEW PRODUCT NOTIFICATION (called from admin actions)
# ══════════════════════════════════════════════
async def notify_new_product(context, product: dict):
    """Broadcast new product arrival to all users."""
    banner = product.get("image_url") or get_banner_url()
    all_users = get_all_users()
    msg = (
        f"🆕🎉 *New Product Alert!*\n\n"
        f"{product['icon']} *{product['name']}*\n"
        f"💰 Price: *{product['price']}*\n"
        f"📁 Type: {product['type']}\n\n"
        f"_{product['desc']}_\n\n"
        f"👉 Use /start → Shop to order now!"
    )
    for u in all_users:
        try:
            await context.bot.send_photo(
                chat_id=u[0],
                photo=banner,
                caption=f"{msg}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                parse_mode="Markdown"
            )
        except:
            pass

async def notify_price_drop(context, product: dict, orig_price: float, new_price: float):
    """Broadcast price drop to all users."""
    banner = product.get("image_url") or get_banner_url()
    all_users = get_all_users()
    drop_pct = round(((orig_price - new_price) / orig_price) * 100) if orig_price > 0 else 0
    msg = (
        f"🎊💥 *Price Drop Alert!* 🎊💥\n\n"
        f"{product['icon']} *{product['name']}*\n"
        f"💰 Was: ~~KSh {orig_price:,.0f}~~\n"
        f"🔥 Now: *KSh {new_price:,.0f}*\n"
        f"📉 You save *{drop_pct}%!*\n\n"
        f"👉 Use /start → Shop to grab this deal!"
    )
    for u in all_users:
        try:
            await context.bot.send_photo(
                chat_id=u[0],
                photo=banner,
                caption=f"{msg}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                parse_mode="Markdown"
            )
        except:
            pass


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Schedule daily quote job at 8:00 AM
    job_queue = app.job_queue
    if job_queue:
        import datetime as dt
        job_queue.run_daily(
            daily_quote_job,
            time=dt.time(hour=8, minute=0, tzinfo=None),
        )

    # User commands
    app.add_handler(CommandHandler("start",     start_with_ref))  # handles /start and /start ref_xxx
    app.add_handler(CommandHandler("myorders",  my_orders))
    app.add_handler(CommandHandler("referral",  my_referral))

    # Admin commands
    app.add_handler(CommandHandler("admin",          admin_panel))
    app.add_handler(CommandHandler("stats",          admin_stats))
    app.add_handler(CommandHandler("listproducts",   admin_list_products))
    app.add_handler(CommandHandler("editlink",       admin_edit_link))
    app.add_handler(CommandHandler("toggleproduct",  admin_toggle_product))
    app.add_handler(CommandHandler("addproduct",     admin_add_product))
    app.add_handler(CommandHandler("newproduct",     admin_new_product))
    app.add_handler(CommandHandler("addcategory",    admin_add_category))
    app.add_handler(CommandHandler("listcategories", admin_list_categories))
    app.add_handler(CommandHandler("users",          admin_list_users))
    app.add_handler(CommandHandler("msg",            admin_message_user))
    app.add_handler(CommandHandler("broadcast",      admin_broadcast))
    app.add_handler(CommandHandler("orders",         admin_orders))

    # Inline mode
    from telegram.ext import InlineQueryHandler
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # Callback & messages
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info(f"🚀 {BOT_NAME} bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
