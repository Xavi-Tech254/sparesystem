"""
Dev Clin Bot — Web Admin Panel
Run with: python admin_panel.py
Access at: http://localhost:5000/admin
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, flash
import sqlite3
import json
import hashlib
import os
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = "devclin_secret_2024_change_this"

# ══════════════════════════════════════════════
#   CONFIG
# ══════════════════════════════════════════════
DB_PATH       = "devclin.db"
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "8589728931:AAFTJDW94p_BOTr-q6AXua-hunOXmbXNSDQ")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "devclin2024")

# ══════════════════════════════════════════════
#   DB HELPERS
# ══════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    return r.json()

def broadcast_telegram(text):
    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    results = {"sent": 0, "failed": 0}
    for u in users:
        r = send_telegram(u["user_id"], f"📢 *Announcement:*\n\n{text}\n\n_Skyline Technologies_")
        if r.get("ok"):
            results["sent"] += 1
        else:
            results["failed"] += 1
    return results

# ══════════════════════════════════════════════
#   AUTH
# ══════════════════════════════════════════════
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════
#   HTML TEMPLATE
# ══════════════════════════════════════════════
BASE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dev Clin Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
  :root {
    --bg: #0a0a0f;
    --panel: #12121a;
    --border: #1e1e2e;
    --accent: #00ff88;
    --accent2: #7c3aed;
    --danger: #ff4444;
    --warn: #ffaa00;
    --text: #e2e2f0;
    --muted: #6b6b8a;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif; min-height: 100vh; }
  .sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; width: 220px;
    background: var(--panel); border-right: 1px solid var(--border);
    padding: 24px 0; display: flex; flex-direction: column;
    z-index: 1000; transition: transform 0.3s;
  }
  .sidebar.hidden { transform: translateX(-100%); }
  .menu-toggle {
    display: none; position: fixed; top: 12px; left: 12px; z-index: 1100;
    background: var(--accent); color: #000; border: none; border-radius: 8px;
    padding: 8px 12px; font-size: 18px; cursor: pointer; font-weight: 700;
  }
  .overlay {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    z-index: 999;
  }
  .overlay.show { display: block; }
  .logo { padding: 0 20px 24px; border-bottom: 1px solid var(--border); }
  .logo h1 { font-size: 20px; font-weight: 800; color: var(--accent); letter-spacing: -1px; }
  .logo p { font-size: 11px; color: var(--muted); font-family: 'Space Mono', monospace; margin-top: 2px; }
  .nav { flex: 1; padding: 16px 0; }
  .nav a {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 20px; color: var(--muted); text-decoration: none;
    font-size: 13px; font-weight: 700; letter-spacing: 0.3px;
    transition: all 0.2s; border-left: 3px solid transparent;
  }
  .nav a:hover, .nav a.active { color: var(--accent); border-left-color: var(--accent); background: rgba(0,255,136,0.05); }
  .nav .section-label { padding: 16px 20px 6px; font-size: 10px; color: var(--muted); letter-spacing: 2px; font-family: 'Space Mono', monospace; }
  .logout { padding: 16px 20px; }
  .logout a { color: var(--danger); font-size: 13px; text-decoration: none; font-weight: 700; }
  .main { margin-left: 220px; padding: 32px; min-height: 100vh; }
  .page-title { font-size: 28px; font-weight: 800; margin-bottom: 4px; }
  .page-sub { font-size: 13px; color: var(--muted); font-family: 'Space Mono', monospace; margin-bottom: 28px; }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .stat-card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; position: relative; overflow: hidden;
  }
  .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: var(--accent); }
  .stat-card .num { font-size: 36px; font-weight: 800; font-family: 'Space Mono', monospace; color: var(--accent); }
  .stat-card .label { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .stat-card .icon { font-size: 28px; position: absolute; right: 16px; top: 16px; opacity: 0.3; }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 24px; margin-bottom: 24px;
  }
  .card-title { font-size: 16px; font-weight: 800; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px 12px; font-family: 'Space Mono', monospace; font-size: 10px; letter-spacing: 1px; color: var(--muted); border-bottom: 1px solid var(--border); }
  td { padding: 12px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.02); }
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 100px;
    font-size: 11px; font-family: 'Space Mono', monospace; font-weight: 700;
  }
  .badge.green { background: rgba(0,255,136,0.1); color: var(--accent); border: 1px solid rgba(0,255,136,0.3); }
  .badge.red { background: rgba(255,68,68,0.1); color: var(--danger); border: 1px solid rgba(255,68,68,0.3); }
  .badge.yellow { background: rgba(255,170,0,0.1); color: var(--warn); border: 1px solid rgba(255,170,0,0.3); }
  .badge.purple { background: rgba(124,58,237,0.1); color: #a78bfa; border: 1px solid rgba(124,58,237,0.3); }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 700;
    cursor: pointer; border: none; text-decoration: none; font-family: 'Syne', sans-serif;
    transition: all 0.2s;
  }
  .btn-primary { background: var(--accent); color: #000; }
  .btn-primary:hover { background: #00e67a; }
  .btn-danger { background: rgba(255,68,68,0.15); color: var(--danger); border: 1px solid rgba(255,68,68,0.3); }
  .btn-danger:hover { background: rgba(255,68,68,0.25); }
  .btn-ghost { background: rgba(255,255,255,0.05); color: var(--text); border: 1px solid var(--border); }
  .btn-ghost:hover { background: rgba(255,255,255,0.1); }
  .btn-warn { background: rgba(255,170,0,0.15); color: var(--warn); border: 1px solid rgba(255,170,0,0.3); }
  .form-group { margin-bottom: 16px; }
  .form-group label { display: block; font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 6px; font-family: 'Space Mono', monospace; letter-spacing: 0.5px; }
  .form-group input, .form-group select, .form-group textarea {
    width: 100%; padding: 10px 14px; background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); font-size: 14px; font-family: 'Syne', sans-serif;
    outline: none; transition: border 0.2s;
  }
  .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: var(--accent); }
  .form-group textarea { resize: vertical; min-height: 80px; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
  .alert-success { background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.3); color: var(--accent); }
  .alert-error { background: rgba(255,68,68,0.1); border: 1px solid rgba(255,68,68,0.3); color: var(--danger); }
  .divider { height: 1px; background: var(--border); margin: 20px 0; }
  .flex { display: flex; align-items: center; gap: 12px; }
  .flex-between { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .msg-bubble { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px; }
  @media (max-width: 768px) {
    .menu-toggle { display: block; }
    .sidebar { transform: translateX(-100%); }
    .sidebar.show { transform: translateX(0); }
    .main { margin-left: 0; padding: 16px; padding-top: 56px; }
    .stats-grid { grid-template-columns: 1fr 1fr; }
    .form-row { grid-template-columns: 1fr; }
    table { font-size: 11px; }
    th, td { padding: 8px 6px; }
    .page-title { font-size: 22px; }
  }
  .msg-bubble.from-user { border-left: 3px solid var(--accent2); }
  .msg-bubble.from-admin { border-left: 3px solid var(--accent); }
  .msg-meta { font-size: 11px; color: var(--muted); font-family: 'Space Mono', monospace; margin-bottom: 4px; }
  .login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--bg); }
  .login-box { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 40px; width: 360px; }
  .login-box h2 { font-size: 24px; font-weight: 800; margin-bottom: 4px; color: var(--accent); }
  .login-box p { font-size: 13px; color: var(--muted); margin-bottom: 24px; }
</style>
</head>
<body>
{% if session.get('logged_in') %}
<button class="menu-toggle" onclick="document.querySelector('.sidebar').classList.toggle('show');document.querySelector('.overlay').classList.toggle('show')">☰</button>
<div class="overlay" onclick="document.querySelector('.sidebar').classList.remove('show');document.querySelector('.overlay').classList.remove('show')"></div>
<div class="sidebar">
  <div class="logo">
    {% set _logo = get_setting("admin_logo") %}
    {% if _logo %}<img src="{{ _logo }}" style="width:60px;height:60px;border-radius:50%;margin-bottom:8px;object-fit:cover">{% endif %}
    <h1>⚡ Dev Clin</h1>
    <p>ADMIN PANEL</p>
  </div>
  <div class="nav">
    <div class="section-label">OVERVIEW</div>
    <a href="/admin" class="{{ 'active' if page=='dashboard' }}">📊 Dashboard</a>
    <a href="/admin/orders" class="{{ 'active' if page=='orders' }}">🛒 Orders</a>
    <div class="section-label">CATALOG</div>
    <a href="/admin/products" class="{{ 'active' if page=='products' }}">📦 Products</a>
    <a href="/admin/categories" class="{{ 'active' if page=='categories' }}">📂 Categories</a>
    <div class="section-label">USERS</div>
    <a href="/admin/users" class="{{ 'active' if page=='users' }}">👥 Users</a>
    <a href="/admin/messages" class="{{ 'active' if page=='messages' }}">💬 Messages</a>
    <div class="section-label">TOOLS</div>
    <a href="/admin/broadcast" class="{{ 'active' if page=='broadcast' }}">📢 Broadcast</a>
    <a href="/admin/reviews" class="{{ 'active' if page=='reviews' }}">⭐ Reviews</a>
    <a href="/admin/tokens" class="{{ 'active' if page=='tokens' }}">🔗 Download Tokens</a>
    <a href="/admin/settings" class="{{ 'active' if page=='settings' }}">⚙️ Bot Settings</a>
  </div>
  <div class="logout"><a href="/admin/logout">⏎ Logout</a></div>
</div>
{% endif %}
<div class="main">
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div class="alert alert-{{ 'success' if category == 'success' else 'error' }}">{{ message }}</div>
  {% endfor %}
{% endwith %}
{{ content | safe }}
</div>
</body>
</html>"""

def render_page(content, page=""):
    def get_setting(key):
        try:
            conn = get_db(); v = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone(); conn.close(); return v[0] if v else ""
        except: return ""
    return render_template_string(BASE_HTML, content=content, page=page, get_setting=get_setting)

# ══════════════════════════════════════════════
#   NOTIFICATION HELPERS
# ══════════════════════════════════════════════
def notify_all_users(message, image_url=""):
    """Send message to all bot users via Telegram API."""
    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            if image_url:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={"chat_id": u["user_id"], "photo": image_url, "caption": message, "parse_mode": "Markdown"}
                )
            else:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": u["user_id"], "text": message, "parse_mode": "Markdown"}
                )
            if r.json().get("ok"):
                sent += 1
        except: pass
    return sent

def notify_new_product(prod_id, name, price, image_url=""):
    msg = (
        f"🎉🎉 *New Product Alert!* 🎉🎉\n\n"
        f"📦 *{name}*\n"
        f"💰 *Price:* {price}\n\n"
        f"👆 Open the bot to purchase now!\n\n"
        f"_Skyline Technologies_"
    )
    notify_all_users(msg, image_url)

def notify_price_drop(prod_id, name, old_price, new_price, image_url=""):
    drop_pct = int(((old_price - new_price) / old_price) * 100) if old_price else 0
    msg = (
        f"🔥💥 *PRICE DROP ALERT!* 💥🔥\n\n"
        f"📦 *{name}*\n"
        f"💰 Was: ~~KSh {old_price:,.0f}~~\n"
        f"🎯 Now: *KSh {new_price:,.0f}*\n"
        f"📉 *{drop_pct}% OFF!*\n\n"
        f"⚡ Grab it now before it ends!\n\n"
        f"_Skyline Technologies_"
    )
    notify_all_users(msg, image_url)

# ══════════════════════════════════════════════
#   ROUTES
# ══════════════════════════════════════════════
@app.route("/download/<token>")
def download_file(token):
    """One-time download link handler. Burns token after first use."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM download_tokens WHERE token=?", (token,)
    ).fetchone()

    if not row:
        conn.close()
        return "<h2 style='font-family:sans-serif;color:#c00'>❌ Invalid download link.</h2>", 404

    from datetime import datetime
    if row["used"]:
        conn.close()
        return "<h2 style='font-family:sans-serif;color:#c00'>❌ This link has already been used. Each link works once only.</h2>", 403

    if datetime.now().isoformat() > row["expires_at"]:
        conn.close()
        return "<h2 style='font-family:sans-serif;color:#c00'>❌ This link has expired (24hr limit). Contact admin for help.</h2>", 410

    # Burn the token immediately
    conn.execute("UPDATE download_tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()

    file_url = row["file_url"]

    # If it's a direct URL, redirect to it
    if file_url.startswith("http"):
        return redirect(file_url)

    # If it's a Telegram file_id, show instructions
    return f"""
    <html><head><title>Download Ready</title>
    <style>body{{font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center}}
    .box{{background:#f0fff4;border:2px solid #00c853;border-radius:12px;padding:32px}}
    h2{{color:#00c853}}p{{color:#555}}code{{background:#eee;padding:4px 8px;border-radius:4px}}</style>
    </head><body>
    <div class="box">
    <h2>✅ Download Ready</h2>
    <p>Your file ID: <code>{file_url}</code></p>
    <p>This link has now been used and cannot be reused.</p>
    <p>If this is a Telegram file, open the bot to retrieve it directly.</p>
    </div></body></html>
    """


@app.route("/admin/tokens")
@login_required
def download_tokens_view():
    """Admin view of all download tokens."""
    conn = get_db()
    tokens = conn.execute(
        "SELECT t.*, u.full_name FROM download_tokens t "
        "LEFT JOIN users u ON t.user_id = u.user_id "
        "ORDER BY t.created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()

    rows = ""
    for t in tokens:
        status = '<span style="color:#00c853">✅ Used</span>' if t["used"] else (
            '<span style="color:#ff9800">⏳ Active</span>'
        )
        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:11px">{t['token'][:20]}...</td>
          <td>{t['full_name'] or t['user_id']}</td>
          <td>{t['product_id']}</td>
          <td>{status}</td>
          <td style="font-size:11px;color:#888">{t['expires_at'][:16]}</td>
          <td style="font-size:11px;color:#888">{t['created_at'][:16]}</td>
        </tr>"""

    content = f"""
    <div class="page-title">Download Tokens</div>
    <div class="page-sub">One-time download links issued to customers</div>
    <div class="card">
      <table>
        <tr><th>TOKEN</th><th>USER</th><th>PRODUCT</th><th>STATUS</th><th>EXPIRES</th><th>CREATED</th></tr>
        {rows if rows else '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--muted)">No tokens yet</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "tokens")


@app.route("/")
def root():
    return redirect("/admin")

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USERNAME and
                request.form.get("password") == ADMIN_PASSWORD):
            session["logged_in"] = True
            return redirect("/admin")
        flash("Invalid credentials", "error")
    content = """
    <div class="login-page">
      <div class="login-box">
        <h2>⚡ Dev Clin</h2>
        <p>Admin Panel — Skyline Technologies</p>
        <form method="POST">
          <div class="form-group">
            <label>USERNAME</label>
            <input type="text" name="username" placeholder="admin" required>
          </div>
          <div class="form-group">
            <label>PASSWORD</label>
            <input type="password" name="password" placeholder="••••••••" required>
          </div>
          <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;">Login →</button>
        </form>
      </div>
    </div>"""
    return render_template_string(BASE_HTML, content=content, page="login")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin/login")

@app.route("/admin")
@login_required
def dashboard():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    verified_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='verified'").fetchone()[0]
    active_products = conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
    recent_orders = conn.execute(
        "SELECT user_id,full_name,product_name,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 8"
    ).fetchall()
    conn.close()

    orders_html = ""
    for o in recent_orders:
        badge = "green" if o["status"] == "verified" else "yellow"
        orders_html += f"""
        <tr>
          <td>{o['full_name']}</td>
          <td>{o['product_name']}</td>
          <td>{o['amount']}</td>
          <td><span class="badge {badge}">{o['status'].upper()}</span></td>
          <td style="color:var(--muted);font-family:'Space Mono',monospace;font-size:11px">{o['created_at'][:16]}</td>
        </tr>"""

    content = f"""
    <div class="page-title">Dashboard</div>
    <div class="page-sub">Welcome back, Admin ⚡</div>
    <div class="stats-grid">
      <div class="stat-card"><div class="icon">👥</div><div class="num">{total_users}</div><div class="label">Total Users</div></div>
      <div class="stat-card"><div class="icon">📦</div><div class="num">{active_products}</div><div class="label">Active Products</div></div>
      <div class="stat-card"><div class="icon">🛒</div><div class="num">{total_orders}</div><div class="label">Total Orders</div></div>
      <div class="stat-card"><div class="icon">✅</div><div class="num">{verified_orders}</div><div class="label">Verified Payments</div></div>
    </div>
    <div class="card">
      <div class="card-title">🛒 Recent Orders</div>
      <table>
        <tr><th>CUSTOMER</th><th>PRODUCT</th><th>AMOUNT</th><th>STATUS</th><th>DATE</th></tr>
        {orders_html if orders_html else '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">No orders yet</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "dashboard")

@app.route("/admin/products", methods=["GET", "POST"])
@login_required
def products():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            pid        = request.form.get("id")
            name       = request.form.get("name")
            cat        = request.form.get("category")
            price      = request.form.get("price")
            price_val  = float(request.form.get("price_value", 0))
            sale_price = float(request.form.get("sale_price", 0) or 0)
            image_url  = request.form.get("image_url", "").strip()
            ptype      = request.form.get("type")
            icon       = request.form.get("icon", "📦")
            desc       = request.form.get("desc")
            link       = request.form.get("link", "")
            try:
                conn.execute(
                    "INSERT INTO products (id,name,category,price,price_value,type,desc,link,icon,active,image_url,sale_price) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, name, cat, price, price_val, ptype, desc, link, icon, 1, image_url, sale_price)
                )
                conn.commit()
                # Notify all users about new product
                notify_new_product(pid, name, price, image_url)
                flash(f"Product '{name}' added! Users notified. ✅", "success")
            except Exception as e:
                flash(f"Error: {e}", "error")
        elif action == "update_link":
            pid = request.form.get("id")
            link = request.form.get("link")
            conn.execute("UPDATE products SET link=? WHERE id=?", (link, pid))
            conn.commit()
            flash("Link updated!", "success")
        elif action == "price_drop":
            pid        = request.form.get("id")
            sale_price = float(request.form.get("sale_price", 0) or 0)
            conn.execute("UPDATE products SET sale_price=? WHERE id=?", (sale_price, pid))
            conn.commit()
            row = conn.execute("SELECT name,price,price_value,image_url FROM products WHERE id=?", (pid,)).fetchone()
            if row and sale_price > 0 and sale_price < (row["price_value"] or 0):
                notify_price_drop(pid, row["name"], row["price_value"], sale_price, row["image_url"] or "")
            flash("Sale price updated! Users notified. ✅", "success")
        elif action == "toggle":
            pid = request.form.get("id")
            row = conn.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
            if row:
                conn.execute("UPDATE products SET active=? WHERE id=?", (0 if row["active"] else 1, pid))
                conn.commit()
                flash("Product status toggled.", "success")
        elif action == "delete":
            pid = request.form.get("id")
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            flash("Product deleted.", "success")

    prods = conn.execute("SELECT * FROM products ORDER BY category").fetchall()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    cat_options = "".join(f'<option value="{c["id"]}">{c["label"]}</option>' for c in cats)

    rows = ""
    for p in prods:
        active_badge = '<span class="badge green">ACTIVE</span>' if p["active"] else '<span class="badge red">HIDDEN</span>'
        link_badge = '<span class="badge green">SET</span>' if p["link"] else '<span class="badge red">MISSING</span>'
        rows += f"""
        <tr>
          <td><code style="font-family:'Space Mono',monospace;font-size:11px">{p['id']}</code></td>
          <td>{p['icon']} <strong>{p['name']}</strong></td>
          <td><span class="badge purple">{p['category']}</span></td>
          <td>{p['price']}</td>
          <td>{p['type']}</td>
          <td>{link_badge}</td>
          <td>{active_badge}</td>
          <td>
            <div class="flex">
              <form method="POST" style="display:inline" onsubmit="return confirm('Delete this product?')">
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="id" value="{p['id']}">
                <button type="submit" class="btn btn-danger" style="padding:4px 10px;font-size:11px">🗑 Delete</button>
              </form>
              <form method="POST" style="display:inline">
                <input type="hidden" name="action" value="toggle">
                <input type="hidden" name="id" value="{p['id']}">
                <button type="submit" class="btn btn-warn" style="padding:4px 10px;font-size:11px">Toggle</button>
              </form>
              <button class="btn btn-ghost" style="padding:4px 10px;font-size:11px"
                onclick="document.getElementById('link-form-{p['id']}').style.display='block'">✏ Link</button>
              <button class="btn btn-warn" style="padding:4px 10px;font-size:11px"
                onclick="document.getElementById('drop-form-{p['id']}').style.display='block'">💸 Drop</button>
            </div>
            <div id="link-form-{p['id']}" style="display:none;margin-top:8px">
              <form method="POST" style="display:flex;gap:6px">
                <input type="hidden" name="action" value="update_link">
                <input type="hidden" name="id" value="{p['id']}">
                <input type="text" name="link" value="{p['link'] or ''}" placeholder="Drive link / file_id" style="flex:1;padding:6px 10px;font-size:12px">
                <button type="submit" class="btn btn-primary" style="padding:6px 12px;font-size:12px">Save</button>
              </form>
            </div>
            <div id="drop-form-{p['id']}" style="display:none;margin-top:8px">
              <form method="POST" style="display:flex;gap:6px;align-items:center">
                <input type="hidden" name="action" value="price_drop">
                <input type="hidden" name="id" value="{p['id']}">
                <input type="number" name="sale_price" value="{p['sale_price'] or ''}" placeholder="Sale price (0 = no drop)" style="flex:1;padding:6px 10px;font-size:12px">
                <button type="submit" class="btn btn-primary" style="padding:6px 12px;font-size:12px">Set Drop</button>
              </form>
            </div>
          </td>
        </tr>"""

    content = f"""
    <div class="page-title">Products</div>
    <div class="page-sub">Manage your product catalog</div>
    <div class="card">
      <div class="card-title">➕ Add New Product</div>
      <form method="POST">
        <input type="hidden" name="action" value="add">
        <div class="form-row">
          <div class="form-group"><label>PRODUCT ID</label><input name="id" placeholder="p7" required></div>
          <div class="form-group"><label>ICON</label><input name="icon" placeholder="📦" value="📦"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>NAME</label><input name="name" placeholder="Product name" required></div>
          <div class="form-group"><label>CATEGORY</label>
            <select name="category">{cat_options}</select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>PRICE LABEL</label><input name="price" placeholder="KSh 500" required></div>
          <div class="form-group"><label>PRICE VALUE (for M-Pesa)</label><input name="price_value" type="number" placeholder="500" required></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>SALE PRICE (leave 0 if no discount)</label><input name="sale_price" type="number" placeholder="0" value="0"></div>
          <div class="form-group"><label>PRODUCT IMAGE URL (optional)</label><input name="image_url" placeholder="https://i.postimg.cc/..."></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>TYPE</label>
            <select name="type"><option>PDF</option><option>DOCX</option><option>APK</option><option>MP3</option><option>MP4</option><option>PRODUCT</option><option>ZIP</option><option>OTHER</option></select>
          </div>
          <div class="form-group"><label>FILE LINK (optional)</label><input name="link" placeholder="Google Drive / Telegram file_id"></div>
        </div>
        <div class="form-group"><label>DESCRIPTION</label><textarea name="desc" placeholder="Product description..." required></textarea></div>
        <button type="submit" class="btn btn-primary">➕ Add Product</button>
      </form>
    </div>
    <div class="card">
      <div class="card-title">📦 All Products</div>
      <table>
        <tr><th>ID</th><th>NAME</th><th>CATEGORY</th><th>PRICE</th><th>TYPE</th><th>LINK</th><th>STATUS</th><th>ACTIONS</th></tr>
        {rows if rows else '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">No products</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "products")

@app.route("/admin/categories", methods=["GET", "POST"])
@login_required
def categories():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            cid = request.form.get("id")
            icon = request.form.get("icon")
            label = request.form.get("label")
            try:
                conn.execute("INSERT INTO categories VALUES (?,?,?)", (cid, f"{icon} {label}", icon))
                conn.commit()
                flash(f"Category '{label}' added!", "success")
            except Exception as e:
                flash(f"Error: {e}", "error")
        elif action == "delete":
            cid = request.form.get("id")
            conn.execute("DELETE FROM categories WHERE id=?", (cid,))
            conn.commit()
            flash("Category deleted.", "success")

    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    rows = ""
    for c in cats:
        rows += f"""
        <tr>
          <td><code style="font-family:'Space Mono',monospace">{c['id']}</code></td>
          <td>{c['icon']}</td>
          <td>{c['label']}</td>
          <td>
            <form method="POST" style="display:inline" onsubmit="return confirm('Delete this category?')">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="id" value="{c['id']}">
              <button type="submit" class="btn btn-danger" style="padding:4px 10px;font-size:11px">Delete</button>
            </form>
          </td>
        </tr>"""

    content = f"""
    <div class="page-title">Categories</div>
    <div class="page-sub">Manage product categories</div>
    <div class="card">
      <div class="card-title">➕ Add Category</div>
      <form method="POST">
        <input type="hidden" name="action" value="add">
        <div class="form-row">
          <div class="form-group"><label>CATEGORY ID</label><input name="id" placeholder="ebooks" required></div>
          <div class="form-group"><label>ICON</label><input name="icon" placeholder="📖" required></div>
        </div>
        <div class="form-group"><label>LABEL</label><input name="label" placeholder="E-Books" required></div>
        <button type="submit" class="btn btn-primary">➕ Add Category</button>
      </form>
    </div>
    <div class="card">
      <div class="card-title">📂 All Categories</div>
      <table>
        <tr><th>ID</th><th>ICON</th><th>LABEL</th><th>ACTIONS</th></tr>
        {rows if rows else '<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted)">No categories</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "categories")

@app.route("/admin/users")
@login_required
def users():
    conn = get_db()
    users_list = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()

    rows = ""
    for u in users_list:
        uname = f"@{u['username']}" if u["username"] else "—"
        rows += f"""
        <tr>
          <td><code style="font-family:'Space Mono',monospace">{u['user_id']}</code></td>
          <td>{u['full_name']}</td>
          <td style="color:var(--muted)">{uname}</td>
          <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted)">{u['joined_at'][:16]}</td>
          <td><a href="/admin/messages?user_id={u['user_id']}" class="btn btn-ghost" style="padding:4px 10px;font-size:11px">💬 Message</a></td>
        </tr>"""

    content = f"""
    <div class="page-title">Users</div>
    <div class="page-sub">{len(users_list)} registered users</div>
    <div class="card">
      <table>
        <tr><th>ID</th><th>NAME</th><th>USERNAME</th><th>JOINED</th><th>ACTION</th></tr>
        {rows if rows else '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">No users yet</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "users")

@app.route("/admin/messages", methods=["GET", "POST"])
@login_required
def messages():
    user_id = request.args.get("user_id") or request.form.get("user_id")
    conn = get_db()

    if request.method == "POST" and request.form.get("action") == "send":
        target_id = int(request.form.get("user_id"))
        msg = request.form.get("message")
        r = send_telegram(target_id, f"💬 *Message from Admin (Dev Clin):*\n\n{msg}\n\n_Reply to this message to respond._")
        if r.get("ok"):
            conn.execute("INSERT INTO messages (from_user_id,from_name,to_user_id,message,direction,created_at) VALUES (?,?,?,?,?,?)",
                         (0, "Admin", target_id, msg, "admin_to_user", datetime.now().isoformat()))
            conn.commit()
            flash("Message sent!", "success")
        else:
            flash(f"Failed: {r.get('description', 'Unknown error')}", "error")

    msgs = []
    user_info = None
    if user_id:
        msgs = conn.execute(
            "SELECT * FROM messages WHERE from_user_id=? OR to_user_id=? ORDER BY created_at",
            (user_id, user_id)
        ).fetchall()
        user_info = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

    all_users = conn.execute("SELECT user_id, full_name, username FROM users").fetchall()
    conn.close()

    user_opts = "".join(f'<option value="{u["user_id"]}" {"selected" if str(u["user_id"])==str(user_id) else ""}>{u["full_name"]} ({u["user_id"]})</option>' for u in all_users)

    msgs_html = ""
    for m in msgs:
        is_admin = m["direction"] == "admin_to_user"
        cls = "from-admin" if is_admin else "from-user"
        sender = "Admin" if is_admin else m["from_name"]
        msgs_html += f"""
        <div class="msg-bubble {cls}">
          <div class="msg-meta">{'🔧 ' if is_admin else '👤 '}{sender} · {m['created_at'][:16]}</div>
          <div>{m['message']}</div>
        </div>"""

    reply_form = ""
    if user_id:
        reply_form = f"""
        <div class="divider"></div>
        <form method="POST">
          <input type="hidden" name="action" value="send">
          <input type="hidden" name="user_id" value="{user_id}">
          <div class="form-group">
            <label>YOUR MESSAGE TO {user_info['full_name'].upper() if user_info else user_id}</label>
            <textarea name="message" placeholder="Type your reply..." required></textarea>
          </div>
          <button type="submit" class="btn btn-primary">📤 Send Message</button>
        </form>"""

    content = f"""
    <div class="page-title">Messages</div>
    <div class="page-sub">Talk directly to clients</div>
    <div class="card">
      <div class="card-title">Select User</div>
      <form method="GET" style="display:flex;gap:12px;align-items:flex-end">
        <div class="form-group" style="flex:1;margin:0">
          <label>USER</label>
          <select name="user_id">{user_opts}</select>
        </div>
        <button type="submit" class="btn btn-primary">Load Chat →</button>
      </form>
    </div>
    <div class="card">
      <div class="card-title">💬 Conversation</div>
      {msgs_html if msgs_html else '<p style="color:var(--muted);font-size:13px">No messages yet. Select a user above.</p>'}
      {reply_form}
    </div>"""
    return render_page(content, "messages")

@app.route("/admin/orders")
@login_required
def orders():
    conn = get_db()
    orders_list = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()

    rows = ""
    for o in orders_list:
        badge = "green" if o["status"] == "verified" else "yellow"
        rows += f"""
        <tr>
          <td><code style="font-family:'Space Mono',monospace;font-size:11px">{o['id']}</code></td>
          <td>{o['full_name']}<br><span style="font-size:11px;color:var(--muted)">@{o['username'] or 'N/A'} · {o['user_id']}</span></td>
          <td>{o['product_name']}</td>
          <td>{o['amount']}</td>
          <td><span class="badge {badge}">{o['status'].upper()}</span></td>
          <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted)">{o['created_at'][:16]}</td>
          <td><a href="/admin/messages?user_id={o['user_id']}" class="btn btn-ghost" style="padding:4px 10px;font-size:11px">💬</a></td>
        </tr>"""

    content = f"""
    <div class="page-title">Orders</div>
    <div class="page-sub">{len(orders_list)} orders total</div>
    <div class="card">
      <table>
        <tr><th>#</th><th>CUSTOMER</th><th>PRODUCT</th><th>AMOUNT</th><th>STATUS</th><th>DATE</th><th>ACTION</th></tr>
        {rows if rows else '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--muted)">No orders yet</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "orders")

@app.route("/admin/broadcast", methods=["GET", "POST"])
@login_required
def broadcast():
    result = None
    if request.method == "POST":
        message = request.form.get("message")
        result = broadcast_telegram(message)
        flash(f"Broadcast sent! ✅ {result['sent']} delivered, ❌ {result['failed']} failed.", "success")

    content = f"""
    <div class="page-title">Broadcast</div>
    <div class="page-sub">Send a message to all bot users</div>
    <div class="card">
      <div class="card-title">📢 New Broadcast</div>
      <form method="POST">
        <div class="form-group">
          <label>MESSAGE</label>
          <textarea name="message" placeholder="Type your announcement here... (supports Markdown: *bold*, _italic_)" style="min-height:150px" required></textarea>
        </div>
        <p style="font-size:12px;color:var(--muted);margin-bottom:16px">⚠️ This will be sent to ALL users. Use Markdown for formatting.</p>
        <button type="submit" class="btn btn-primary" onclick="return confirm('Send this broadcast to all users?')">📢 Send Broadcast</button>
      </form>
    </div>"""
    return render_page(content, "broadcast")

@app.route("/admin/reviews")
@login_required
def reviews():
    conn = get_db()
    all_reviews = conn.execute(
        "SELECT * FROM reviews ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()

    rows = ""
    for r in all_reviews:
        stars = "⭐" * (r["rating"] or 0)
        badge_color = "purple" if r["type"] == "bot" else "green"
        rows += f"""
        <tr>
          <td>{r['full_name']}<br><span style="font-size:11px;color:var(--muted)">@{r['username'] or 'N/A'}</span></td>
          <td><span class="badge {badge_color}">{r['type'].upper()}</span></td>
          <td>{r['product_name']}</td>
          <td>{stars} ({r['rating']}/5)</td>
          <td style="max-width:200px">{r['review']}</td>
          <td style="font-family:'Space Mono',monospace;font-size:11px;color:var(--muted)">{r['created_at'][:16]}</td>
        </tr>"""

    content = f"""
    <div class="page-title">Reviews</div>
    <div class="page-sub">{len(all_reviews)} reviews total</div>
    <div class="card">
      <table>
        <tr><th>USER</th><th>TYPE</th><th>PRODUCT</th><th>RATING</th><th>REVIEW</th><th>DATE</th></tr>
        {rows if rows else '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--muted)">No reviews yet</td></tr>'}
      </table>
    </div>"""
    return render_page(content, "reviews")

@app.route("/admin/api/stats")
@login_required
def api_stats():
    conn = get_db()
    data = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "verified": conn.execute("SELECT COUNT(*) FROM orders WHERE status='verified'").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0],
    }
    conn.close()
    return jsonify(data)

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def bot_settings():
    global ADMIN_USERNAME, ADMIN_PASSWORD
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "change_password":
            new_user = request.form.get("username")
            new_pass = request.form.get("password")
            if new_user and new_pass:
                ADMIN_USERNAME = new_user
                ADMIN_PASSWORD = new_pass
                flash("Login credentials updated! Set as Railway env vars to make permanent.", "success")
            else:
                flash("Username and password cannot be empty.", "error")
        elif action == "mpesa_settings":
            mpesa_name = request.form.get("mpesa_name", "").strip()
            mpesa_phone = request.form.get("mpesa_phone", "").strip()
            if mpesa_name and mpesa_phone:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('mpesa_name', ?)", (mpesa_name,))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('mpesa_number', ?)", (mpesa_phone,))
                conn.commit()
                flash(f"M-Pesa details updated! Name: {mpesa_name}, Phone: {mpesa_phone}", "success")
            else:
                flash("Name and phone cannot be empty.", "error")
        elif action == "api_keys":
            ai_key       = request.form.get("ai_api_key", "").strip()
            dl_key       = request.form.get("downloader_api_key", "").strip()
            music_key    = request.form.get("music_api_key", "").strip()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_api_key', ?)", (ai_key,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('downloader_api_key', ?)", (dl_key,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('music_api_key', ?)", (music_key,))
            conn.commit()
            flash("API keys saved successfully!", "success")
        elif action == "branding":
            banner = request.form.get("bot_banner_image", "").strip()
            logo   = request.form.get("admin_logo", "").strip()
            group  = request.form.get("group_chat_link", "").strip()
            quotes = "1" if request.form.get("quotes_enabled") else "0"
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('bot_banner_image', ?)", (banner,))
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('admin_logo', ?)", (logo,))
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('group_chat_link', ?)", (group,))
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('quotes_enabled', ?)", (quotes,))
            conn.commit()
            flash("Branding & links updated! ✅", "success")

    # Load current mpesa settings
    settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}
    conn.close()
    mpesa_name   = settings.get("mpesa_name", "Clinton Oduor")
    mpesa_phone  = settings.get("mpesa_number", "0743810633")
    ai_api_key   = settings.get("ai_api_key", "")
    dl_api_key   = settings.get("downloader_api_key", "")
    music_api_key= settings.get("music_api_key", "")

    # Mask keys for display (show only last 6 chars)
    def mask_key(k):
        if not k: return ""
        return "••••••••••••••••" + k[-6:] if len(k) > 6 else k

    ai_placeholder    = "Currently set ✅ — paste to update" if ai_api_key else "sk-ant-api03-..."
    ai_status         = f'<p style="font-size:11px;color:var(--accent);margin-top:4px">✅ Key is set: {mask_key(ai_api_key)}</p>' if ai_api_key else '<p style="font-size:11px;color:var(--danger);margin-top:4px">❌ Not set — AI Assistant will not work</p>'
    dl_placeholder    = "Currently set ✅ — paste to update" if dl_api_key else "AIza..."
    dl_status         = f'<p style="font-size:11px;color:var(--accent);margin-top:4px">✅ Key is set: {mask_key(dl_api_key)}</p>' if dl_api_key else '<p style="font-size:11px;color:var(--muted);margin-top:4px">Optional — without it, Invidious (free) is used for YouTube search</p>'
    music_placeholder = "Currently set ✅ — paste to update" if music_api_key else "Leave blank to use iTunes (free)"
    music_status      = f'<p style="font-size:11px;color:var(--accent);margin-top:4px">✅ Key is set: {mask_key(music_api_key)}</p>' if music_api_key else '<p style="font-size:11px;color:var(--muted);margin-top:4px">Optional — bot uses iTunes Search API (free, no key) by default</p>'

    content = f"""
    <div class="page-title">Settings</div>
    <div class="page-sub">Manage payment details, API keys, and admin credentials</div>

    <div class="card">
      <div class="card-title">🔑 API Keys — AI / Downloader / Music</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:16px">
        Paste your API keys here. They are stored securely in the database and activate instantly in the bot.
        Keys are masked after saving — paste a new value to update.
      </p>
      <form method="POST">
        <input type="hidden" name="action" value="api_keys">
        <div class="form-group">
          <label>🤖 AI API KEY (Anthropic / Claude)</label>
          <input name="ai_api_key" type="password" placeholder="{ai_placeholder}" value="">
          {ai_status}
          <p style="font-size:11px;color:var(--muted);margin-top:4px">Get your key at <a href="https://console.anthropic.com" target="_blank" style="color:var(--accent)">console.anthropic.com</a></p>
        </div>
        <div class="form-group">
          <label>⬇️ DOWNLOADER API KEY (YouTube Data API v3)</label>
          <input name="downloader_api_key" type="password" placeholder="{dl_placeholder}" value="">
          {dl_status}
          <p style="font-size:11px;color:var(--muted);margin-top:4px">Get at <a href="https://console.cloud.google.com" target="_blank" style="color:var(--accent)">console.cloud.google.com</a> → YouTube Data API v3. <br>Downloads use <strong>cobalt.tools</strong> (free, no key needed).</p>
        </div>
        <div class="form-group">
          <label>🎵 MUSIC API KEY (Optional — for premium music APIs)</label>
          <input name="music_api_key" type="password" placeholder="{music_placeholder}" value="">
          {music_status}
          <p style="font-size:11px;color:var(--muted);margin-top:4px">Can be used for Spotify API, Deezer, or other music services in future.</p>
        </div>
        <button type="submit" class="btn btn-primary">💾 Save API Keys</button>
      </form>
    </div>

    <div class="card">
      <div class="card-title">📱 M-Pesa Payment Settings</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:16px">
        These details are shown to customers. <strong>Verification checks phone number + amount only</strong> — name is <em>not</em> checked.
      </p>
      <form method="POST">
        <input type="hidden" name="action" value="mpesa_settings">
        <div class="form-row">
          <div class="form-group">
            <label>RECEIVER NAME (shown to customers)</label>
            <input name="mpesa_name" value="{mpesa_name}" required placeholder="Clinton Oduor">
          </div>
          <div class="form-group">
            <label>PHONE NUMBER (Send Money — verified in SMS)</label>
            <input name="mpesa_phone" value="{mpesa_phone}" required placeholder="0743810633">
          </div>
        </div>
        <button type="submit" class="btn btn-primary">💾 Save M-Pesa Details</button>
      </form>
    </div>

    <div class="card">
      <div class="card-title">🧪 Payment Verifier — Test M-Pesa SMS</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:16px">Paste an M-Pesa SMS below to check if the bot would accept it.</p>
      <div class="form-group">
        <label>PASTE M-PESA SMS HERE</label>
        <textarea id="mpesa-test" placeholder="ABC123DE confirmed. Ksh500.00 sent to Clinton Oduor 0743810633 on 10/5/24 at 3:30 PM..." style="min-height:120px"></textarea>
      </div>
      <button class="btn btn-primary" onclick="testMpesa()">🔍 Test Verification</button>
      <div id="test-result" style="margin-top:16px;display:none"></div>
    </div>

    <div class="card">
      <div class="card-title">🔐 Change Admin Login</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:16px">⚠️ Set <code>ADMIN_USERNAME</code> and <code>ADMIN_PASSWORD</code> in Railway Variables to make permanent.</p>
      <form method="POST">
        <input type="hidden" name="action" value="change_password">
        <div class="form-row">
          <div class="form-group"><label>NEW USERNAME</label><input name="username" value="{ADMIN_USERNAME}" required></div>
          <div class="form-group"><label>NEW PASSWORD</label><input type="password" name="password" placeholder="New password" required></div>
        </div>
        <button type="submit" class="btn btn-primary">💾 Save Credentials</button>
      </form>
    </div>

    <script>
    function testMpesa() {{
      const msg = document.getElementById('mpesa-test').value.trim();
      if (!msg) {{ alert('Please paste an M-Pesa SMS first'); return; }}
      const result = document.getElementById('test-result');
      result.style.display = 'block';

      const phone = "{mpesa_phone}";
      const phone254 = "254" + phone.slice(-9);
      const phone07 = "0" + phone.slice(-9);

      let errors = [];
      let details = {{}};

      details.name = 'ℹ️ Name check: <b>disabled</b> (not required for verification)';

      if (!msg.includes(phone) && !msg.includes(phone254) && !msg.includes(phone07)) {{
        errors.push('❌ Phone number <b>{mpesa_phone}</b> not found in SMS');
      }} else {{
        details.phone = '✅ Phone matched: <b>{mpesa_phone}</b>';
      }}

      const amtMatch = msg.match(/[Kk][Ss][Hh]\.?\s*([\d,]+\.?\d*)/);
      if (amtMatch) {{
        const amt = parseFloat(amtMatch[1].replace(',',''));
        details.amount = '✅ Amount found: <b>KSh ' + amt.toLocaleString() + '</b>';
      }} else {{
        errors.push('❌ Could not find amount (KshXXX) in SMS');
      }}

      const receiptMatch = msg.match(/\b([A-Z0-9]{{8,12}})\b/);
      if (receiptMatch) {{
        details.receipt = '✅ Receipt code: <b>' + receiptMatch[1] + '</b>';
      }} else {{
        details.receipt = '⚠️ No receipt code found (optional)';
      }}

      const dateMatch = msg.match(/\d{{1,2}}\/\d{{1,2}}\/\d{{2,4}}/);
      details.date = dateMatch ? '✅ Date: <b>' + dateMatch[0] + '</b>' : '⚠️ No date found';

      let html = '';
      if (errors.length === 0) {{
        html += '<div style="background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.3);border-radius:8px;padding:16px;margin-bottom:12px">';
        html += '<b style="color:#00ff88">✅ PAYMENT WOULD BE ACCEPTED</b></div>';
      }} else {{
        html += '<div style="background:rgba(255,68,68,0.1);border:1px solid rgba(255,68,68,0.3);border-radius:8px;padding:16px;margin-bottom:12px">';
        html += '<b style="color:#ff4444">❌ PAYMENT WOULD BE REJECTED</b><br><br>' + errors.join('<br>') + '</div>';
      }}

      html += '<div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:16px;font-size:13px;line-height:2">';
      Object.values(details).forEach(d => html += d + '<br>');
      html += '</div>';

      result.innerHTML = html;
    }}
    </script>"""

    content += """
    <div class="card">
      <div class="card-title">🎨 Branding & Links</div>
      <form method="POST">
        <input type="hidden" name="action" value="branding">
        <div class="form-group">
          <label>BOT BANNER IMAGE URL</label>
          <input name="bot_banner_image" value="{banner_img}" placeholder="https://i.postimg.cc/your-image.jpg">
          <small style="color:var(--muted);font-size:11px">Used as bot background image throughout. Upload to postimg.cc and paste URL.</small>
        </div>
        <div class="form-group">
          <label>ADMIN PANEL LOGO URL</label>
          <input name="admin_logo" value="{admin_logo}" placeholder="https://i.postimg.cc/your-logo.jpg">
        </div>
        <div class="form-group">
          <label>GROUP CHAT LINK</label>
          <input name="group_chat_link" value="{group_link}" placeholder="https://t.me/your_group">
        </div>
        <div class="form-group">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="checkbox" name="quotes_enabled" {quotes_checked}> 
            ENABLE DAILY QUOTES (6:30AM, 12PM, 3PM, 9PM)
          </label>
        </div>
        <button type="submit" class="btn btn-primary">💾 Save Branding</button>
      </form>
    </div>""".format(
        banner_img=settings.get("bot_banner_image",""),
        admin_logo=settings.get("admin_logo",""),
        group_link=settings.get("group_chat_link",""),
        quotes_on=settings.get("quotes_enabled","1"),
        quotes_checked="checked" if settings.get("quotes_enabled","1")=="1" else ""
    )
    return render_page(content, "settings")
