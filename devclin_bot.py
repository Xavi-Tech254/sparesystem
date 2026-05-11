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

    # Seed default settings
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_name', 'Clinton Oduor')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('mpesa_number', '0743810633')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('ai_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('downloader_api_key', '')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('music_api_key', '')")

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
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_states_db (user_id, state, extra, updated_at) VALUES (?,?,?,?)",
              (user_id, state, extra, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    user_states[user_id] = state

def get_user_state(user_id: int):
    # Check in-memory first
    if user_id in user_states:
        return user_states[user_id]
    # Fall back to DB
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT state, extra FROM user_states_db WHERE user_id=?", (user_id,))
        row = c.fetchone()
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
        c = conn.cursor()
        c.execute("DELETE FROM user_states_db WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass


    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

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
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active"]
    return [dict(zip(keys, r)) for r in rows]

def get_product(prod_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (prod_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    keys = ["id","name","category","price","price_value","type","desc","link","icon","active"]
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
AWAIT_MUSIC_SEARCH   = 10
AWAIT_YT_SEARCH      = 11
AWAIT_TIKTOK_LINK    = 12
AWAIT_FB_LINK        = 13
AWAIT_SPOTIFY_SEARCH = 14
AWAIT_YTMUSIC_SEARCH = 15
AWAIT_DL_LINK        = 16
AWAIT_AI_CHAT        = 17

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
    full_caption = f"{caption}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    markup = InlineKeyboardMarkup(keyboard)

    # Case 1: it's a CallbackQuery object
    if hasattr(update_or_query, 'edit_message_media'):
        try:
            await update_or_query.edit_message_media(
                media=InputMediaPhoto(media=CYBER_IMAGE, caption=full_caption, parse_mode="Markdown"),
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
                photo=CYBER_IMAGE, caption=full_caption,
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
                photo=CYBER_IMAGE, caption=full_caption,
                parse_mode="Markdown", reply_markup=markup
            )
            return
    except Exception as e:
        logger.error(f"send_cyber_footer (update) failed: {e}")


async def start_from_query(query, context):
    """Show main menu from a callback query (button press)."""
    user_states.pop(query.from_user.id, None)
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("🎵 Music",       callback_data="music_menu"),
         InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu")],
        [InlineKeyboardButton("🤖 AI Assistant",callback_data="ai_menu"),
         InlineKeyboardButton("🔗 Links",       callback_data="links")],
        [InlineKeyboardButton("ℹ About",        callback_data="about"),
         InlineKeyboardButton("📞 Contact",     callback_data="contact")],
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
#   MUSIC SEARCH  (via iTunes Search API — free, no key)
# ══════════════════════════════════════════════
async def search_music_itunes(query: str):
    """Search iTunes for tracks. Returns list of result dicts."""
    import asyncio
    try:
        params = urllib.parse.urlencode({"term": query, "media": "music", "limit": 8, "entity": "song"})
        url = f"https://itunes.apple.com/search?{params}"
        loop = asyncio.get_event_loop()
        def _fetch():
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DevClinBot/1.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return _json.loads(resp.read().decode())
        data = await loop.run_in_executor(None, _fetch)
        results = data.get("results", [])
        if results:
            return results
    except Exception as e:
        logger.error(f"iTunes search error: {e}")

    # Fallback: try Deezer API (free, no key needed)
    try:
        params2 = urllib.parse.urlencode({"q": query, "limit": 8})
        url2 = f"https://api.deezer.com/search?{params2}"
        loop = asyncio.get_event_loop()
        def _fetch2():
            req = urllib.request.Request(url2, headers={"User-Agent": "DevClinBot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return _json.loads(resp.read().decode())
        data2 = await loop.run_in_executor(None, _fetch2)
        deezer_results = data2.get("data", [])
        # Normalize to iTunes-like format
        normalized = []
        for r in deezer_results:
            normalized.append({
                "trackName":   r.get("title", "Unknown"),
                "artistName":  r.get("artist", {}).get("name", "Unknown"),
                "previewUrl":  r.get("preview", ""),
                "trackViewUrl": r.get("link", ""),
                "_source": "deezer",
            })
        return normalized
    except Exception as e:
        logger.error(f"Deezer fallback error: {e}")
        return []

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
        [InlineKeyboardButton("🎵 Music",       callback_data="music_menu"),
         InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu")],
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
        await query.edit_message_text("Product not found.")
        return

    receiver_name, receiver_number = get_mpesa_settings()

    text = (
        f"{prod['icon']} *{prod['name']}*\n\n"
        f"💰 *Price:* {prod['price']}\n"
        f"📁 *Type:* {prod['type']}\n\n"
        f"{prod['desc']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Payment via M-Pesa Send Money:*\n"
        f"📱 Send to: *{receiver_number}*\n"
        f"👤 Name: *{receiver_name}*\n"
        f"💰 Amount: *{prod['price']}*\n\n"
        f"After payment, tap ✅ *I've Paid* and paste your M-Pesa confirmation message."
    )

    buttons = [
        [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{prod_id}")],
        [InlineKeyboardButton(f"◀ Back", callback_data=f"cat_{prod['category']}"),
         InlineKeyboardButton("🏠 Home", callback_data="home")],
        [me_button()],
    ]
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
#   🎵 MUSIC MENU
# ══════════════════════════════════════════════
async def show_music_menu(query, context):
    text = (
        "🎵 *Music Search*\n\n"
        "Search for any song or artist and listen instantly!\n\n"
        "Tap the button below, then type a song name or artist 🎶"
    )
    buttons = [
        [InlineKeyboardButton("🔍 Search Music", callback_data="music_search")],
        back_home_row(),
        me_row(),
    ]
    await send_cyber_footer(query, context, text, buttons)

async def prompt_music_search(query, context):
    user_id = query.from_user.id
    set_user_state(user_id, AWAIT_MUSIC_SEARCH)
    text = "🎵 *Music Search*\n\nType the song name or artist name below 👇"
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="music_menu")]]
    await send_cyber_footer(query, context, text, buttons)

async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    """Search iTunes/Deezer and present results."""
    user = update.effective_user
    clear_user_state(user.id)

    await update.message.reply_text("🔍 Searching music... please wait ⏳")
    results = await search_music_itunes(query_text)

    if not results:
        buttons = [
            [InlineKeyboardButton("🔍 Try Again", callback_data="music_search")],
            back_home_row(),
        ]
        await update.message.reply_text(
            "😔 No results found. Try a different name.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    import html as _html
    source_label = "Deezer" if results[0].get("_source") == "deezer" else "iTunes"
    text = f"🎵 <b>Results for:</b> <i>{_html.escape(query_text)}</i> ({source_label})\n\n"
    buttons = []
    for i, r in enumerate(results[:5]):
        artist  = _html.escape(r.get("artistName", "Unknown Artist"))
        track   = _html.escape(r.get("trackName", "Unknown Track"))
        preview = r.get("previewUrl", "")
        store   = r.get("trackViewUrl", "")

        text += f"{i+1}. 🎵 <b>{track}</b>\n   👤 {artist}\n"

        row = []
        if preview:
            row.append(InlineKeyboardButton(f"▶ Preview #{i+1}", url=preview))
        if store:
            label = "🍎 Apple Music" if source_label == "iTunes" else "🎧 Deezer"
            row.append(InlineKeyboardButton(label, url=store))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton("🔍 Search Again", callback_data="music_search")])
    buttons.append(back_home_row())

    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

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

    # Admin shortcut
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "👋 Use /admin for the admin panel or /msg <user_id> <message> to contact a user.",
            parse_mode="Markdown"
        )
        return

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

    # ── Music search ───────────────────────────────────────────────────
    if state == AWAIT_MUSIC_SEARCH:
        await handle_music_search(update, context, text)
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

    # ── Music ──────────────────────────────────────────────────────────
    elif data == "music_menu":
        await show_music_menu(query, context)
    elif data == "music_search":
        await prompt_music_search(query, context)

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

    keyboard = [
        [InlineKeyboardButton("🛍 Shop",        callback_data="shop"),
         InlineKeyboardButton("🛠 Services",    callback_data="services")],
        [InlineKeyboardButton("🎵 Music",       callback_data="music_menu"),
         InlineKeyboardButton("⬇️ Downloader",  callback_data="downloader_menu")],
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
