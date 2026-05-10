import logging
import os
import json
import re
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

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
MPESA_RECEIVER_NAME   = "Clinton Oduor"       # Name to verify in M-Pesa message
MPESA_RECEIVER_NUMBER = "522533"              # Paybill / Till number to verify
PAYBILL_NAME          = "Skyline Technologies"

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

    conn.commit()

    # Seed default products if table is empty
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
AWAIT_MPESA_MSG    = 1
AWAIT_REPLY_TARGET = 2
AWAIT_REPLY_MSG    = 3
AWAIT_BROADCAST    = 4

# Pending payments: {user_id: product_id}
pending_payments = {}
# Admin reply targets: {admin_id: target_user_id}
admin_reply_targets = {}

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
    try:
        if hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_photo(
                photo=CYBER_IMAGE,
                caption=full_caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update_or_query.edit_message_media(
                media=InputMediaPhoto(media=CYBER_IMAGE, caption=full_caption, parse_mode="Markdown"),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        msg = full_caption
        try:
            if hasattr(update_or_query, 'message') and update_or_query.message:
                await update_or_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e2:
            logger.error(f"send_cyber_footer fallback failed: {e2}")

# ══════════════════════════════════════════════
#   M-PESA VERIFICATION
# ══════════════════════════════════════════════
def parse_mpesa_message(msg: str, expected_amount: float):
    """
    Parse an M-Pesa confirmation SMS and verify:
    - Receiver name contains Clinton Oduor
    - Receiver number matches MPESA_RECEIVER_NUMBER
    - Amount matches expected amount
    - Date is present (today or recent)
    Returns (True, details_dict) or (False, error_reason)
    """
    msg_upper = msg.upper()

    # Check receiver name
    if "CLINTON ODUOR" not in msg_upper:
        return False, f"❌ Receiver name not found. Expected *Clinton Oduor* in the M-Pesa message."

    # Check receiver number / paybill
    if MPESA_RECEIVER_NUMBER not in msg:
        return False, f"❌ Receiver number *{MPESA_RECEIVER_NUMBER}* not found in the message."

    # Extract amount — match patterns like "Ksh500.00" or "KES 500" or "500.00"
    amount_match = re.search(r'[Kk][Ss][Hh]\.?\s*([\d,]+\.?\d*)', msg)
    if not amount_match:
        amount_match = re.search(r'([\d,]+\.?\d*)', msg)

    if not amount_match:
        return False, "❌ Could not read the amount from the message."

    amount_str = amount_match.group(1).replace(",", "")
    try:
        paid_amount = float(amount_str)
    except ValueError:
        return False, "❌ Could not parse the amount from the message."

    if abs(paid_amount - expected_amount) > 1:  # allow KSh 1 tolerance
        return False, (
            f"❌ Amount mismatch!\n\n"
            f"Expected: *KSh {expected_amount:,.0f}*\n"
            f"Found in message: *KSh {paid_amount:,.0f}*\n\n"
            f"Please pay the correct amount and try again."
        )

    # Extract date
    date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', msg)
    date_str = date_match.group(0) if date_match else "N/A"

    return True, {
        "amount": paid_amount,
        "date": date_str,
        "receiver": MPESA_RECEIVER_NAME,
        "number": MPESA_RECEIVER_NUMBER,
    }

# ══════════════════════════════════════════════
#   /start  — MAIN MENU
# ══════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    keyboard = [
        [InlineKeyboardButton("🛍 Shop",       callback_data="shop"),
         InlineKeyboardButton("🛠 Services",   callback_data="services")],
        [InlineKeyboardButton("🔗 Links",      callback_data="links"),
         InlineKeyboardButton("ℹ About",       callback_data="about")],
        [me_button(), InlineKeyboardButton("📞 Contact", callback_data="contact")],
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

    text = (
        f"{prod['icon']} *{prod['name']}*\n\n"
        f"💰 *Price:* {prod['price']}\n"
        f"📁 *Type:* {prod['type']}\n\n"
        f"{prod['desc']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Payment via M-Pesa:*\n"
        f"📱 Paybill/Till: *{MPESA_RECEIVER_NUMBER}*\n"
        f"👤 Account Name: *{MPESA_RECEIVER_NAME}*\n"
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

    user_id = query.from_user.id
    pending_payments[user_id] = prod_id

    text = (
        f"📲 *M-Pesa Payment Verification*\n\n"
        f"📦 Product: *{prod['name']}*\n"
        f"💰 Amount: *{prod['price']}*\n\n"
        f"Please send the full M-Pesa confirmation SMS you received after paying.\n\n"
        f"_Example format:_\n"
        f"`ABC123DE confirmed. Ksh500.00 sent to {MPESA_RECEIVER_NAME} {MPESA_RECEIVER_NUMBER} on 10/5/24...`\n\n"
        f"Just paste the message below 👇"
    )

    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")],
    ]
    await send_cyber_footer(query, context, text, buttons)
    context.user_data["awaiting_mpesa"] = True

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
        f"• 💻 Tech gadgets\n• 🛠 Development services\n\n"
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

# ══════════════════════════════════════════════
#   ADMIN — DIRECT MESSAGE TO CLIENT
# ══════════════════════════════════════════════
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

# ══════════════════════════════════════════════
#   ADMIN — BROADCAST
# ══════════════════════════════════════════════
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
#   MESSAGE HANDLER (M-Pesa + user replies)
# ══════════════════════════════════════════════
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    # If admin is using /msg, handled separately
    if user.id == ADMIN_ID:
        # Forward any admin reply to the last user who messaged admin
        # (Admin can also use /msg command for direct messaging)
        await update.message.reply_text(
            "👋 Use /admin for the admin panel or /msg <user_id> <message> to contact a user.",
            parse_mode="Markdown"
        )
        return

    # Check if user has a pending payment
    if user.id in pending_payments:
        prod_id = pending_payments[user.id]
        prod = get_product(prod_id)
        if not prod:
            del pending_payments[user.id]
            return

        # Verify M-Pesa message
        ok, result = parse_mpesa_message(text, prod["price_value"])

        if ok:
            # Payment verified!
            del pending_payments[user.id]
            context.user_data["awaiting_mpesa"] = False
            save_order(user, prod, mpesa_msg=text, status="verified")

            # Notify admin
            admin_msg = (
                f"✅ *PAYMENT VERIFIED!*\n\n"
                f"👤 User: {user.full_name}\n"
                f"🔗 Handle: @{user.username or 'N/A'}\n"
                f"🆔 ID: `{user.id}`\n\n"
                f"📦 Product: *{prod['name']}*\n"
                f"💰 Amount: *{prod['price']}*\n"
                f"📅 Date: {result['date']}\n\n"
                f"M-Pesa msg:\n`{text[:200]}`\n\n"
                f"{'✅ File link set — auto-sending.' if prod['link'] else '⚠️ No file link set. Send manually!'}"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Admin notify failed: {e}")

            # Send file or notify
            if prod["link"]:
                confirm = (
                    f"✅ *Payment Verified!*\n\n"
                    f"Thank you, {user.first_name}! Your file is ready 🎉\n\n"
                    f"📦 *{prod['name']}*"
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
                try:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=prod["link"],
                        caption=f"📦 {prod['name']} — Enjoy! 🚀\n\n_{BOT_NAME} | {COMPANY}_",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"File send error: {e}")
                    await context.bot.send_message(chat_id=user.id, text=f"📎 Download: {prod['link']}")
            else:
                confirm = (
                    f"✅ *Payment Verified!*\n\n"
                    f"Thank you! The admin has been notified and will send your file shortly. ⏳\n\n"
                    f"📦 *{prod['name']}*\n\n"
                    f"If you don't receive it within 10 minutes, contact us below 👇"
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
            # Verification failed — tell user why
            fail_text = (
                f"⚠️ *Payment Verification Failed*\n\n"
                f"{result}\n\n"
                f"Please check and paste the correct M-Pesa message, or contact admin for help."
            )
            buttons = [
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_TG.replace('@','')}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"prod_{prod_id}")],
            ]
            await update.message.reply_photo(
                photo=CYBER_IMAGE,
                caption=f"{fail_text}\n\n━━━━━━━━━━━━━━━━\n{ME_BIO}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            # Also notify admin of failed attempt
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ *Failed payment attempt*\n👤 {user.full_name} (@{user.username or 'N/A'}) `{user.id}`\n📦 {prod['name']}\n\nMessage:\n`{text[:200]}`",
                    parse_mode="Markdown"
                )
            except:
                pass
        return

    # Forward user messages to admin inbox
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

    if data == "home":
        await start(update, context)
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

# ══════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("listproducts", admin_list_products))
    app.add_handler(CommandHandler("editlink", admin_edit_link))
    app.add_handler(CommandHandler("toggleproduct", admin_toggle_product))
    app.add_handler(CommandHandler("addproduct", admin_add_product))
    app.add_handler(CommandHandler("newproduct", admin_new_product))
    app.add_handler(CommandHandler("addcategory", admin_add_category))
    app.add_handler(CommandHandler("listcategories", admin_list_categories))
    app.add_handler(CommandHandler("users", admin_list_users))
    app.add_handler(CommandHandler("msg", admin_message_user))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("orders", admin_orders))

    # Callback & messages
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info(f"🚀 {BOT_NAME} bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
