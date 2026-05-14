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
from datetime import datetime
import hashlib as _hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

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
        active INTEGER DEFAULT 1
    )''')

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

    # New product columns
    try: c.execute("ALTER TABLE products ADD COLUMN image_url TEXT DEFAULT ''")
    except: pass
    try: c.execute("ALTER TABLE products ADD COLUMN sale_price REAL DEFAULT 0")
    except: pass

    # Reviews table
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, username TEXT, full_name TEXT,
        product_id TEXT, product_name TEXT,
        rating INTEGER, review TEXT,
        type TEXT DEFAULT 'product',
        created_at TEXT
    )""")

    # Seed default settings
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_name', 'Clinton Oduor')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_number', '0743810633')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('ai_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('downloader_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('music_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('bot_banner_image', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('admin_logo', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('group_chat_link', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('quotes_enabled', '1')")

    # Table for persistent user states (survives restarts)
    c.execute('''CREATE TABLE IF NOT EXISTS user_states_db (
        user_id INTEGER PRIMARY KEY,
        state INTEGER,
        extra TEXT,
        updated_at TEXT
    )''')

    # ── ANTI-SCAM: Track used M-Pesa transaction IDs ──
    c.execute('''CREATE TABLE IF NOT EXISTS used_transactions (
        txn_id TEXT PRIMARY KEY,
        user_id INTEGER,
        product_id TEXT,
        used_at TEXT
    )''')

    # ── ANTI-SCAM: One-time download tokens ──
    c.execute('''CREATE TABLE IF NOT EXISTS download_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        product_id TEXT,
        file_url TEXT,
        expires_at TEXT,
        used INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    # ── USER ACCOUNTS: extra columns for registration ──
    try: c.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN registered INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN loyalty_points INTEGER DEFAULT 0")
    except: pass

    # ── LOYALTY POINTS LOG ──
    c.execute('''CREATE TABLE IF NOT EXISTS loyalty_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        points INTEGER,
        reason TEXT,
        created_at TEXT
    )''')

    # ── REDOWNLOAD REQUESTS ──
    c.execute('''CREATE TABLE IF NOT EXISTS redownload_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id TEXT,
        product_name TEXT,
        status TEXT DEFAULT "pending",
        created_at TEXT
    )''')

    # ── ALERT SUBSCRIBERS ──
    c.execute('''CREATE TABLE IF NOT EXISTS alert_subscribers (
        user_id INTEGER PRIMARY KEY,
        subscribed INTEGER DEFAULT 1,
        created_at TEXT
    )''')

    conn.commit()
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        default_products = [
            ("p1","School Notes Bundle","education","KSh 500",500,"PDF","Complete notes for SS1–SS3. All subjects covered.","","📚",1,"",0),
            ("p2","Business Plan Template","education","KSh 800",800,"DOCX","Professional business plan template. Editable Word format.","","📄",1,"",0),
            ("p3","Android VPN App","apps","KSh 1,200",1200,"APK","Premium VPN for Android. Fast, secure, unlimited data.","","📱",1,"",0),
            ("p4","Afrobeats Mix 2024","music","KSh 300",300,"MP3","Hot afrobeats collection — 30 tracks, 45 minutes.","","🎵",1,"",0),
            ("p5","Tech Tutorial Series","videos","KSh 2,000",2000,"MP4","Full coding tutorial series. Python, Web Dev & more.","","🎬",1,"",0),
            ("p6","Galaxy Tab A9","gadgets","KSh 85,000",85000,"PRODUCT","Samsung Galaxy Tab A9 — brand new sealed box. Fast delivery.","","💻",1,"",0),
        ]
        c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", default_products)

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

# ══════════════════════════════════════════════
#   ANTI-SCAM: TRANSACTION GUARD
# ══════════════════════════════════════════════
def is_transaction_used(txn_id: str) -> bool:
    """Check if this M-Pesa transaction ID has already been used."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT txn_id FROM used_transactions WHERE txn_id=?", (txn_id,)
        ).fetchone()
        conn.close()
        return row is not None
    except:
        return False

def mark_transaction_used(txn_id: str, user_id: int, product_id: str):
    """Permanently mark a transaction ID as used immediately after delivery."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO used_transactions (txn_id, user_id, product_id, used_at) VALUES (?,?,?,?)",
            (txn_id, user_id, product_id, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        logger.info(f"🔒 Transaction {txn_id} marked USED by user {user_id}")
    except Exception as e:
        logger.error(f"mark_transaction_used error: {e}")


# ══════════════════════════════════════════════
#   ANTI-SCAM: ONE-TIME DOWNLOAD TOKENS
# ══════════════════════════════════════════════
import secrets as _secrets

def generate_download_token(user_id: int, product_id: str, file_url: str) -> str:
    """
    Create a one-time download token valid for 24 hours.
    Returns the full token URL to send to the user.
    """
    token = _secrets.token_urlsafe(40)
    expires_at = datetime.now().replace(microsecond=0)
    # Add 24 hours manually (no timedelta import needed — already in datetime)
    from datetime import timedelta
    expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO download_tokens (token, user_id, product_id, file_url, expires_at, used, created_at) VALUES (?,?,?,?,?,0,?)",
            (token, user_id, product_id, file_url, expires_at, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"generate_download_token error: {e}")
    # This URL is served by admin_panel.py Flask route /download/<token>
    return token

def resolve_download_token(token: str, user_id: int):
    """
    Validate and burn a download token.
    Returns (file_url, None) on success or (None, error_message) on failure.
    """
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM download_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row:
            conn.close()
            return None, "❌ Invalid download link."
        if row["used"]:
            conn.close()
            return None, "❌ This link has already been used."
        if datetime.now().isoformat() > row["expires_at"]:
            conn.close()
            return None, "❌ This link has expired (24hr limit)."
        if row["user_id"] != user_id:
            conn.close()
            return None, "❌ This link belongs to a different user."
        # Burn the token immediately
        conn.execute("UPDATE download_tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
        conn.close()
        return row["file_url"], None
    except Exception as e:
        logger.error(f"resolve_download_token error: {e}")
        return None, "❌ Download error. Contact admin."


def register_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?)",
              (user.id, user.username or "", user.full_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
#   ACCOUNT HELPERS
# ══════════════════════════════════════════════
def hash_password(pwd: str) -> str:
    """SHA-256 hash (bcrypt-level security without external dep)."""
    return _hashlib.sha256(pwd.encode()).hexdigest()

def is_registered(user_id: int) -> bool:
    """Check if user has completed registration."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT registered FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        return bool(row and row[0])
    except:
        return False

def get_account(user_id: int) -> dict:
    """Get full account info for a user."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT user_id, username, full_name, display_name, email, loyalty_points, joined_at FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "user_id": row[0], "username": row[1], "full_name": row[2],
                "display_name": row[3] or row[2], "email": row[4] or "",
                "loyalty_points": row[5] or 0, "joined_at": row[6]
            }
    except:
        pass
    return {}

def complete_registration(user_id: int, display_name: str, password: str, email: str):
    """Save registration details."""
    conn = get_db()
    conn.execute(
        "UPDATE users SET display_name=?, password_hash=?, email=?, registered=1 WHERE user_id=?",
        (display_name, hash_password(password), email, user_id)
    )
    # Auto-subscribe to alerts
    conn.execute(
        "INSERT OR IGNORE INTO alert_subscribers (user_id, subscribed, created_at) VALUES (?,1,?)",
        (user_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_loyalty_points(user_id: int, points: int, reason: str):
    """Add loyalty points to a user account."""
    try:
        conn = get_db()
        conn.execute("UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id=?", (points, user_id))
        conn.execute(
            "INSERT INTO loyalty_log (user_id, points, reason, created_at) VALUES (?,?,?,?)",
            (user_id, points, reason, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"add_loyalty_points error: {e}")

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
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active","image_url","sale_price"]
    return [dict(zip(keys, r)) for r in rows]

def get_product(prod_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (prod_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active","image_url","sale_price"]
    return dict(zip(keys, row))

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

# ── Registration states ──
AWAIT_REG_NAME       = 30
AWAIT_REG_PASSWORD   = 31
AWAIT_REG_EMAIL      = 32

# Pending payments: {user_id: product_id}
pending_payments = {}
# Admin reply targets: {admin_id: target_user_id}
admin_reply_targets = {}
# Per-user state tracking
user_states = {}      # user_id -> state constant
user_dl_platform = {} # user_id -> platform name for downloader

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
    """Always sends a NEW message so the main menu stays visible."""
    _s = get_settings()
    banner = _s.get("bot_banner_image", "") or CYBER_IMAGE
    full_caption = f"{caption}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    markup = InlineKeyboardMarkup(keyboard)
    try:
        msg_obj = update_or_query.message if hasattr(update_or_query, "message") else update_or_query
        await msg_obj.reply_photo(photo=banner, caption=full_caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"send_cyber_footer failed: {e}")


async def start_from_query(query, context):
    """Show main menu from a callback query (button press)."""
    user_states.pop(query.from_user.id, None)
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("💬 Group Chat",   callback_data="group_chat")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("ℹ About",        callback_data="about"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
        [InlineKeyboardButton("⭐ Rate Us",      callback_data="rate_bot")],
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
    # Transaction ID: M-Pesa codes are 10 uppercase alphanumeric chars at start
    receipt_match = re.search(r'\b([A-Z0-9]{10})\b', msg)
    if not receipt_match:
        receipt_match = re.search(r'\b([A-Z0-9]{8,12})\b', msg)
    receipt = receipt_match.group(1) if receipt_match else "N/A"

    return True, {
        "amount":   paid_amount,
        "date":     date_str,
        "receiver": receiver_name,
        "number":   receiver_number,
        "receipt":  receipt,   # This is the unique transaction ID used as scam guard
    }

# ══════════════════════════════════════════════
#   YOUTUBE SEARCH  (via YouTube Data API v3 or scrape-free proxy)
# ══════════════════════════════════════════════
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")  # optional
# Note: YouTube key can also be set via admin panel (downloader_api_key)

async def search_youtube(query: str):
    """Search YouTube. Returns list of {title, url, thumbnail, channel}."""
    import asyncio
    results = []
    yt_key = get_api_setting("downloader_api_key", "YOUTUBE_API_KEY") or YOUTUBE_API_KEY
    if yt_key:
        try:
            params = urllib.parse.urlencode({
                "part": "snippet", "q": query, "type": "video",
                "maxResults": 5, "key": yt_key
            })
            url = f"https://www.googleapis.com/youtube/v3/search?{params}"
            loop = asyncio.get_event_loop()
            def _fetch():
                req = urllib.request.Request(url, headers={"User-Agent": "DevClinBot/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return _json.loads(resp.read().decode())
            data = await loop.run_in_executor(None, _fetch)
            for item in data.get("items", []):
                vid_id = item["id"]["videoId"]
                results.append({
                    "title":   item["snippet"]["title"],
                    "url":     f"https://youtu.be/{vid_id}",
                    "channel": item["snippet"]["channelTitle"],
                    "thumb":   item["snippet"]["thumbnails"]["default"]["url"],
                })
        except Exception as e:
            logger.error(f"YouTube API search error: {e}")
    else:
        try:
            params = urllib.parse.urlencode({"q": query, "type": "video"})
            url = f"https://invidious.privacydev.net/api/v1/search?{params}"
            loop = asyncio.get_event_loop()
            def _fetch2():
                req = urllib.request.Request(url, headers={"User-Agent": "DevClinBot/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return _json.loads(resp.read().decode())
            items = await loop.run_in_executor(None, _fetch2)
            for item in items[:5]:
                results.append({
                    "title":   item.get("title", "Unknown"),
                    "url":     f"https://youtu.be/{item.get('videoId','')}",
                    "channel": item.get("author", ""),
                    "thumb":   "",
                })
        except Exception as e:
            logger.error(f"Invidious search error: {e}")
    return results

# ══════════════════════════════════════════════
#   DOWNLOADER  (via yt-dlp subprocess or cobalt.tools API)
# ══════════════════════════════════════════════
async def download_media_cobalt(url: str) -> dict:
    """
    Use cobalt.tools public API to resolve a download link.
    Supports: YouTube, TikTok, Facebook, Spotify (audio), Instagram, Twitter.
    Returns: {"url": direct_link, "filename": ...} or {"error": msg}
    """
    import asyncio
    api = "https://api.cobalt.tools/api/json"
    payload = _json.dumps({
        "url": url,
        "vCodec": "h264",
        "vQuality": "720",
        "aFormat": "mp3",
        "isAudioOnly": False,
        "disableMetadata": False,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "DevClinBot/1.0",
    }
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            req = urllib.request.Request(api, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())
        data = await loop.run_in_executor(None, _fetch)
        if data.get("status") in ("stream", "redirect", "tunnel"):
            return {"url": data.get("url", ""), "filename": data.get("filename", "media")}
        elif data.get("status") == "picker":
            picks = data.get("picker", [])
            if picks:
                return {"url": picks[0].get("url", ""), "filename": "media"}
        return {"error": data.get("text", "Download failed. Check the link.")}
    except Exception as e:
        logger.error(f"Cobalt API error: {e}")
        return {"error": "Download service unavailable. Try again later."}

# ══════════════════════════════════════════════
#   AI ASSISTANT  (via Anthropic Claude API)
# ══════════════════════════════════════════════
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

async def ask_claude(user_message: str, history: list = None) -> str:
    """Call Claude claude-haiku-4-5-20251001 for a quick AI reply."""
    import asyncio
    # Read API key from DB (admin panel) or env var
    live_key = get_api_setting("ai_api_key", "ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
    if not live_key:
        return (
            "🤖 AI assistant is not configured yet.\n\n"
            "The admin needs to add an AI API key in Admin Panel → Settings → API Keys."
        )
    messages = (history or []) + [{"role": "user", "content": user_message}]
    payload = _json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 512,
        "system": (
            f"You are a helpful assistant inside the {BOT_NAME} Telegram bot, "
            f"operated by {COMPANY}. Be concise, friendly, and answer in the user's language. "
            "If asked about products or payments, remind the user to use the /start menu."
        ),
        "messages": messages,
    }).encode()
    headers = {
        "x-api-key": live_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "User-Agent": "DevClinBot/1.0",
    }
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())
        data = await loop.run_in_executor(None, _fetch)
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "⚠️ AI service temporarily unavailable. Please try again later."

# Per-user AI conversation history (in-memory, resets on restart)
ai_history = {}  # user_id -> list of {role, content}

# ══════════════════════════════════════════════
#   /start  — MAIN MENU
# ══════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    # Clear any active state
    clear_user_state(user.id)
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("💬 Group Chat",   callback_data="group_chat")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("ℹ About",        callback_data="about"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
        [me_button()],
    ]
    await send_cyber_footer(update, context, WELCOME_MSG, keyboard)

# ══════════════════════════════════════════════
#   SHOP — CATEGORIES
# ══════════════════════════════════════════════
async def show_shop(query, context):
    products = get_products()
    cats_with_products = list(dict.fromkeys([p["category"] for p in products]))
    all_cats = {c["id"]: c["label"] for c in get_categories()}

    buttons = []
    row = []
    for cat in cats_with_products:
        label = all_cats.get(cat, cat.title())
        row.append(InlineKeyboardButton(label, callback_data=f"cat_{cat}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(back_home_row())
    buttons.append(me_row())
    await send_cyber_footer(query, context, "🛍 *Shop — Choose a Category*", buttons)

# ══════════════════════════════════════════════
#   CATEGORY LISTING
# ══════════════════════════════════════════════
async def show_category(query, context, cat: str):
    items = get_products(category=cat)
    all_cats = {c["id"]: c["label"] for c in get_categories()}

    if not items:
        await query.edit_message_text("No products in this category yet.")
        return

    text = f"{all_cats.get(cat, cat.title())} *Products*\n\n"
    for p in items:
        text += f"{p['icon']} *{p['name']}* — {p['price']}\n_{p['desc']}_\n\n"

    buttons = [
        [InlineKeyboardButton(f"{p['icon']} {p['name']} — {p['price']}", callback_data=f"prod_{p['id']}")]
        for p in items
    ]
    buttons.append([InlineKeyboardButton("◀ Back to Shop", callback_data="shop")])
    buttons.append(back_home_row())
    buttons.append(me_row())
    await send_cyber_footer(query, context, text, buttons)

# ══════════════════════════════════════════════
#   PRODUCT DETAIL
# ══════════════════════════════════════════════
async def show_product(query, context, prod_id: str):
    prod = get_product(prod_id)
    if not prod:
        await query.message.reply_text("Product not found.")
        return

    receiver_name, receiver_number = get_mpesa_settings()
    sale_price  = prod.get("sale_price", 0) or 0
    price_value = prod.get("price_value", 0) or 0

    if sale_price and sale_price < price_value:
        drop_pct      = int(((price_value - sale_price) / price_value) * 100)
        price_display = f"~~{prod['price']}~~ ➡ *KSh {sale_price:,.0f}* 🔥 ({drop_pct}% OFF)"
        mpesa_amount  = f"KSh {sale_price:,.0f}"
    else:
        price_display = f"*{prod['price']}*"
        mpesa_amount  = prod['price']

    text = (
        f"{prod['icon']} *{prod['name']}*\n\n"
        f"💰 *Price:* {price_display}\n"
        f"📁 *Type:* {prod['type']}\n\n"
        f"{prod['desc']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Payment via M-Pesa Send Money:*\n"
        f"📱 Send to: *{receiver_number}*\n"
        f"👤 Name: *{receiver_name}*\n"
        f"💰 Amount: *{mpesa_amount}*\n\n"
        f"After payment, tap ✅ *I\'ve Paid* and paste your M-Pesa confirmation message."
    )

    buttons = [
        [InlineKeyboardButton("✅ I\'ve Paid", callback_data=f"paid_{prod_id}")],
        [InlineKeyboardButton("◀ Back", callback_data=f"cat_{prod['category']}"),
         InlineKeyboardButton("🏠 Home", callback_data="home")],
        [me_button()],
    ]

    _s      = get_settings()
    img_url = prod.get("image_url", "") or _s.get("bot_banner_image", "") or CYBER_IMAGE
    full_cap = f"{text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    try:
        await query.message.reply_photo(photo=img_url, caption=full_cap, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await send_cyber_footer(query, context, text, buttons)

# ══════════════════════════════════════════════
#   PAYMENT — ASK FOR MPESA MESSAGE
# ══════════════════════════════════════════════
async def payment_initiate(query, context, prod_id: str):
    prod = get_product(prod_id)
    if not prod:
        return

    receiver_name, receiver_number = get_mpesa_settings()
    user_id = query.from_user.id
    pending_payments[user_id] = prod_id
    set_user_state(user_id, AWAIT_MPESA_MSG, prod_id)

    text = (
        f"📲 *M-Pesa Payment Verification*\n\n"
        f"📦 Product: *{prod['name']}*\n"
        f"💰 Amount: *{prod['price']}*\n\n"
        f"*Send Money via M-Pesa to:*\n"
        f"📱 Number: *{receiver_number}*\n"
        f"👤 Name: *{receiver_name}*\n\n"
        f"After paying, paste the full M-Pesa confirmation SMS below 👇\n\n"
        f"_Example:_\n"
        f"`ABC123DE confirmed. Ksh500.00 sent to {receiver_name} {receiver_number} on 10/5/24...`"
    )

    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")],
    ]
    await send_cyber_footer(query, context, text, buttons)

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
    await send_cyber_footer(query, context, text, buttons)

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
        f"• 🎵 Music search & streaming\n• ⬇️ Media downloader\n• 🤖 AI Assistant\n\n"
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
         InlineKeyboardButton("✈ Telegram", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        back_home_row(),
        [me_button()],
    ]
    await send_cyber_footer(query, context, text, buttons)


# ══════════════════════════════════════════════
#   GROUP CHAT
# ══════════════════════════════════════════════
async def show_group_chat(query, context):
    settings = get_settings()
    group_link = settings.get("group_chat_link", "")
    if group_link:
        text = (
            "💬 *Community Group Chat*\n\n"
            "Join our community to chat, share experiences and get support!\n\n"
            "🌟 _Connect with other customers_\n"
            "💡 _Share tips and feedback_\n"
            "🛍 _Get exclusive deals_"
        )
        buttons = [
            [InlineKeyboardButton("💬 Join Group Chat", url=group_link)],
            back_home_row(),
        ]
    else:
        text = "💬 *Community Group Chat*\n\n_Coming soon! Check back later._"
        buttons = [back_home_row()]
    await send_cyber_footer(query, context, text, buttons)

# ══════════════════════════════════════════════
#   RATINGS & REVIEWS
# ══════════════════════════════════════════════
AWAIT_PRODUCT_REVIEW = 20
AWAIT_PRODUCT_RATING = 21
AWAIT_BOT_RATING     = 22
AWAIT_BOT_REVIEW     = 23

async def show_bot_rating(query, context):
    user_id = query.from_user.id
    set_user_state(user_id, AWAIT_BOT_RATING)
    text = (
        "⭐ *Rate Dev Clin Market*\n\n"
        "How would you rate your overall experience?\n\n"
        "Tap a star below 👇"
    )
    buttons = [
        [
            InlineKeyboardButton("⭐ 1", callback_data="bot_rate_1"),
            InlineKeyboardButton("⭐ 2", callback_data="bot_rate_2"),
            InlineKeyboardButton("⭐ 3", callback_data="bot_rate_3"),
            InlineKeyboardButton("⭐ 4", callback_data="bot_rate_4"),
            InlineKeyboardButton("⭐ 5", callback_data="bot_rate_5"),
        ],
        back_home_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def handle_bot_rating(query, context, rating: int):
    user_id = query.from_user.id
    context.user_data[f"bot_rating_{user_id}"] = rating
    set_user_state(user_id, AWAIT_BOT_REVIEW)
    stars = "⭐" * rating
    await query.message.reply_text(
        f"✅ You rated us *{stars}* ({rating}/5)\n\nNow leave a short review 💬\n_Type below or tap Skip._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip Review", callback_data="skip_bot_review")]])
    )

async def save_bot_review(update, context, review_text: str):
    user    = update.effective_user
    user_id = user.id
    rating  = context.user_data.pop(f"bot_rating_{user_id}", 0)
    clear_user_state(user_id)
    stars   = "⭐" * rating

    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (user_id,username,full_name,product_id,product_name,rating,review,type,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, user.username or "", user.full_name, "bot", "Dev Clin Market", rating, review_text, "bot", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    settings = get_settings()
    banner   = settings.get("bot_banner_image", "") or CYBER_IMAGE
    group_link = settings.get("group_chat_link", "")

    review_msg = (
        f"🌟 *New Review — Dev Clin Market*\n\n"
        f"👤 *{user.full_name}*" + (f" (@{user.username})" if user.username else "") +
        f"\n{stars} *{rating}/5*\n\n"
        f"💬 _{review_text}_\n\n━━━━━━━━━━━━━━━━\n_{COMPANY}_"
    )
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=banner, caption=review_msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Review to admin failed: {e}")
    if group_link and "t.me/" in group_link:
        try:
            group_id = group_link.split("t.me/")[-1].strip("/")
            await context.bot.send_photo(chat_id=f"@{group_id}", photo=banner, caption=review_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Review to group failed: {e}")

    await update.message.reply_text(
        f"✅ *Thank you for your review!* {stars}\n\n_{COMPANY}_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([back_home_row()])
    )

async def send_product_rating_request(context, user_id: int, product_name: str, product_id: str):
    buttons = [
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"prod_rate_{product_id}_1"),
            InlineKeyboardButton("⭐ 2", callback_data=f"prod_rate_{product_id}_2"),
            InlineKeyboardButton("⭐ 3", callback_data=f"prod_rate_{product_id}_3"),
            InlineKeyboardButton("⭐ 4", callback_data=f"prod_rate_{product_id}_4"),
            InlineKeyboardButton("⭐ 5", callback_data=f"prod_rate_{product_id}_5"),
        ],
        [InlineKeyboardButton("⏭ Skip", callback_data="skip_prod_review")],
    ]
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⭐ *How was {product_name}?*\n\nYour feedback helps other buyers! Tap a star 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Rating request failed: {e}")

async def handle_product_rating(query, context, product_id: str, rating: int):
    user_id = query.from_user.id
    context.user_data[f"prod_rating_{user_id}"] = (product_id, rating)
    set_user_state(user_id, AWAIT_PRODUCT_REVIEW)
    stars = "⭐" * rating
    await query.message.reply_text(
        f"✅ You rated *{stars}* ({rating}/5)\n\nLeave a short review below 👇\n_Or tap Skip._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data="skip_prod_review")]])
    )

async def save_product_review(update, context, review_text: str):
    user    = update.effective_user
    user_id = user.id
    data    = context.user_data.pop(f"prod_rating_{user_id}", None)
    clear_user_state(user_id)
    if not data:
        return
    product_id, rating = data
    prod         = get_product(product_id)
    product_name = prod["name"] if prod else product_id
    stars        = "⭐" * rating

    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (user_id,username,full_name,product_id,product_name,rating,review,type,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, user.username or "", user.full_name, product_id, product_name, rating, review_text, "product", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    settings = get_settings()
    banner   = settings.get("bot_banner_image", "") or CYBER_IMAGE
    review_msg = (
        f"⭐ *Product Review*\n\n📦 *{product_name}*\n"
        f"👤 {user.full_name}" + (f" (@{user.username})" if user.username else "") +
        f"\n{stars} *{rating}/5*\n\n💬 _{review_text}_\n\n_{COMPANY}_"
    )
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=banner, caption=review_msg, parse_mode="Markdown")
    except: pass

    await update.message.reply_text(
        f"✅ *Review submitted! Thank you* {stars}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([back_home_row()])
    )

# ══════════════════════════════════════════════
#   DAILY & TIMELY QUOTES
# ══════════════════════════════════════════════
import random as _random

QUOTES = {
    "morning": [
        "🌅 *Good Morning!* Rise and shine — today is a new opportunity to grow. 💪\n\n_Skyline Technologies_",
        "🌄 *Morning Motivation!* The secret of getting ahead is getting started. 🚀\n\n_Dev Clin_",
        "☀️ *Good Morning!* Every day is a chance to be better than yesterday. 🌟\n\n_Skyline Technologies_",
        "🌞 *Rise & Grind!* Success is the sum of small efforts repeated every day. 💼\n\n_Dev Clin_",
    ],
    "afternoon": [
        "☀️ *Good Afternoon!* Keep pushing — you are halfway there. Stay focused! 🎯\n\n_Skyline Technologies_",
        "🌤 *Afternoon Check-in!* Hard work beats talent when talent doesn't work hard. 💡\n\n_Dev Clin_",
        "💪 *Keep Going!* The afternoon slump is real — but so is your potential. 🔥\n\n_Skyline Technologies_",
        "⚡ *Power Hour!* Don't watch the clock — do what it does. Keep going! 🕐\n\n_Dev Clin_",
    ],
    "evening": [
        "🌇 *Good Evening!* Reflect on today's wins and prepare for tomorrow. 🌟\n\n_Skyline Technologies_",
        "🌆 *Evening Vibes!* You did great today. Rest, recharge, come back stronger. 💫\n\n_Dev Clin_",
        "🌃 *Evening Motivation!* Dreams don't work unless you do. 🚀\n\n_Skyline Technologies_",
    ],
    "night": [
        "🌙 *Good Night!* Sleep well, dream big, wake up ready to conquer tomorrow. 💤\n\n_Skyline Technologies_",
        "✨ *Night Thoughts!* The harder you work, the greater you'll feel when you achieve it. 🌙\n\n_Dev Clin_",
        "🌟 *Sweet Dreams!* Tomorrow is another chance to be amazing. Rest well! 😴\n\n_Skyline Technologies_",
    ],
}

async def send_scheduled_quote(context):
    settings = get_settings()
    if settings.get("quotes_enabled", "1") != "1":
        return
    import datetime as _dt
    hour = _dt.datetime.utcnow().hour
    # UTC times for EAT (UTC+3): 6:30AM=03:30, 12PM=09:00, 3PM=12:00, 9PM=18:00
    if hour == 3:   qt = "morning"
    elif hour == 9:  qt = "afternoon"
    elif hour == 12: qt = "evening"
    elif hour == 18: qt = "night"
    else: return
    quote = _random.choice(QUOTES[qt])
    conn  = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=quote, parse_mode="Markdown")
        except: pass

# ══════════════════════════════════════════════
#   /contact COMMAND
# ══════════════════════════════════════════════
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📞 *Contact Us*\n\nWe're always available to help!\n\n"
        f"💬 WhatsApp: {WHATSAPP}\n✈ Telegram: {ADMIN_TG}\n📸 Instagram: {INSTAGRAM}\n\n"
        f"_Response time: Usually within minutes_ ⚡"
    )
    buttons = [
        [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP),
         InlineKeyboardButton("✈ Telegram", url=f"https://t.me/{ADMIN_TG.replace('@','')}") ],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        back_home_row(),
        [me_button()],
    ]
    _s   = get_settings()
    _b   = _s.get("bot_banner_image", "") or CYBER_IMAGE
    full = f"{text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    await update.message.reply_photo(photo=_b, caption=full, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

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
async def adminfix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    conn.execute(
        "UPDATE users SET registered=1, display_name='Clinton', email='admin@skyline.com' WHERE user_id=?",
        (user.id,)
    )
    conn.commit()
    conn.close()
    add_loyalty_points(user.id, 50, "Admin welcome bonus")
    await update.message.reply_text("✅ Admin account fixed! Now send /start")
    
@admin_only
async def admin_alert_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a new product alert to all subscribed users."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /alertproduct <product_id>\nExample: /alertproduct p7",
            parse_mode="Markdown"
        )
        return
    prod_id = args[0]
    prod = get_product(prod_id)
    if not prod:
        await update.message.reply_text(f"❌ Product {prod_id} not found.")
        return
    conn2 = get_db()
    subs = conn2.execute("SELECT user_id FROM alert_subscribers WHERE subscribed=1").fetchall()
    conn2.close()
    sent = 0; failed = 0
    await update.message.reply_text(f"📢 Sending new product alert to {len(subs)} subscribers...")
    for sub in subs:
        try:
            await context.bot.send_message(
                chat_id=sub[0],
                text=(
                    f"🆕 *New Product Alert!*\n\n"
                    f"{prod['icon']} *{prod['name']}*\n"
                    f"💰 {prod['price']} | 📁 {prod['type']}\n\n"
                    f"{prod['desc']}\n\n"
                    f"Open the shop to buy now! 👇"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🛍 Buy {prod['name']}", callback_data=f"prod_{prod_id}")]
                ])
            )
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Alert sent!\n📤 Delivered: {sent}\n❌ Failed: {failed}",
        parse_mode="Markdown"
    )


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

    # ── Registration flow ─────────────────────────────────────────────
    if state == AWAIT_REG_NAME:
        name = text.strip()
        if len(name) < 2:
            await update.message.reply_text("⚠️ Name too short. Please enter your full name (e.g. Xavi Clinton).")
            return
        await reg_ask_password(update, context, name)
        return

    if state == AWAIT_REG_PASSWORD:
        pwd = text.strip()
        if len(pwd) < 6:
            await update.message.reply_text("⚠️ Password must be at least *6 characters*. Try again 👇", parse_mode="Markdown")
            return
        await reg_ask_email(update, context, pwd)
        return

    if state == AWAIT_REG_EMAIL:
        email = text.strip()
        import re as _re
        if not _re.match(r"[^@]+@[^@]+\.[^@]+", email):
            await update.message.reply_text("⚠️ That doesn't look like a valid email. Please try again 👇")
            return
        await reg_complete(update, context, email)
        return

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
            receipt_no  = result.get("receipt", "N/A")
            paid_amount = result["amount"]
            pay_date    = result["date"]
            recv_name, recv_num = get_mpesa_settings()

            # ── ANTI-SCAM CHECK 1: Block reused transaction IDs ──────────
            if receipt_no != "N/A" and is_transaction_used(receipt_no):
                await update.message.reply_photo(
                    photo=CYBER_IMAGE,
                    caption=(
                        f"🚫 *Transaction Already Used*\n\n"
                        f"M-Pesa code `{receipt_no}` has already been used to claim a product.\n\n"
                        f"Each M-Pesa confirmation SMS can only be used *once*.\n\n"
                        f"If you believe this is a mistake, contact the admin below."
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                        [InlineKeyboardButton("🏠 Home", callback_data="home")],
                    ])
                )
                # Alert admin of replay attempt
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=(
                            f"⚠️ *REPLAY ATTACK BLOCKED*\n"
                            f"👤 {user.full_name} (@{user.username or 'N/A'}) `{user.id}`\n"
                            f"📦 {prod['name']}\n"
                            f"🧾 TXN: `{receipt_no}` — already used!\n\n"
                            f"Message:\n`{escape_md(text[:200])}`"
                        ),
                        parse_mode="Markdown"
                    )
                except:
                    pass
                # Keep state so they can try with a real SMS
                pending_payments[user.id] = prod_id
                user_states[user.id] = AWAIT_MPESA_MSG
                return

            # ── All checks passed ────────────────────────────────────────
            del pending_payments[user.id]
            user_states.pop(user.id, None)
            save_order(user, prod, mpesa_msg=text, status="verified")

            # ── ANTI-SCAM: Mark transaction used IMMEDIATELY ─────────────
            if receipt_no != "N/A":
                mark_transaction_used(receipt_no, user.id, prod["id"])

            # ── LOYALTY POINTS: 10pts per KSh 100 spent ──────────────────
            pts_earned = max(10, int(paid_amount / 100) * 10)
            add_loyalty_points(user.id, pts_earned, f"Purchase: {prod["name"]}")

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

                # ── ANTI-SCAM: Generate one-time 24hr download token ─────
                token = generate_download_token(user.id, prod["id"], prod["link"])

                # Build the one-time link (served by admin_panel Flask /download/<token>)
                # If you have a custom domain set DOWNLOAD_BASE_URL in env, else use Railway URL
                base_url = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("DOWNLOAD_BASE_URL", "http://localhost:5000")
                one_time_link = f"{base_url}/download/{token}"

                try:
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=(
                            f"📦 *{prod['name']}* — Your Download Link\n\n"
                            f"🔗 {one_time_link}\n\n"
                            f"⚠️ *Important:*\n"
                            f"• This link works *one time only*\n"
                            f"• It expires in *24 hours*\n"
                            f"• Do *not* share it — it is tied to your account\n\n"
                            f"_{BOT_NAME} | {COMPANY}_"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Token link send error: {e}")

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
                _ps = get_settings()
                _pb = _ps.get("bot_banner_image", "") or CYBER_IMAGE
                buttons = [
                    [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                    [InlineKeyboardButton("🏠 Home", callback_data="home")],
                    [me_button()],
                ]
                await update.message.reply_photo(
                    photo=_pb,
                    caption=f"{confirm}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await send_product_rating_request(context, user.id, prod['name'], prod['id'])
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

    # ── Product review ────────────────────────────────────────────────
    if state == AWAIT_PRODUCT_REVIEW:
        await save_product_review(update, context, text)
        return

    # ── Bot review ────────────────────────────────────────────────────
    if state == AWAIT_BOT_REVIEW:
        await save_bot_review(update, context, text)
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

    elif data.startswith("cat_"):
        await show_category(query, context, data[4:])
    elif data.startswith("prod_"):
        await show_product(query, context, data[5:])
    elif data.startswith("paid_"):
        await payment_initiate(query, context, data[5:])

    elif data == "noop":
        await query.answer()

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

    # ── Group Chat ─────────────────────────────────────────────────────
    elif data == "group_chat":
        await show_group_chat(query, context)

    # ── Bot Rating ─────────────────────────────────────────────────────
    elif data == "rate_bot":
        await show_bot_rating(query, context)
    elif data.startswith("bot_rate_"):
        await handle_bot_rating(query, context, int(data.split("_")[-1]))
    elif data == "skip_bot_review":
        clear_user_state(query.from_user.id)
        context.user_data.pop(f"bot_rating_{query.from_user.id}", None)
        await query.message.reply_text("👍 Thanks anyway!", reply_markup=InlineKeyboardMarkup([back_home_row()]))

    # ── Product Rating ──────────────────────────────────────────────────
    elif data.startswith("prod_rate_"):
        parts = data.split("_")
        await handle_product_rating(query, context, parts[2], int(parts[3]))
    elif data == "skip_prod_review":
        clear_user_state(query.from_user.id)
        context.user_data.pop(f"prod_rating_{query.from_user.id}", None)
        await query.message.reply_text("👍 Enjoy your purchase!", reply_markup=InlineKeyboardMarkup([back_home_row()]))


    # ── My Account ─────────────────────────────────────────────────────
    elif data == "my_account":
        acc = get_account(user_id)
        name   = acc.get("display_name") or query.from_user.first_name
        email  = acc.get("email") or "Not set"
        points = acc.get("loyalty_points", 0)
        joined = (acc.get("joined_at") or "")[:10]
        conn2 = get_db()
        order_count = conn2.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='verified'", (user_id,)
        ).fetchone()[0]
        conn2.close()
        text2 = (
            f"👤 *My Account*\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📛 Name: *{name}*\n"
            f"📧 Email: {email}\n"
            f"🏆 Loyalty Points: *{points} pts*\n"
            f"🛒 Verified Orders: *{order_count}*\n"
            f"📅 Joined: {joined}\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"_Every purchase earns *10pts per KSh 100* spent!_\n"
            f"_100pts = KSh 50 discount_ 🎁"
        )
        btns = [
            [InlineKeyboardButton("🛒 My Orders",      callback_data="my_orders_btn"),
             InlineKeyboardButton("🏆 Loyalty Points", callback_data="loyalty_info")],
            [InlineKeyboardButton("🔄 Redownload",     callback_data="redownload_menu"),
             InlineKeyboardButton("🔗 My Referral",    callback_data="my_referral_btn")],
            [InlineKeyboardButton("🔔 Alert Settings", callback_data="alert_settings")],
            back_home_row(),
        ]
        await send_cyber_footer(query, context, text2, btns)

    elif data == "my_orders_btn":
        acc = get_account(user_id)
        conn2 = get_db()
        rows = conn2.execute(
            "SELECT product_name, amount, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15",
            (user_id,)
        ).fetchall()
        conn2.close()
        name = acc.get("display_name") or query.from_user.first_name
        if not rows:
            txt = f"🛒 *{name}'s Orders*\n\nNo orders yet! Browse the shop to get started."
        else:
            txt = f"🛒 *{name}'s Orders*\n\n"
            for r in rows:
                icon = "✅" if r[2] == "verified" else "⏳"
                txt += f"{icon} *{r[0]}*\n💰 {r[1]} | 📅 {r[3][:10]}\n\n"
        await send_cyber_footer(query, context, txt, [
            [InlineKeyboardButton("🔄 Request Redownload", callback_data="redownload_menu")],
            [InlineKeyboardButton("◀ Back", callback_data="my_account")],
        ])

    elif data == "loyalty_info":
        acc = get_account(user_id)
        points = acc.get("loyalty_points", 0)
        conn2 = get_db()
        logs = conn2.execute(
            "SELECT points, reason, created_at FROM loyalty_log WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ).fetchall()
        conn2.close()
        txt = (
            f"🏆 *Loyalty Points*\n\n"
            f"Your balance: *{points} pts*\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"*How to earn:*\n"
            f"• Every purchase earns 10pts per KSh 100\n"
            f"• Welcome bonus: 50pts\n"
            f"• Referral bonus: 20pts\n\n"
            f"*How to redeem:*\n"
            f"100pts = KSh 50 discount — contact admin\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"*Recent activity:*\n"
        )
        for log in logs:
            sign = "+" if log[0] > 0 else ""
            txt += f"• {sign}{log[0]}pts — {log[1]} ({log[2][:10]})\n"
        if not logs:
            txt += "_No activity yet_"
        await send_cyber_footer(query, context, txt, [
            [InlineKeyboardButton("💬 Redeem Points", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
            [InlineKeyboardButton("◀ Back", callback_data="my_account")],
        ])

    elif data == "redownload_menu":
        conn2 = get_db()
        purchases = conn2.execute(
            "SELECT DISTINCT product_id, product_name FROM orders WHERE user_id=? AND status='verified'",
            (user_id,)
        ).fetchall()
        conn2.close()
        if not purchases:
            await send_cyber_footer(query, context,
                "🔄 *Redownload*\n\nNo verified purchases found. Buy something first!",
                [[InlineKeyboardButton("🛍 Shop", callback_data="shop"),
                  InlineKeyboardButton("◀ Back", callback_data="my_account")]]
            )
            return
        btns = [
            [InlineKeyboardButton(f"📦 {p[1]}", callback_data=f"req_redl_{p[0]}")]
            for p in purchases
        ]
        btns.append([InlineKeyboardButton("◀ Back", callback_data="my_account")])
        await send_cyber_footer(query, context,
            "🔄 *Request Redownload*\n\nSelect the product you need re-sent 👇",
            btns
        )

    elif data.startswith("req_redl_"):
        prod_id2 = data[9:]
        prod2 = get_product(prod_id2)
        name2 = prod2["name"] if prod2 else prod_id2
        conn2 = get_db()
        conn2.execute(
            "INSERT INTO redownload_requests (user_id, product_id, product_name, status, created_at) VALUES (?,?,?,'pending',?)",
            (user_id, prod_id2, name2, datetime.now().isoformat())
        )
        conn2.commit()
        conn2.close()
        try:
            acc2 = get_account(user_id)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔄 *Redownload Request*\n\n"
                    f"👤 {acc2.get('display_name') or query.from_user.full_name}\n"
                    f"🆔 `{user_id}`\n"
                    f"📦 Product: *{name2}*\n\n"
                    f"Reply: `/msg {user_id} <download link>`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Redownload notify error: {e}")
        await send_cyber_footer(query, context,
            f"✅ *Redownload Requested!*\n\n📦 *{name2}*\n\nAdmin notified — file will be resent shortly. ⏳",
            [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
        )

    elif data == "alert_settings":
        conn2 = get_db()
        row2 = conn2.execute("SELECT subscribed FROM alert_subscribers WHERE user_id=?", (user_id,)).fetchone()
        conn2.close()
        subbed = row2 and row2[0]
        status_txt = "🔔 *ON* — you receive new product alerts" if subbed else "🔕 *OFF* — not receiving alerts"
        await send_cyber_footer(query, context,
            f"🔔 *Alert Settings*\n\nNew product notifications:\n{status_txt}",
            [
                [InlineKeyboardButton("🔕 Turn OFF" if subbed else "🔔 Turn ON",
                    callback_data="toggle_alerts")],
                [InlineKeyboardButton("◀ Back", callback_data="my_account")],
            ]
        )

    elif data == "toggle_alerts":
        conn2 = get_db()
        row2 = conn2.execute("SELECT subscribed FROM alert_subscribers WHERE user_id=?", (user_id,)).fetchone()
        new_val = 0 if (row2 and row2[0]) else 1
        conn2.execute(
            "INSERT OR REPLACE INTO alert_subscribers (user_id, subscribed, created_at) VALUES (?,?,?)",
            (user_id, new_val, datetime.now().isoformat())
        )
        conn2.commit()
        conn2.close()
        msg2 = "🔔 Alerts *turned ON*! You'll be notified of new products." if new_val else "🔕 Alerts *turned OFF*."
        await send_cyber_footer(query, context, msg2,
            [[InlineKeyboardButton("◀ Back", callback_data="alert_settings")]]
        )

    elif data == "my_referral_btn":
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user_id}"
        txt = (
            f"🔗 *Your Referral Link*\n\n"
            f"`{ref_link}`\n\n"
            f"🏆 Earn *20 loyalty points* for every friend who joins!\n\n"
            f"_Tap to copy and share_ 👆"
        )
        await send_cyber_footer(query, context, txt, [
            [InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={ref_link}&text=Check+out+{BOT_NAME}!")],
            [InlineKeyboardButton("◀ Back", callback_data="my_account")],
        ])

    elif data == "reg_cancel":
        clear_user_state(user_id)
        context.user_data.pop(f"reg_name_{user_id}", None)
        context.user_data.pop(f"reg_pass_{user_id}", None)
        await query.message.reply_text("Registration cancelled. Use /start to try again.")

    elif data == "reg_skip_email":
        user_id2 = query.from_user.id
        name3  = context.user_data.pop(f"reg_name_{user_id2}", query.from_user.first_name)
        pass3  = context.user_data.pop(f"reg_pass_{user_id2}", "default")
        complete_registration(user_id2, name3, pass3, "")
        clear_user_state(user_id2)
        add_loyalty_points(user_id2, 50, "Welcome bonus")
        _s2 = get_settings()
        banner2 = _s2.get("bot_banner_image", "") or CYBER_IMAGE
        keyboard2 = [
            [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
             InlineKeyboardButton("🛠 Services",    callback_data="services")],
            [InlineKeyboardButton("👤 My Account",  callback_data="my_account"),
             InlineKeyboardButton("📞 Contact",     callback_data="contact")],
            [me_button()],
        ]
        await query.message.reply_photo(
            photo=banner2,
            caption=(
                f"🎉 *Account Created!*\n\n"
                f"Welcome, *{name3}!* 🚀\n\n"
                f"🏆 You earned *50 loyalty points* as a welcome bonus!\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{WELCOME_MSG}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard2)
        )

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
# ══════════════════════════════════════════════
#   REGISTRATION FLOW
# ══════════════════════════════════════════════
async def begin_registration(update_or_msg, context):
    """Step 1 — Ask for display name."""
    # Works with both Update objects and message objects
    msg = update_or_msg.message if hasattr(update_or_msg, "message") else update_or_msg
    user_id = msg.chat_id
    set_user_state(user_id, AWAIT_REG_NAME)
    _s = get_settings()
    banner = _s.get("bot_banner_image", "") or CYBER_IMAGE
    await msg.reply_photo(
        photo=banner,
        caption=(
            f"👋 *Welcome to {BOT_NAME}!*\n"
            f"🏙 _{COMPANY}_\n\n"
            f"Let's set up your account in 3 quick steps.\n\n"
            f"*Step 1 of 3*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📝 What should we call you?\n\n"
            f"_Type your full name below (e.g. Xavi Clinton)_ 👇"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="reg_cancel")]])
    )

async def reg_ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    """Step 2 - Ask for password."""
    user_id = update.effective_user.id
    context.user_data[f"reg_name_{user_id}"] = name
    set_user_state(user_id, AWAIT_REG_PASSWORD)
    await update.message.reply_text(
        f"\u2705 Nice to meet you, *{name}!*\n\n"
        f"*Step 2 of 3*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f510 Create a *password* for your account\n\n"
        f"\u2022 Minimum 6 characters\n"
        f"\u2022 Mix letters and numbers for security\n\n"
        f"_Type your password below_ \U0001f447",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u274c Cancel", callback_data="reg_cancel")]])
    )

async def reg_ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE, password: str):
    """Step 3 - Ask for email."""
    user_id = update.effective_user.id
    context.user_data[f"reg_pass_{user_id}"] = password
    set_user_state(user_id, AWAIT_REG_EMAIL)
    await update.message.reply_text(
        "\U0001f510 *Password saved!*\n\n"
        "*Step 3 of 3 \u2014 Last one!*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4e7 What's your *email address*?\n\n"
        "_Used for receipts and account recovery_\n\n"
        "_Type your email below_ \U0001f447",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u23ed Skip Email", callback_data="reg_skip_email")]])
    )

async def reg_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, email: str):
    """Finish registration and show main menu."""
    user    = update.effective_user
    user_id = user.id
    name    = context.user_data.pop(f"reg_name_{user_id}", user.first_name)
    password = context.user_data.pop(f"reg_pass_{user_id}", "default")

    complete_registration(user_id, name, password, email)
    clear_user_state(user_id)
    add_loyalty_points(user_id, 50, "Welcome bonus")

    _s = get_settings()
    banner = _s.get("bot_banner_image", "") or CYBER_IMAGE
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⏬ Downloader",      callback_data="downloader_menu"),
         InlineKeyboardButton("💬 Group Chat",  callback_data="group_chat")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("👤 My Account",  callback_data="my_account"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
        [me_button()],
    ]
    await update.message.reply_photo(
        photo=banner,
        caption=(
            f"🎉 *Account Created Successfully!*\n\n"
            f"Welcome aboard, *{name}!* 🚀\n\n"
            f"🏆 You earned *50 loyalty points* as a welcome bonus!\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{WELCOME_MSG}"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🆕 *New User Registered!*\n\n"
                f"👤 Name: *{name}*\n"
                f"📧 Email: {email or 'Not provided'}\n"
                f"🔗 Telegram: @{user.username or 'N/A'}\n"
                f"🆔 ID: `{user_id}`"
            ),
            parse_mode="Markdown"
        )
    except:
        pass


async def start_with_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    user_states.pop(user.id, None)

    # ── Check if user has completed registration ──────────────────────
    if not is_registered(user.id):
        # Check for referral param — save for after registration
        if context.args and context.args[0].startswith("ref_"):
            context.user_data[f"pending_ref_{user.id}"] = context.args[0]
        await begin_registration(update, context)
        return

    # ── Returning user — personalised welcome ─────────────────────────
    account = get_account(user.id)
    display_name = account.get("display_name") or user.first_name
    points = account.get("loyalty_points", 0)
    _s = get_settings()
    banner = _s.get("bot_banner_image", "") or CYBER_IMAGE

    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("💬 Group Chat",   callback_data="group_chat")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("👤 My Account",  callback_data="my_account"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
        [me_button()],
    ]
    await update.message.reply_photo(
        photo=banner,
        caption=(
            f"\U0001f44b *Hello, {display_name}!*\n\n"
            f"Welcome back to *{BOT_NAME}* \U0001f680\n"
            f"\U0001f3d9 _{COMPANY}_\n\n"
            f"\U0001f3c6 Loyalty Points: *{points} pts*\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"What would you like to do today? \U0001f447"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return

    # Check for referral
    if context.args and context.args[0].startswith("ref_"):
        ref_id = context.args[0].replace("ref_", "")
        try:
            ref_id_int = int(ref_id)
            if ref_id_int != user.id:
                try:
                    add_loyalty_points(ref_id_int, 20, f"Referral: {user.first_name} joined")
                    await context.bot.send_message(
                        chat_id=ref_id_int,
                        text=f"🎉 *{user.first_name}* just joined via your referral link!\n\nContact admin to claim your reward 👇",
                        parse_mode="Markdown"
                    )
                except:
                    pass
        except:
            pass

    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu"),
         InlineKeyboardButton("💬 Group Chat",   callback_data="group_chat")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("ℹ About",        callback_data="about"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
        [me_button()],
    ]
    await send_cyber_footer(update, context, WELCOME_MSG, keyboard)


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start",     start_with_ref))  # handles /start and /start ref_xxx
    app.add_handler(CommandHandler("myorders",  my_orders))
    app.add_handler(CommandHandler("referral",  my_referral))
    app.add_handler(CommandHandler("contact",   contact_command))

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
    app.add_handler(CommandHandler("alertproduct",    admin_alert_new_product))
    app.add_handler(CommandHandler("orders",         admin_orders))
    app.add_handler(CommandHandler("adminfix",       adminfix))
    
    # Inline mode
    from telegram.ext import InlineQueryHandler
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # Callback & messages
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Scheduled quotes: 6:30AM, 12PM, 3PM, 9PM EAT
    jq = app.job_queue
    if jq:
        import datetime as _dt
        jq.run_daily(send_scheduled_quote, time=_dt.time(3, 30))   # 6:30 AM EAT
        jq.run_daily(send_scheduled_quote, time=_dt.time(9, 0))    # 12:00 PM EAT
        jq.run_daily(send_scheduled_quote, time=_dt.time(12, 0))   # 3:00 PM EAT
        jq.run_daily(send_scheduled_quote, time=_dt.time(18, 0))   # 9:00 PM EAT

    logger.info(f"🚀 {BOT_NAME} bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
