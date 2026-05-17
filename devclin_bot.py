import logging
import os
import re
import sqlite3
import asyncio
import urllib.request
import urllib.parse
import json as _json
import secrets as _secrets
import hashlib
import random as _random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, InlineQueryHandler
)
from telegram import InlineQueryResultArticle, InputTextMessageContent
import uuid as _uuid
from flask import Flask
from threading import Thread

# ══════════════════════════════════════════════
#   WEB KEEP-ALIVE
# ══════════════════════════════════════════════
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Dev Clin Market is running!"

def run_web():
    app_web.run(host='0.0.0.0', port=8080)

Thread(target=run_web, daemon=True).start()

# ══════════════════════════════════════════════
#   LOGGING
# ══════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#   CONFIG
# ══════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "8589728931:AAFTJDW94p_BOTr-q6AXua-hunOXmbXNSDQ")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "6105493227"))

BOT_NAME   = "Dev Clin Market"
BOT_HANDLE = "@DevClinBot"
COMPANY    = "Skyline Technologies"
TAGLINE    = "Elevating Digital Solutions"
PORTFOLIO  = "https://devclin.netlify.app"
WHATSAPP   = "https://wa.me/17808518629"
INSTAGRAM  = "https://instagram.com/skyline_tech"
ADMIN_TG   = "@yourusername"

MPESA_RECEIVER_NAME   = "Clinton Oduor"
MPESA_RECEIVER_NUMBER = "0743810633"

ME_LINK  = PORTFOLIO
ME_LABEL = "👤 Me"
ME_BIO   = "Built by Dev Clin 🚀\nSkyline Technologies — Elevating Digital Solutions"

CYBER_IMAGE = "https://i.postimg.cc/CLHFDLbK/Gemini-Generated-Image-avf6o5avf6o5avf6.png"

DOWNLOAD_EXPIRY_MINUTES = 39
DOWNLOAD_MAX_CLICKS     = 3
POINTS_PER_DISCOUNT     = 100
DISCOUNT_AMOUNT         = 100.0

# ══════════════════════════════════════════════
#   CONVERSATION STATES
# ══════════════════════════════════════════════
(
    REG_USERNAME, REG_PASSWORD,
    AWAIT_MPESA_MSG,
    DASH_USERNAME, DASH_PASSWORD,
    DASH_CHANGE_NAME,
    SERVICE_PICK, SERVICE_DESC,
    AWAIT_BOT_REVIEW, AWAIT_PRODUCT_REVIEW,
    ADMIN_REPLY_MSG,
) = range(11)

# In-memory state stores
user_states        = {}   # user_id -> state
user_data_temp     = {}   # user_id -> dict of temp data
pending_payments   = {}   # user_id -> product_id
admin_reply_target = {}   # admin_id -> target_user_id

# ══════════════════════════════════════════════
#   DATABASE
# ══════════════════════════════════════════════
DB_PATH = "devclin.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id      INTEGER PRIMARY KEY,
        username         TEXT UNIQUE,
        display_name     TEXT,
        password_hash    TEXT,
        points           INTEGER DEFAULT 0,
        discount_balance REAL DEFAULT 0,
        joined_at        TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id          TEXT PRIMARY KEY,
        name        TEXT,
        category    TEXT,
        price       TEXT,
        price_value REAL,
        type        TEXT,
        desc        TEXT,
        link        TEXT,
        icon        TEXT,
        active      INTEGER DEFAULT 1,
        image_url   TEXT DEFAULT '',
        sale_price  REAL DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id    TEXT PRIMARY KEY,
        label TEXT,
        icon  TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        username     TEXT,
        display_name TEXT,
        product_id   TEXT,
        product_name TEXT,
        amount       TEXT,
        amount_value REAL,
        status       TEXT DEFAULT 'pending',
        mpesa_msg    TEXT,
        created_at   TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_downloads (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        product_id   TEXT,
        product_name TEXT,
        file_url     TEXT,
        click_count  INTEGER DEFAULT 3,
        expires_at   TEXT,
        created_at   TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS used_transactions (
        txn_id     TEXT PRIMARY KEY,
        user_id    INTEGER,
        product_id TEXT,
        used_at    TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        username     TEXT,
        display_name TEXT,
        product_id   TEXT,
        product_name TEXT,
        rating       INTEGER,
        review       TEXT,
        type         TEXT DEFAULT 'product',
        created_at   TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        from_name    TEXT,
        to_user_id   INTEGER,
        message      TEXT,
        direction    TEXT,
        created_at   TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS service_inquiries (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        username     TEXT,
        display_name TEXT,
        service_name TEXT,
        description  TEXT,
        created_at   TEXT,
        replied      INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_states_db (
        user_id    INTEGER PRIMARY KEY,
        state      INTEGER,
        extra      TEXT,
        updated_at TEXT
    )''')

    # Default settings
    defaults = [
        ('mpesa_name',         MPESA_RECEIVER_NAME),
        ('mpesa_number',       MPESA_RECEIVER_NUMBER),
        ('bot_banner_image',   ''),
        ('banner_shop',        ''),
        ('banner_payment',     ''),
        ('banner_services',    ''),
        ('banner_contact',     ''),
        ('banner_about',       ''),
        ('banner_group',       ''),
        ('banner_rate',        ''),
        ('banner_links',       ''),
        ('banner_account',     ''),
        ('admin_logo',         ''),
        ('group_chat_link',    ''),
        ('quotes_enabled',     '1'),
        ('ai_api_key',         ''),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    # Seed sample products if empty
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample = [
            ("p1","School Notes Bundle","education","KSh 500",500,"PDF",
             "Complete notes for SS1–SS3. All subjects covered.","","📚",1,"",0),
            ("p2","Business Plan Template","education","KSh 800",800,"DOCX",
             "Professional business plan template. Editable Word format.","","📄",1,"",0),
            ("p3","Android VPN App","apps","KSh 1,200",1200,"APK",
             "Premium VPN for Android. Fast, secure, unlimited data.","","📱",1,"",0),
            ("p4","Afrobeats Mix 2024","music","KSh 300",300,"MP3",
             "Hot afrobeats collection — 30 tracks, 45 minutes.","","🎵",1,"",0),
            ("p5","Tech Tutorial Series","videos","KSh 2,000",2000,"MP4",
             "Full coding tutorial series. Python, Web Dev & more.","","🎬",1,"",0),
            ("p6","Galaxy Tab A9","gadgets","KSh 85,000",85000,"PRODUCT",
             "Samsung Galaxy Tab A9 — brand new sealed box.","","💻",1,"",0),
        ]
        c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", sample)

    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        cats = [
            ("education","📚 Education","📚"),
            ("apps","📱 Apps / APK","📱"),
            ("music","🎵 Music","🎵"),
            ("videos","🎬 Videos","🎬"),
            ("gadgets","💻 Gadgets","💻"),
            ("documents","📄 Documents","📄"),
        ]
        c.executemany("INSERT INTO categories VALUES (?,?,?)", cats)

    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
#   DB HELPERS
# ══════════════════════════════════════════════
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_password(pw: str, hashed: str) -> bool:
    return hash_password(pw) == hashed

def get_settings() -> dict:
    try:
        conn = get_db()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}
    except:
        return {}

def get_mpesa_settings():
    s = get_settings()
    return s.get("mpesa_name", MPESA_RECEIVER_NAME), s.get("mpesa_number", MPESA_RECEIVER_NUMBER)

def get_user(telegram_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_username(username: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE LOWER(username)=?", (username.lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def register_user(telegram_id: int, username: str, display_name: str, password: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (telegram_id,username,display_name,password_hash,points,discount_balance,joined_at) VALUES (?,?,?,?,0,0,?)",
        (telegram_id, username, display_name, hash_password(password), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_products(category=None, active_only=True):
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM products WHERE category=? AND active=?", (category, 1 if active_only else 0)
        ).fetchall()
    else:
        q = "SELECT * FROM products WHERE active=1" if active_only else "SELECT * FROM products"
        rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_product(prod_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (prod_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_order(user_id, username, display_name, product, amount_paid, mpesa_msg):
    conn = get_db()
    conn.execute(
        "INSERT INTO orders (user_id,username,display_name,product_id,product_name,amount,amount_value,status,mpesa_msg,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, username, display_name, product["id"], product["name"],
         product["price"], amount_paid, "verified", mpesa_msg, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def is_transaction_used(txn_id: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT txn_id FROM used_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    conn.close()
    return row is not None

def mark_transaction_used(txn_id, user_id, product_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO used_transactions VALUES (?,?,?,?)",
        (txn_id, user_id, product_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def create_download_access(user_id, product_id, product_name, file_url) -> int:
    """Create download record. Returns the row id."""
    expires_at = (datetime.now() + timedelta(minutes=DOWNLOAD_EXPIRY_MINUTES)).isoformat()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO user_downloads (user_id,product_id,product_name,file_url,click_count,expires_at,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, product_id, product_name, file_url, DOWNLOAD_MAX_CLICKS, expires_at, datetime.now().isoformat())
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id

def use_download_click(download_id: int):
    """Decrement click count. Returns (file_url, clicks_remaining, error_msg)."""
    conn = get_db()
    row = conn.execute("SELECT * FROM user_downloads WHERE id=?", (download_id,)).fetchone()
    if not row:
        conn.close()
        return None, 0, "❌ Download record not found."
    if datetime.now().isoformat() > row["expires_at"]:
        conn.execute("DELETE FROM user_downloads WHERE id=?", (download_id,))
        conn.commit()
        conn.close()
        return None, 0, "⏰ Your download link has expired (39 min limit)."
    if row["click_count"] <= 0:
        conn.close()
        return None, 0, "⛔ You've used all 3 clicks for this download."
    new_count = row["click_count"] - 1
    conn.execute("UPDATE user_downloads SET click_count=? WHERE id=?", (new_count, download_id))
    conn.commit()
    conn.close()
    return row["file_url"], new_count, None

def add_points(user_id: int, amount_paid: float) -> tuple:
    """Add points, check if discount threshold reached. Returns (new_points, discount_granted)."""
    pts_earned = int(amount_paid / 10)
    conn = get_db()
    conn.execute("UPDATE users SET points = points + ? WHERE telegram_id=?", (pts_earned, user_id))
    row = conn.execute("SELECT points, discount_balance FROM users WHERE telegram_id=?", (user_id,)).fetchone()
    new_points = row["points"]
    discount_granted = 0
    while new_points >= POINTS_PER_DISCOUNT:
        new_points -= POINTS_PER_DISCOUNT
        discount_granted += DISCOUNT_AMOUNT
    if discount_granted:
        conn.execute(
            "UPDATE users SET points=?, discount_balance=discount_balance+? WHERE telegram_id=?",
            (new_points, discount_granted, user_id)
        )
    conn.commit()
    conn.close()
    return new_points, discount_granted

def apply_discount(user_id: int, discount_amount: float):
    conn = get_db()
    conn.execute(
        "UPDATE users SET discount_balance = MAX(0, discount_balance - ?) WHERE telegram_id=?",
        (discount_amount, user_id)
    )
    conn.commit()
    conn.close()

def log_message(from_id, from_name, to_id, message, direction):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (from_user_id,from_name,to_user_id,message,direction,created_at) VALUES (?,?,?,?,?,?)",
        (from_id, from_name, to_id, message, direction, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def escape_md(text: str) -> str:
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, f'\\{ch}')
    return text

# ══════════════════════════════════════════════
#   STATE HELPERS
# ══════════════════════════════════════════════
def set_state(user_id: int, state: int, extra: dict = None):
    user_states[user_id] = state
    if extra:
        user_data_temp[user_id] = extra
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_states_db (user_id,state,extra,updated_at) VALUES (?,?,?,?)",
        (user_id, state, _json.dumps(extra or {}), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_state(user_id: int):
    if user_id in user_states:
        return user_states[user_id]
    conn = get_db()
    row = conn.execute("SELECT state FROM user_states_db WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        user_states[user_id] = row["state"]
        return row["state"]
    return None

def clear_state(user_id: int):
    user_states.pop(user_id, None)
    user_data_temp.pop(user_id, None)
    conn = get_db()
    conn.execute("DELETE FROM user_states_db WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
#   UI HELPERS
# ══════════════════════════════════════════════
def me_button():
    return InlineKeyboardButton(ME_LABEL, url=ME_LINK)

def home_row():
    return [InlineKeyboardButton("🏠 Main Menu", callback_data="home")]

def me_row():
    return [me_button(), InlineKeyboardButton("📞 Contact", callback_data="contact")]

async def send_banner(target, context, caption, keyboard, section=None):
    s = get_settings()
    default = s.get("bot_banner_image", "") or CYBER_IMAGE
    section_map = {
        "shop":     s.get("banner_shop", "") or default,
        "payment":  s.get("banner_payment", "") or default,
        "services": s.get("banner_services", "") or default,
        "contact":  s.get("banner_contact", "") or default,
        "about":    s.get("banner_about", "") or default,
        "group":    s.get("banner_group", "") or default,
        "rate":     s.get("banner_rate", "") or default,
        "links":    s.get("banner_links", "") or default,
        "account":  s.get("banner_account", "") or default,
    }
    banner = section_map.get(section, default) if section else default
    full   = f"{caption}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    markup = InlineKeyboardMarkup(keyboard)
    try:
        msg = target.message if hasattr(target, "message") else target
        await msg.reply_photo(photo=banner, caption=full, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"send_banner error: {e}")

# ══════════════════════════════════════════════
#   MAIN MENU
# ══════════════════════════════════════════════
MAIN_MENU_KB = [
    [InlineKeyboardButton("🛍 Shop",         callback_data="shop"),
     InlineKeyboardButton("🛠 Services",     callback_data="services")],
    [InlineKeyboardButton("💬 Group Chat",   callback_data="group_chat"),
     InlineKeyboardButton("🔗 Links",        callback_data="links")],
    [InlineKeyboardButton("ℹ️ About",        callback_data="about"),
     InlineKeyboardButton("📞 Contact",      callback_data="contact")],
    [InlineKeyboardButton("📊 My Dashboard", callback_data="dashboard"),
     InlineKeyboardButton("⭐ Rate Us",      callback_data="rate_bot")],
    [me_button()],
]

WELCOME_MSG = (
    "👋 Welcome to *Dev Clin Market!*\n"
    "Powered by *Skyline Technologies*\n\n"
    "🏙 _Elevating Digital Solutions_\n\n"
    "What would you like to do today? 👇"
)

async def show_main_menu(target, context):
    await send_banner(target, context, WELCOME_MSG, MAIN_MENU_KB)

# ══════════════════════════════════════════════
#   /start — REGISTRATION GATE
# ══════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_state(user_id)

    existing = get_user(user_id)
    if existing:
        await show_main_menu(update, context)
        return

    # New user — start registration
    set_state(user_id, REG_USERNAME)
    await update.message.reply_text(
        "👋 *Welcome to Dev Clin Market!*\n"
        "Powered by *Skyline Technologies* 🚀\n\n"
        "Let's get you set up first!\n\n"
        "👤 Choose a *username* (used for login, must be unique):",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════
#   REGISTRATION FLOW
# ══════════════════════════════════════════════
async def handle_reg_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.message.text.strip()

    if len(username) < 3:
        await update.message.reply_text("❌ Username must be at least 3 characters. Try again:")
        return
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        await update.message.reply_text("❌ Username can only contain letters, numbers and underscores. Try again:")
        return
    if get_user_by_username(username):
        await update.message.reply_text(
            f"❌ *'{username}'* is already taken.\nPlease choose a different username:",
            parse_mode="Markdown"
        )
        return

    user_data_temp[user_id] = {"username": username}
    set_state(user_id, REG_PASSWORD)
    await update.message.reply_text(
        f"✅ *{username}* is available!\n\n"
        "🔒 Now create a *password* (minimum 6 characters):\n"
        "_Keep it safe — you'll need it to access your dashboard._",
        parse_mode="Markdown"
    )

async def handle_reg_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    password = update.message.text.strip()

    if len(password) < 6:
        await update.message.reply_text("❌ Password must be at least 6 characters. Try again:")
        return

    username = user_data_temp.get(user_id, {}).get("username")
    if not username:
        set_state(user_id, REG_USERNAME)
        await update.message.reply_text("Something went wrong. Please enter your username again:")
        return

    tg_user = update.effective_user
    display  = tg_user.full_name or username
    register_user(user_id, username, display, password)
    clear_state(user_id)

    await update.message.reply_text(
        f"🎉 *Welcome aboard, {username}!*\n\n"
        f"✅ Registration complete!\n"
        f"📛 Username: `{username}`\n"
        f"🏷 Display name: {display}\n\n"
        f"Your credentials are saved securely.\n"
        f"Use them to access your Dashboard anytime.\n\n"
        f"Here's your menu 👇",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context)

# ══════════════════════════════════════════════
#   SHOP
# ══════════════════════════════════════════════
async def show_shop(query, context):
    products = get_products()
    cats_with_products = list(dict.fromkeys([p["category"] for p in products]))
    all_cats = {c["id"]: c["label"] for c in get_categories()}

    buttons, row = [], []
    for cat in cats_with_products:
        label = all_cats.get(cat, cat.title())
        row.append(InlineKeyboardButton(label, callback_data=f"cat_{cat}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append(home_row())
    buttons.append(me_row())
    await send_banner(query, context, "🛍 *Shop — Choose a Category*", buttons, "shop")

async def show_category(query, context, cat: str):
    items    = get_products(category=cat)
    all_cats = {c["id"]: c["label"] for c in get_categories()}
    if not items:
        await query.message.reply_text("No products in this category yet.")
        return
    text = f"{all_cats.get(cat, cat.title())} *Products*\n\n"
    for p in items:
        text += f"{p['icon']} *{p['name']}* — {p['price']}\n_{p['desc']}_\n\n"
    buttons = [[InlineKeyboardButton(f"{p['icon']} {p['name']} — {p['price']}", callback_data=f"prod_{p['id']}")] for p in items]
    buttons.append([InlineKeyboardButton("◀ Back to Shop", callback_data="shop")])
    buttons.append(home_row())
    await send_banner(query, context, text, buttons, "shop")

async def show_product(query, context, prod_id: str):
    prod = get_product(prod_id)
    if not prod:
        await query.message.reply_text("Product not found.")
        return

    user_id = query.from_user.id
    user    = get_user(user_id)
    recv_name, recv_num = get_mpesa_settings()

    sale   = prod.get("sale_price", 0) or 0
    pvalue = prod.get("price_value", 0) or 0
    discount_bal = user["discount_balance"] if user else 0

    # Determine effective price
    base_price = sale if (sale and sale < pvalue) else pvalue
    if sale and sale < pvalue:
        price_display = f"~~{prod['price']}~~ ➡ *KSh {sale:,.0f}* 🔥"
    else:
        price_display = f"*{prod['price']}*"

    final_price = max(0, base_price - discount_bal)
    discount_line = ""
    if discount_bal > 0:
        discount_line = (
            f"\n🎁 *Your Points Discount:* KSh {discount_bal:,.0f}\n"
            f"✅ *You Pay:* KSh {final_price:,.0f}"
        )

    text = (
        f"{prod['icon']} *{prod['name']}*\n\n"
        f"💰 *Price:* {price_display}\n"
        f"📁 *Type:* {prod['type']}\n\n"
        f"{prod['desc']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Payment via M-Pesa Send Money:*\n"
        f"📱 Send to: *{recv_num}*\n"
        f"👤 Name: *{recv_name}*\n"
        f"💰 Amount: *KSh {final_price:,.0f}*"
        f"{discount_line}\n\n"
        f"After payment tap ✅ *I've Paid*"
    )

    buttons = [
        [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{prod_id}")],
        [InlineKeyboardButton("◀ Back", callback_data=f"cat_{prod['category']}"),
         InlineKeyboardButton("🏠 Home", callback_data="home")],
        [me_button()],
    ]
    s       = get_settings()
    img_url = prod.get("image_url", "") or s.get("bot_banner_image", "") or CYBER_IMAGE
    full    = f"{text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}"
    try:
        await query.message.reply_photo(photo=img_url, caption=full, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await send_banner(query, context, text, buttons, "shop")

# ══════════════════════════════════════════════
#   PAYMENT INITIATION
# ══════════════════════════════════════════════
async def payment_initiate(query, context, prod_id: str):
    prod = get_product(prod_id)
    if not prod:
        return
    user_id = query.from_user.id
    user    = get_user(user_id)
    recv_name, recv_num = get_mpesa_settings()

    discount_bal = user["discount_balance"] if user else 0
    pvalue       = prod.get("sale_price", 0) or prod.get("price_value", 0)
    final_price  = max(0, pvalue - discount_bal)

    pending_payments[user_id] = prod_id
    set_state(user_id, AWAIT_MPESA_MSG)

    discount_note = ""
    if discount_bal > 0:
        discount_note = (
            f"\n🎁 Discount applied: KSh {discount_bal:,.0f}\n"
            f"✅ *You Pay: KSh {final_price:,.0f}*\n"
        )

    text = (
        f"📲 *M-Pesa Payment Verification*\n\n"
        f"📦 Product: *{prod['name']}*\n"
        f"💰 Amount: *KSh {final_price:,.0f}*"
        f"{discount_note}\n\n"
        f"*Send Money via M-Pesa to:*\n"
        f"📱 Number: *{recv_num}*\n"
        f"👤 Name: *{recv_name}*\n\n"
        f"After paying, paste the full M-Pesa\n"
        f"confirmation SMS below 👇\n\n"
        f"_Example:_\n"
        f"`ABC123XYZ confirmed. Ksh{final_price:,.0f} sent to {recv_name} {recv_num} on {datetime.now().strftime('%d/%m/%y')}...`"
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")]]
    await send_banner(query, context, text, buttons, "payment")

# ══════════════════════════════════════════════
#   PAYMENT VERIFICATION
# ══════════════════════════════════════════════
def parse_mpesa_message(msg: str, expected_amount: float):
    recv_name, recv_num = get_mpesa_settings()

    # CHECK 1 — Phone number
    num_clean = recv_num.replace("+","").replace(" ","")
    num_254   = "254" + num_clean[-9:] if not num_clean.startswith("254") else num_clean
    num_07    = "0"   + num_clean[-9:]
    if num_clean not in msg and num_254 not in msg and num_07 not in msg:
        return False, f"❌ Receiver number *{recv_num}* not found in the SMS.\n\nMake sure you sent to the correct number."

    # CHECK 2 — Amount
    amt_match = re.search(r'[Kk][Ss][Hh]\.?\s*([\d,]+\.?\d*)', msg)
    if not amt_match:
        amt_match = re.search(r'([\d,]+\.\d{2})', msg)
    if not amt_match:
        return False, "❌ Could not read the amount from the SMS.\n\nPlease paste the full M-Pesa confirmation message."
    try:
        paid = float(amt_match.group(1).replace(",",""))
    except:
        return False, "❌ Could not parse the amount. Paste the exact SMS from Safaricom."
    if abs(paid - expected_amount) > 1:
        return False, (
            f"❌ Amount mismatch.\n\n"
            f"Expected: *KSh {expected_amount:,.0f}*\n"
            f"Found in SMS: *KSh {paid:,.0f}*\n\n"
            f"Please pay the exact amount."
        )

    # CHECK 3 — Today's date
    today_formats = [
        datetime.now().strftime("%d/%m/%y"),
        datetime.now().strftime("%d/%m/%Y"),
        datetime.now().strftime("%-d/%-m/%y"),
        datetime.now().strftime("%-d/%-m/%Y"),
    ]
    date_found = any(fmt in msg for fmt in today_formats)
    if not date_found:
        return False, (
            f"❌ Payment date doesn't match today's date.\n\n"
            f"Today is *{datetime.now().strftime('%d/%m/%Y')}*.\n"
            f"Only payments made today are accepted."
        )

    # CHECK 4 — Transaction code
    txn_match = re.search(r'\b([A-Z0-9]{10})\b', msg)
    if not txn_match:
        txn_match = re.search(r'\b([A-Z0-9]{8,12})\b', msg)
    receipt = txn_match.group(1) if txn_match else "N/A"

    date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', msg)
    date_str   = date_match.group(0) if date_match else datetime.now().strftime("%d/%m/%Y")

    return True, {
        "amount":  paid,
        "date":    date_str,
        "receipt": receipt,
        "receiver_name": recv_name,
        "receiver_num":  recv_num,
    }

# ══════════════════════════════════════════════
#   PROCESS VERIFIED PAYMENT
# ══════════════════════════════════════════════
async def process_verified_payment(update: Update, context, user_id, prod, result, raw_sms):
    tg_user      = update.effective_user
    user         = get_user(user_id)
    username     = user["username"] if user else str(user_id)
    display_name = user["display_name"] if user else tg_user.full_name
    receipt_no   = result["receipt"]
    paid_amount  = result["amount"]
    pay_date     = result["date"]

    # Anti-scam: block reused transaction
    if receipt_no != "N/A" and is_transaction_used(receipt_no):
        await update.message.reply_photo(
            photo=CYBER_IMAGE,
            caption=(
                f"🚫 *Transaction Already Used*\n\n"
                f"Code `{receipt_no}` has already been used.\n"
                f"Each M-Pesa SMS can only be used *once*.\n\n"
                f"Contact admin if this is a mistake."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")],
            ])
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⚠️ *REPLAY ATTACK BLOCKED*\n"
                    f"👤 {display_name} (@{tg_user.username or 'N/A'}) `{user_id}`\n"
                    f"📦 {prod['name']}\n"
                    f"🧾 TXN: `{receipt_no}` — already used!\n\n"
                    f"SMS:\n`{escape_md(raw_sms[:200])}`"
                ),
                parse_mode="Markdown"
            )
        except:
            pass
        pending_payments[user_id] = prod["id"]
        set_state(user_id, AWAIT_MPESA_MSG)
        return

    # Save order
    discount_used = user["discount_balance"] if user else 0
    save_order(user_id, username, display_name, prod, paid_amount, raw_sms)
    if receipt_no != "N/A":
        mark_transaction_used(receipt_no, user_id, prod["id"])

    # Apply discount
    if discount_used > 0:
        apply_discount(user_id, discount_used)

    # Add points
    new_points, discount_granted = add_points(user_id, paid_amount)

    # Send receipt
    recv_name, recv_num = get_mpesa_settings()
    receipt_text = (
        f"🧾 *PAYMENT RECEIPT*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏪 *{COMPANY}*\n"
        f"📦 Product: *{prod['name']}*\n"
        f"💰 Amount Paid: *KSh {paid_amount:,.0f}*\n"
        f"📅 Date: {pay_date}\n"
        f"🧾 M-Pesa Ref: `{receipt_no}`\n"
        f"📱 Sent to: {recv_num}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"✅ Confirmed. Thank you, {display_name}! 🎉\n\n"
        f"🏆 Points earned: +{int(paid_amount/10)} pts\n"
        f"📊 Total points: {new_points} pts"
    )
    await update.message.reply_text(receipt_text, parse_mode="Markdown")

    # Notify discount earned
    if discount_granted:
        await update.message.reply_text(
            f"🎉 *Congratulations!*\n\n"
            f"You've earned a *KSh {discount_granted:,.0f} discount!*\n\n"
            f"🏆 Points used: {int(discount_granted/DISCOUNT_AMOUNT)*POINTS_PER_DISCOUNT}\n"
            f"📊 Remaining points: {new_points}\n\n"
            f"Your discount will be applied automatically on your next purchase! 🛍",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🎁 *{display_name}* (`{user_id}`) earned a KSh {discount_granted:,.0f} discount (hit {POINTS_PER_DISCOUNT} points).",
                parse_mode="Markdown"
            )
        except:
            pass

    # Notify admin of sale
    admin_msg = (
        f"✅ *PAYMENT VERIFIED*\n\n"
        f"👤 {display_name} (@{tg_user.username or 'N/A'})\n"
        f"🆔 `{user_id}`\n\n"
        f"📦 *{prod['name']}*\n"
        f"💰 KSh {paid_amount:,.0f}\n"
        f"🧾 Ref: `{receipt_no}`\n"
        f"📅 {pay_date}\n\n"
        f"{'✅ Link set — auto-sent.' if prod['link'] else '⚠️ No link set. Send manually with /msg!'}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
    except:
        pass

    # Send download access
    if prod["link"]:
        dl_id      = create_download_access(user_id, prod["id"], prod["name"], prod["link"])
        expires_at = (datetime.now() + timedelta(minutes=DOWNLOAD_EXPIRY_MINUTES)).strftime("%I:%M %p")
        await update.message.reply_text(
            f"📦 *{prod['name']}* — Download Ready!\n\n"
            f"🔗 *Your download link:*\n{prod['link']}\n\n"
            f"⚠️ *Important:*\n"
            f"• You have *{DOWNLOAD_MAX_CLICKS} clicks* maximum\n"
            f"• Link access expires at *{expires_at}* (39 minutes)\n"
            f"• After limit → access removed\n\n"
            f"🖱 Clicks remaining: *{DOWNLOAD_MAX_CLICKS}/{DOWNLOAD_MAX_CLICKS}*\n"
            f"⏱ Expires: *{expires_at}*\n\n"
            f"_Download ID: #{dl_id} — contact admin if issues_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍 Shop More", callback_data="shop"),
                 InlineKeyboardButton("🏠 Home", callback_data="home")],
            ])
        )
        # Schedule auto-delete after 39 min
        context.job_queue.run_once(
            delete_download_record,
            when=DOWNLOAD_EXPIRY_MINUTES * 60,
            data={"download_id": dl_id, "user_id": user_id, "product_name": prod["name"]}
        )
    else:
        s  = get_settings()
        pb = s.get("bot_banner_image","") or CYBER_IMAGE
        await update.message.reply_photo(
            photo=pb,
            caption=(
                f"✅ *Payment Confirmed!*\n\n"
                f"📦 *{prod['name']}*\n\n"
                f"Admin has been notified and will deliver your item shortly. ⏳\n"
                f"If no reply in 10 minutes, contact us below."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")],
            ])
        )

    # Send product rating request
    await send_product_rating_request(context, user_id, prod["name"], prod["id"])

async def delete_download_record(context: ContextTypes.DEFAULT_TYPE):
    """Job: auto-delete download record after 39 min."""
    data        = context.job.data
    download_id = data["download_id"]
    user_id     = data["user_id"]
    prod_name   = data["product_name"]
    conn = get_db()
    conn.execute("DELETE FROM user_downloads WHERE id=?", (download_id,))
    conn.commit()
    conn.close()
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"⏰ *Download Expired*\n\n"
                f"Your download access for *{prod_name}* has expired (39 min limit).\n\n"
                f"Contact admin if you need assistance."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")],
            ])
        )
    except:
        pass

# ══════════════════════════════════════════════
#   MY DASHBOARD
# ══════════════════════════════════════════════
async def dashboard_start(query, context):
    user_id = query.from_user.id
    set_state(user_id, DASH_USERNAME)
    await query.message.reply_text(
        "📊 *My Dashboard*\n\n"
        "🔐 Please enter your *username* to login:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]])
    )

async def handle_dash_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.message.text.strip()
    found    = get_user_by_username(username)
    if not found:
        await update.message.reply_text(
            "❌ Username not found. Try again or tap Cancel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]])
        )
        return
    user_data_temp[user_id] = {"dash_username": username, "dash_user_id": found["telegram_id"]}
    set_state(user_id, DASH_PASSWORD)
    await update.message.reply_text(
        "🔒 Enter your *password*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]])
    )

async def handle_dash_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    password = update.message.text.strip()
    temp     = user_data_temp.get(user_id, {})
    username = temp.get("dash_username")
    found    = get_user_by_username(username) if username else None

    if not found or not verify_password(password, found["password_hash"]):
        await update.message.reply_text(
            "❌ *Invalid credentials.*\n\nTry again or use /start.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Retry", callback_data="dashboard"),
                                                InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
        clear_state(user_id)
        return

    clear_state(user_id)
    await show_dashboard(update, context, found)

async def show_dashboard(update_or_query, context, user: dict):
    conn = get_db()
    downloads_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='verified'", (user["telegram_id"],)
    ).fetchone()[0]
    conn.close()

    joined = user["joined_at"][:10] if user.get("joined_at") else "N/A"
    text = (
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 *{user['username']}'s Dashboard*\n"
        f"_{COMPANY}_\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏷 Display Name: *{user['display_name']}*\n"
        f"🏆 Points: *{user['points']} pts*\n"
        f"💰 Discount Balance: *KSh {user['discount_balance']:,.0f}*\n"
        f"📥 Total Purchases: *{downloads_count}*\n"
        f"🗓 Member since: {joined}\n\n"
        f"━━━━━━━━━━━━━━━━"
    )
    buttons = [
        [InlineKeyboardButton("📋 My Downloads", callback_data=f"my_downloads_{user['telegram_id']}"),
         InlineKeyboardButton("🏆 My Points", callback_data=f"my_points_{user['telegram_id']}")],
        [InlineKeyboardButton("✏️ Change Name", callback_data=f"change_name_{user['telegram_id']}")],
        home_row(),
    ]
    msg = update_or_query.message if hasattr(update_or_query, "message") else update_or_query
    await send_banner(msg, context, text, buttons, "account")

async def show_my_downloads(query, context, target_user_id: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT product_name, amount, created_at FROM orders WHERE user_id=? AND status='verified' ORDER BY id DESC LIMIT 20",
        (target_user_id,)
    ).fetchall()
    conn.close()

    if not rows:
        text = "📥 *My Downloads*\n\nYou haven't purchased anything yet.\n\nHead to the shop! 🛍"
    else:
        text = "📥 *My Downloads*\n\n"
        for r in rows:
            text += f"✅ *{r['product_name']}*\n💰 {r['amount']} | 📅 {r['created_at'][:10]}\n\n"

    buttons = [
        [InlineKeyboardButton("◀ Back to Dashboard", callback_data="dashboard")],
        home_row(),
    ]
    await send_banner(query, context, text, buttons, "account")

async def show_my_points(query, context, target_user_id: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id=?", (target_user_id,)).fetchone()
    conn.close()
    if not user:
        return
    text = (
        f"🏆 *My Points*\n\n"
        f"📊 Current Points: *{user['points']} pts*\n"
        f"💰 Discount Balance: *KSh {user['discount_balance']:,.0f}*\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*How points work:*\n"
        f"• Every KSh 10 spent = 1 point\n"
        f"• Reach 100 points = KSh 100 discount\n"
        f"• Discount auto-applied on next purchase\n"
        f"• Points reset by 100, remainder carries forward\n\n"
        f"Keep shopping to earn more! 🛍"
    )
    buttons = [
        [InlineKeyboardButton("◀ Back to Dashboard", callback_data="dashboard")],
        home_row(),
    ]
    await send_banner(query, context, text, buttons, "account")

async def start_change_name(query, context, target_user_id: int):
    user_id = query.from_user.id
    user    = get_user(target_user_id)
    if not user:
        return
    user_data_temp[user_id] = {"change_name_for": target_user_id}
    set_state(user_id, DASH_CHANGE_NAME)
    await query.message.reply_text(
        f"✏️ *Change Display Name*\n\n"
        f"Current name: *{user['display_name']}*\n\n"
        f"Enter your new display name:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="dashboard")]])
    )

async def handle_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    new_name = update.message.text.strip()
    temp     = user_data_temp.get(user_id, {})
    for_id   = temp.get("change_name_for", user_id)

    if len(new_name) < 2:
        await update.message.reply_text("❌ Name too short. Minimum 2 characters:")
        return

    # Check if display name already taken by another user
    conn = get_db()
    existing = conn.execute(
        "SELECT telegram_id FROM users WHERE display_name=? AND telegram_id!=?", (new_name, for_id)
    ).fetchone()
    if existing:
        conn.close()
        await update.message.reply_text(
            f"❌ *'{new_name}'* is already taken.\nChoose a different display name:",
            parse_mode="Markdown"
        )
        return
    conn.execute("UPDATE users SET display_name=? WHERE telegram_id=?", (new_name, for_id))
    conn.commit()
    conn.close()
    clear_state(user_id)

    user = get_user(for_id)
    await update.message.reply_text(
        f"✅ *Display name updated!*\n\n"
        f"New name: *{new_name}*\n"
        f"Login username: `{user['username']}` (unchanged)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Back to Dashboard", callback_data="dashboard")],
            home_row(),
        ])
    )

# ══════════════════════════════════════════════
#   SERVICES (Option B + Portfolio)
# ══════════════════════════════════════════════
SERVICES_LIST = [
    {"name": "Web Development",  "price": "KSh 15,000+", "desc": "Full websites & web apps from scratch.",   "icon": "🌐"},
    {"name": "Bot Development",  "price": "KSh 10,000+", "desc": "Telegram & WhatsApp bots with full features.", "icon": "🤖"},
    {"name": "Graphic Design",   "price": "KSh 3,000+",  "desc": "Logos, flyers, banners & brand identity.",  "icon": "🎨"},
    {"name": "App Installation", "price": "KSh 500",     "desc": "Remote installation & setup of any app.",   "icon": "📲"},
]

async def show_services(query, context):
    text = "🛠 *Our Services*\n\n"
    for s in SERVICES_LIST:
        text += f"{s['icon']} *{s['name']}* — {s['price']}\n_{s['desc']}_\n\n"
    text += "Tap *Make Inquiry* to tell us what you need 👇"
    buttons = [
        [InlineKeyboardButton("📩 Make Inquiry", callback_data="service_inquiry")],
        [InlineKeyboardButton("🌐 View Portfolio", url=PORTFOLIO)],
        home_row(),
        me_row(),
    ]
    await send_banner(query, context, text, buttons, "services")

async def service_inquiry_start(query, context):
    user_id = query.from_user.id
    set_state(user_id, SERVICE_PICK)
    buttons = []
    for i, s in enumerate(SERVICES_LIST):
        buttons.append([InlineKeyboardButton(f"{s['icon']} {s['name']}", callback_data=f"svc_{i}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="services")])
    await query.message.reply_text(
        "📩 *Service Inquiry*\n\nWhich service are you interested in?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def service_picked(query, context, idx: int):
    user_id = query.from_user.id
    svc     = SERVICES_LIST[idx]
    user_data_temp[user_id] = {"service_name": svc["name"]}
    set_state(user_id, SERVICE_DESC)
    await query.message.reply_text(
        f"📩 *{svc['icon']} {svc['name']}*\n\n"
        f"📝 Briefly describe what you need\n"
        f"_(be as specific as possible)_:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="services")]])
    )

async def handle_service_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tg_user = update.effective_user
    desc    = update.message.text.strip()
    temp    = user_data_temp.get(user_id, {})
    svc     = temp.get("service_name", "General")
    user    = get_user(user_id)
    username = user["username"] if user else str(user_id)
    display  = user["display_name"] if user else tg_user.full_name
    clear_state(user_id)

    # Save to DB
    conn = get_db()
    conn.execute(
        "INSERT INTO service_inquiries (user_id,username,display_name,service_name,description,created_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, display, svc, desc, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *Inquiry sent!*\n\n"
        f"🛠 Service: *{svc}*\n\n"
        f"We'll get back to you shortly. ⚡\n\n"
        f"_You can also reach us directly:_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP)],
            home_row(),
        ])
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📩 *New Service Inquiry*\n\n"
                f"👤 *{display}* (`{user_id}`)\n"
                f"📛 Username: @{username}\n"
                f"🛠 Service: *{svc}*\n\n"
                f"📝 *Description:*\n{desc}\n\n"
                f"Reply with /msg {user_id} <your reply>"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP)],
            ])
        )
    except:
        pass

# ══════════════════════════════════════════════
#   RATINGS
# ══════════════════════════════════════════════
async def show_bot_rating(query, context):
    user_id = query.from_user.id
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
        home_row(),
    ]
    await send_banner(query, context, text, buttons, "rate")

async def handle_bot_rating(query, context, rating: int):
    user_id = query.from_user.id
    user_data_temp[user_id] = {"bot_rating": rating}
    set_state(user_id, AWAIT_BOT_REVIEW)
    stars = "⭐" * rating
    await query.message.reply_text(
        f"✅ You rated us *{stars}* ({rating}/5)\n\n"
        f"Leave a short review below 💬\n_Or tap Skip._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip Review", callback_data="skip_bot_review")]])
    )

async def save_bot_review(update: Update, context: ContextTypes.DEFAULT_TYPE, review_text: str):
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user    = get_user(user_id)
    username = user["username"] if user else str(user_id)
    display  = user["display_name"] if user else tg_user.full_name
    rating   = user_data_temp.get(user_id, {}).get("bot_rating", 0)
    stars    = "⭐" * rating
    clear_state(user_id)

    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (user_id,username,display_name,product_id,product_name,rating,review,type,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, username, display, "bot", "Dev Clin Market", rating, review_text, "bot", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    s      = get_settings()
    banner = s.get("bot_banner_image","") or CYBER_IMAGE
    review_msg = (
        f"🌟 *New Bot Review*\n\n"
        f"👤 *{display}* (`{user_id}`)\n"
        f"{stars} *{rating}/5*\n\n"
        f"💬 _{review_text}_\n\n_{COMPANY}_"
    )
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=banner, caption=review_msg, parse_mode="Markdown")
    except:
        pass

    group_link = s.get("group_chat_link","")
    if group_link and "t.me/" in group_link:
        try:
            gid = group_link.split("t.me/")[-1].strip("/")
            await context.bot.send_photo(chat_id=f"@{gid}", photo=banner, caption=review_msg, parse_mode="Markdown")
        except:
            pass

    await update.message.reply_text(
        f"✅ *Thank you for your review!* {stars}\n\n_{COMPANY}_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([home_row()])
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
            text=f"⭐ *How was {product_name}?*\n\nYour feedback helps other buyers!\nTap a star 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except:
        pass

async def handle_product_rating(query, context, product_id: str, rating: int):
    user_id = query.from_user.id
    user_data_temp[user_id] = {"prod_rating": rating, "prod_id": product_id}
    set_state(user_id, AWAIT_PRODUCT_REVIEW)
    stars = "⭐" * rating
    await query.message.reply_text(
        f"✅ You rated *{stars}* ({rating}/5)\n\nLeave a short review 👇\n_Or tap Skip._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data="skip_prod_review")]])
    )

async def save_product_review(update: Update, context: ContextTypes.DEFAULT_TYPE, review_text: str):
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user    = get_user(user_id)
    username  = user["username"] if user else str(user_id)
    display   = user["display_name"] if user else tg_user.full_name
    temp      = user_data_temp.get(user_id, {})
    rating    = temp.get("prod_rating", 0)
    product_id = temp.get("prod_id", "")
    prod      = get_product(product_id)
    prod_name = prod["name"] if prod else product_id
    stars     = "⭐" * rating
    clear_state(user_id)

    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (user_id,username,display_name,product_id,product_name,rating,review,type,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, username, display, product_id, prod_name, rating, review_text, "product", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    s      = get_settings()
    banner = s.get("bot_banner_image","") or CYBER_IMAGE
    review_msg = (
        f"⭐ *Product Review*\n\n"
        f"📦 *{prod_name}*\n"
        f"👤 {display} (`{user_id}`)\n"
        f"{stars} *{rating}/5*\n\n"
        f"💬 _{review_text}_\n\n_{COMPANY}_"
    )
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=banner, caption=review_msg, parse_mode="Markdown")
    except:
        pass

    await update.message.reply_text(
        f"✅ *Review submitted! Thank you* {stars}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([home_row()])
    )

# ══════════════════════════════════════════════
#   OTHER SECTIONS
# ══════════════════════════════════════════════
async def show_links(query, context):
    text = "🔗 *Our Links*\n\nFind us on all platforms 👇"
    buttons = [
        [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP)],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        [InlineKeyboardButton("🌐 Portfolio", url=PORTFOLIO)],
        [InlineKeyboardButton("✈ Telegram", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        home_row(),
        me_row(),
    ]
    await send_banner(query, context, text, buttons, "links")

async def show_about(query, context):
    text = (
        f"ℹ️ *About {BOT_NAME}*\n\n"
        f"🏙 *{COMPANY}*\n_{TAGLINE}_\n\n"
        f"We offer:\n"
        f"• 📦 Digital products\n"
        f"• 🎓 Educational materials\n"
        f"• 💻 Tech gadgets\n"
        f"• 🛠 Development services\n\n"
        f"📲 Bot: {BOT_HANDLE}\n"
        f"📞 Admin: {ADMIN_TG}\n"
        f"🌐 Portfolio: {PORTFOLIO}"
    )
    buttons = [
        [InlineKeyboardButton("🛍 Shop Now", callback_data="shop")],
        [InlineKeyboardButton("🌐 Portfolio", url=PORTFOLIO)],
        home_row(),
        me_row(),
    ]
    await send_banner(query, context, text, buttons, "about")

async def show_contact(query, context):
    text = (
        f"📞 *Contact Us*\n\n"
        f"We're always available to help!\n\n"
        f"💬 WhatsApp: +1 (780) 851-8629\n"
        f"✈ Telegram: {ADMIN_TG}\n"
        f"📸 Instagram: @skyline_tech\n\n"
        f"_Response time: Usually within minutes_ ⚡"
    )
    buttons = [
        [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP),
         InlineKeyboardButton("✈ Telegram", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM)],
        home_row(),
        [me_button()],
    ]
    await send_banner(query, context, text, buttons, "contact")

async def show_group_chat(query, context):
    s          = get_settings()
    group_link = s.get("group_chat_link","")
    if group_link:
        text = (
            "💬 *Community Group Chat*\n\n"
            "Join our community!\n\n"
            "🌟 _Connect with other customers_\n"
            "💡 _Share tips and feedback_\n"
            "🛍 _Get exclusive deals_"
        )
        buttons = [
            [InlineKeyboardButton("💬 Join Group", url=group_link)],
            home_row(),
        ]
    else:
        text    = "💬 *Community Group Chat*\n\n_Coming soon! Check back later._"
        buttons = [home_row()]
    await send_banner(query, context, text, buttons, "group")

# ══════════════════════════════════════════════
#   DAILY QUOTES
# ══════════════════════════════════════════════
QUOTES = {
    "morning": [
        "🌅 *Good Morning!* Rise and shine — today is a new opportunity to grow. 💪\n\n_Skyline Technologies_",
        "🌄 *Morning Motivation!* The secret of getting ahead is getting started. 🚀\n\n_Dev Clin_",
        "☀️ *Good Morning!* Every day is a chance to be better than yesterday. 🌟\n\n_Skyline Technologies_",
    ],
    "afternoon": [
        "☀️ *Good Afternoon!* Keep pushing — you are halfway there. Stay focused! 🎯\n\n_Skyline Technologies_",
        "🌤 *Afternoon Check-in!* Hard work beats talent when talent doesn't work hard. 💡\n\n_Dev Clin_",
        "💪 *Keep Going!* The afternoon slump is real — but so is your potential. 🔥\n\n_Skyline Technologies_",
    ],
    "evening": [
        "🌇 *Good Evening!* Reflect on today's wins and prepare for tomorrow. 🌟\n\n_Skyline Technologies_",
        "🌆 *Evening Vibes!* You did great today. Rest, recharge, come back stronger. 💫\n\n_Dev Clin_",
    ],
    "night": [
        "🌙 *Good Night!* Sleep well, dream big, wake up ready to conquer tomorrow. 💤\n\n_Skyline Technologies_",
        "✨ *Night Thoughts!* The harder you work, the greater you'll feel when you achieve it. 🌙\n\n_Dev Clin_",
    ],
}

async def send_scheduled_quote(context: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    if s.get("quotes_enabled","1") != "1":
        return
    import datetime as _dt
    hour = _dt.datetime.utcnow().hour
    if hour == 3:    qt = "morning"
    elif hour == 9:  qt = "afternoon"
    elif hour == 12: qt = "evening"
    elif hour == 18: qt = "night"
    else: return
    quote = _random.choice(QUOTES[qt])
    conn  = get_db()
    users = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["telegram_id"], text=quote, parse_mode="Markdown")
        except:
            pass

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
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔧 *Admin Panel — Dev Clin*\n\n"
        "📦 *Products:*\n"
        "`/addproduct` — Add product\n"
        "`/listproducts` — List all\n"
        "`/editlink <id> <link>` — Set file link\n"
        "`/toggleproduct <id>` — Enable/disable\n\n"
        "📂 *Categories:*\n"
        "`/addcategory <id> <icon> <label>`\n"
        "`/listcategories`\n\n"
        "💬 *Users:*\n"
        "`/users` — List users\n"
        "`/msg <user_id> <message>` — Message user\n"
        "`/orders` — Recent orders\n"
        "`/stats` — Statistics\n\n"
        "📢 *Broadcast:*\n"
        "`/broadcast <message>`",
        parse_mode="Markdown"
    )

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_orders   = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    verified_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='verified'").fetchone()[0]
    active_products = conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
    inquiries      = conn.execute("SELECT COUNT(*) FROM service_inquiries WHERE replied=0").fetchone()[0]
    conn.close()
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Users: *{total_users}*\n"
        f"📦 Active Products: *{active_products}*\n"
        f"🛒 Total Orders: *{total_orders}*\n"
        f"✅ Verified Payments: *{verified_orders}*\n"
        f"📩 Pending Inquiries: *{inquiries}*",
        parse_mode="Markdown"
    )

@admin_only
async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_products(active_only=False)
    if not products:
        await update.message.reply_text("No products.")
        return
    text = "📦 *All Products:*\n\n"
    for p in products:
        s = "✅" if p["active"] else "❌"
        text += f"{s} `{p['id']}` {p['icon']} *{p['name']}* — {p['price']}\nLink: {'✅' if p['link'] else '❌ Not set'}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/editlink <product_id> <link>`", parse_mode="Markdown")
        return
    pid  = args[0]
    link = " ".join(args[1:])
    conn = get_db()
    c    = conn.execute("UPDATE products SET link=? WHERE id=?", (link, pid))
    conn.commit()
    conn.close()
    if c.rowcount:
        await update.message.reply_text(f"✅ Link updated for `{pid}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Product `{pid}` not found.", parse_mode="Markdown")

@admin_only
async def admin_toggle_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/toggleproduct <id>`", parse_mode="Markdown")
        return
    pid  = args[0]
    conn = get_db()
    row  = conn.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        await update.message.reply_text(f"❌ Product `{pid}` not found.", parse_mode="Markdown")
        conn.close()
        return
    new = 0 if row["active"] else 1
    conn.execute("UPDATE products SET active=? WHERE id=?", (new, pid))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"{'✅ Enabled' if new else '❌ Disabled'} `{pid}`.", parse_mode="Markdown")

@admin_only
async def admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *Add Product*\n\nFormat:\n"
        "`/newproduct id|name|category|price|price_value|type|icon|description`\n\n"
        "Example:\n`/newproduct p7|Python Course|videos|KSh 1500|1500|MP4|🎓|Full course`",
        parse_mode="Markdown"
    )

@admin_only
async def admin_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args  = " ".join(context.args)
    parts = args.split("|")
    if len(parts) < 8:
        await update.message.reply_text("❌ Invalid format.", parse_mode="Markdown")
        return
    pid, name, cat, price, pval, ptype, icon, desc = parts[:8]
    try:
        pval = float(pval)
    except:
        pval = 0.0
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, name, cat, price, pval, ptype, desc, "", icon, 1, "", 0)
        )
        conn.commit()
        await update.message.reply_text(f"✅ *{name}* added!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    conn.close()

@admin_only
async def admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: `/addcategory <id> <icon> <label>`", parse_mode="Markdown")
        return
    cid, icon, label = args[0], args[1], " ".join(args[2:])
    conn = get_db()
    try:
        conn.execute("INSERT INTO categories VALUES (?,?,?)", (cid, f"{icon} {label}", icon))
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
    conn  = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()
    if not users:
        await update.message.reply_text("No users yet.")
        return
    text = f"👥 *All Users ({len(users)}):*\n\n"
    for u in users[:25]:
        text += (
            f"• `{u['telegram_id']}` — *{u['username']}*\n"
            f"  🏆 {u['points']} pts | 💰 KSh {u['discount_balance']:,.0f} discount\n\n"
        )
    if len(users) > 25:
        text += f"_...and {len(users)-25} more_"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    rows = conn.execute(
        "SELECT user_id,display_name,product_name,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No orders yet.")
        return
    text = "🛒 *Recent Orders:*\n\n"
    for r in rows:
        s = "✅" if r["status"] == "verified" else "⏳"
        text += f"{s} `{r['user_id']}` — {r['display_name']}\n📦 {r['product_name']} | {r['amount']}\n📅 {r['created_at'][:10]}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def admin_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/msg <user_id> <message>`", parse_mode="Markdown")
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
            text=f"💬 *Message from Admin ({BOT_NAME}):*\n\n{message}",
            parse_mode="Markdown"
        )
        log_message(ADMIN_ID, "Admin", target_id, message, "admin_to_user")
        await update.message.reply_text(f"✅ Sent to `{target_id}`.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

@admin_only
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/broadcast <message>`", parse_mode="Markdown")
        return
    message = " ".join(args)
    conn    = get_db()
    users   = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    sent = failed = 0
    await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u["telegram_id"],
                text=f"📢 *Announcement from {BOT_NAME}:*\n\n{message}\n\n_{COMPANY}_",
                parse_mode="Markdown"
            )
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(
        f"✅ Broadcast complete!\n📤 Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════
#   MESSAGE HANDLER
# ══════════════════════════════════════════════
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text.strip()
    state   = get_state(user_id)

    # Registration states
    if state == REG_USERNAME:
        await handle_reg_username(update, context); return
    if state == REG_PASSWORD:
        await handle_reg_password(update, context); return

    # Dashboard states
    if state == DASH_USERNAME:
        await handle_dash_username(update, context); return
    if state == DASH_PASSWORD:
        await handle_dash_password(update, context); return
    if state == DASH_CHANGE_NAME:
        await handle_change_name(update, context); return

    # Service inquiry
    if state == SERVICE_DESC:
        await handle_service_desc(update, context); return

    # Reviews
    if state == AWAIT_BOT_REVIEW:
        await save_bot_review(update, context, text); return
    if state == AWAIT_PRODUCT_REVIEW:
        await save_product_review(update, context, text); return

    # Payment verification
    if state == AWAIT_MPESA_MSG:
        prod_id = pending_payments.get(user_id)
        prod    = get_product(prod_id) if prod_id else None
        if not prod:
            pending_payments.pop(user_id, None)
            clear_state(user_id)
            return

        user         = get_user(user_id)
        discount_bal = user["discount_balance"] if user else 0
        pvalue       = prod.get("sale_price", 0) or prod.get("price_value", 0)
        final_price  = max(0, pvalue - discount_bal)

        ok, result = parse_mpesa_message(text, final_price)

        if ok:
            pending_payments.pop(user_id, None)
            clear_state(user_id)
            await process_verified_payment(update, context, user_id, prod, result, text)
        else:
            recv_name, recv_num = get_mpesa_settings()
            fail_text = (
                f"❌ *Payment Not Verified*\n\n"
                f"{result}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"*Expected:*\n"
                f"📱 Phone: *{recv_num}*\n"
                f"💰 Amount: *KSh {final_price:,.0f}*\n"
                f"📅 Date: *Today — {datetime.now().strftime('%d/%m/%Y')}*\n\n"
                f"Paste the correct SMS or tap Cancel."
            )
            pending_payments[user_id] = prod_id
            set_state(user_id, AWAIT_MPESA_MSG)
            await update.message.reply_photo(
                photo=CYBER_IMAGE,
                caption=f"{fail_text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"paid_{prod_id}")],
                    [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")],
                ])
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"⚠️ *Failed payment*\n"
                        f"👤 `{user_id}`\n"
                        f"📦 {prod['name']}\n"
                        f"Reason: {escape_md(result[:100])}"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        return

    # Admin shortcut
    if user_id == ADMIN_ID and state is None:
        await update.message.reply_text(
            "👋 Use /admin for commands or /msg <user_id> <message> to contact a user.",
            parse_mode="Markdown"
        )
        return

    # Default: forward to admin
    user    = get_user(user_id)
    display = user["display_name"] if user else update.effective_user.full_name
    username = user["username"] if user else str(user_id)
    log_message(user_id, display, ADMIN_ID, text, "user_to_admin")
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💬 *Message from user:*\n\n"
                f"👤 {display} (@{username})\n"
                f"🆔 `{user_id}`\n\n"
                f"📩 {text}\n\n"
                f"_Reply:_ `/msg {user_id} <reply>`"
            ),
            parse_mode="Markdown"
        )
    except:
        pass
    await update.message.reply_text(
        f"💬 Message forwarded to admin.\n\nOr use /start to open the menu.\n\n_{BOT_NAME} | {COMPANY}_",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════
#   CALLBACK ROUTER
# ══════════════════════════════════════════════
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    # Require registration for everything except home
    user = get_user(user_id)
    if not user and data != "home":
        await query.message.reply_text(
            "⚠️ Please use /start to register first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Start", callback_data="home")]])
        )
        return

    if data == "home":
        clear_state(user_id)
        pending_payments.pop(user_id, None)
        if get_user(user_id):
            await show_main_menu(query, context)
        else:
            await start(update, context)

    elif data == "shop":           await show_shop(query, context)
    elif data == "services":       await show_services(query, context)
    elif data == "links":          await show_links(query, context)
    elif data == "about":          await show_about(query, context)
    elif data == "contact":        await show_contact(query, context)
    elif data == "group_chat":     await show_group_chat(query, context)
    elif data == "rate_bot":       await show_bot_rating(query, context)
    elif data == "dashboard":      await dashboard_start(query, context)
    elif data == "service_inquiry":await service_inquiry_start(query, context)

    elif data.startswith("cat_"):  await show_category(query, context, data[4:])
    elif data.startswith("prod_"): await show_product(query, context, data[5:])
    elif data.startswith("paid_"): await payment_initiate(query, context, data[5:])

    elif data.startswith("svc_"):
        await service_picked(query, context, int(data[4:]))

    elif data.startswith("my_downloads_"):
        await show_my_downloads(query, context, int(data[13:]))
    elif data.startswith("my_points_"):
        await show_my_points(query, context, int(data[10:]))
    elif data.startswith("change_name_"):
        await start_change_name(query, context, int(data[12:]))

    elif data.startswith("bot_rate_"):
        await handle_bot_rating(query, context, int(data.split("_")[-1]))
    elif data == "skip_bot_review":
        clear_state(user_id)
        user_data_temp.pop(user_id, None)
        await query.message.reply_text(
            "👍 Thanks anyway!",
            reply_markup=InlineKeyboardMarkup([home_row()])
        )

    elif data.startswith("prod_rate_"):
        parts = data.split("_")
        await handle_product_rating(query, context, parts[2], int(parts[3]))
    elif data == "skip_prod_review":
        clear_state(user_id)
        user_data_temp.pop(user_id, None)
        await query.message.reply_text(
            "👍 Enjoy your purchase!",
            reply_markup=InlineKeyboardMarkup([home_row()])
        )

# ══════════════════════════════════════════════
#   INLINE QUERY — product search
# ══════════════════════════════════════════════
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q        = update.inline_query.query.strip().lower()
    products = get_products(active_only=True)
    matches  = [p for p in products if q in p["name"].lower() or q in p["desc"].lower()] if q else products[:8]
    recv_name, recv_num = get_mpesa_settings()
    results = []
    for p in matches[:10]:
        desc_text = (
            f"{p['icon']} {p['name']}\n"
            f"💰 {p['price']} | 📁 {p['type']}\n\n"
            f"{p['desc']}\n\n"
            f"To buy:\n📱 M-Pesa Send Money to {recv_num} ({recv_name})\n"
            f"Then open the bot and confirm payment."
        )
        results.append(
            InlineQueryResultArticle(
                id=str(_uuid.uuid4()),
                title=f"{p['icon']} {p['name']} — {p['price']}",
                description=p["desc"][:80],
                input_message_content=InputTextMessageContent(message_text=desc_text)
            )
        )
    await update.inline_query.answer(results, cache_time=30)

# ══════════════════════════════════════════════
#   /myorders COMMAND
# ══════════════════════════════════════════════
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = get_user(user_id)
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return
    conn = get_db()
    rows = conn.execute(
        "SELECT product_name, amount, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15",
        (user_id,)
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text(
            "🛒 *My Orders*\n\nNo orders yet.\n\nUse /start to browse the shop!",
            parse_mode="Markdown"
        )
        return
    text = f"🛒 *My Orders* — {user['display_name']}\n\n"
    for r in rows:
        icon = "✅" if r["status"] == "verified" else "⏳"
        text += f"{icon} *{r['product_name']}*\n💰 {r['amount']} | 📅 {r['created_at'][:10]}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Shop More", callback_data="shop"),
                                            InlineKeyboardButton("🏠 Home", callback_data="home")]]))

# ══════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",          start))
    app.add_handler(CommandHandler("myorders",       my_orders))
    app.add_handler(CommandHandler("admin",          admin_cmd))
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

    # Inline & callbacks
    app.add_handler(InlineQueryHandler(inline_query_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Scheduled quotes (EAT = UTC+3)
    jq = app.job_queue
    if jq:
        import datetime as _dt
        jq.run_daily(send_scheduled_quote, time=_dt.time(3, 30))
        jq.run_daily(send_scheduled_quote, time=_dt.time(9, 0))
        jq.run_daily(send_scheduled_quote, time=_dt.time(12, 0))
        jq.run_daily(send_scheduled_quote, time=_dt.time(18, 0))

    logger.info(f"🚀 {BOT_NAME} is running...")
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
