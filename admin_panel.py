import os
import sqlite3
import json
import random
import string
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, flash, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devclin_skyline_2025")

DB_PATH   = "devclin.db"
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin1234")
COMPANY   = "Skyline Technologies"
BOT_NAME  = "Dev Clin Market"

# ══════════════════════════════════════════════
#   DB
# ══════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_settings():
    try:
        conn = get_db()
        rows = conn.execute("SELECT key,value FROM settings").fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}
    except:
        return {}

def save_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
#   AUTH
# ══════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════
#   BASE STYLE
# ══════════════════════════════════════════════
BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dev Clin Admin</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:#0f0f1a;color:#e0e0e0;min-height:100vh}
  .navbar{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:14px 24px;display:flex;
          align-items:center;justify-content:space-between;border-bottom:1px solid #00d4ff33;
          position:sticky;top:0;z-index:100}
  .navbar .brand{font-size:1.2rem;font-weight:700;color:#00d4ff}
  .navbar a{color:#aaa;text-decoration:none;margin-left:16px;font-size:.9rem}
  .navbar a:hover{color:#00d4ff}
  .container{max-width:1100px;margin:0 auto;padding:24px 16px}
  .card{background:#1a1a2e;border:1px solid #00d4ff22;border-radius:12px;padding:20px;margin-bottom:20px}
  .card h2{color:#00d4ff;margin-bottom:16px;font-size:1.1rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
  .stat{background:linear-gradient(135deg,#1a1a2e,#0f3460);border:1px solid #00d4ff33;
        border-radius:12px;padding:20px;text-align:center}
  .stat .num{font-size:2rem;font-weight:700;color:#00d4ff}
  .stat .lbl{font-size:.85rem;color:#888;margin-top:4px}
  table{width:100%;border-collapse:collapse;font-size:.88rem}
  th{background:#0f3460;color:#00d4ff;padding:10px 12px;text-align:left}
  td{padding:9px 12px;border-bottom:1px solid #ffffff0a}
  tr:hover td{background:#ffffff05}
  .btn{display:inline-block;padding:8px 16px;border-radius:8px;border:none;cursor:pointer;
       font-size:.85rem;font-weight:600;text-decoration:none;transition:.2s}
  .btn-primary{background:linear-gradient(135deg,#00d4ff,#0099cc);color:#000}
  .btn-danger{background:linear-gradient(135deg,#ff4444,#cc0000);color:#fff}
  .btn-success{background:linear-gradient(135deg,#00cc66,#009944);color:#fff}
  .btn-warning{background:linear-gradient(135deg,#ffaa00,#cc8800);color:#000}
  .btn-sm{padding:5px 10px;font-size:.78rem}
  input,textarea,select{background:#0f0f1a;border:1px solid #00d4ff33;color:#e0e0e0;
                         border-radius:8px;padding:9px 12px;width:100%;margin-bottom:12px;font-size:.9rem}
  input:focus,textarea:focus,select:focus{outline:none;border-color:#00d4ff}
  label{font-size:.85rem;color:#aaa;margin-bottom:4px;display:block}
  .badge{display:inline-block;padding:3px 8px;border-radius:20px;font-size:.75rem;font-weight:600}
  .badge-green{background:#00cc6622;color:#00cc66;border:1px solid #00cc6644}
  .badge-red{background:#ff444422;color:#ff4444;border:1px solid #ff444444}
  .badge-yellow{background:#ffaa0022;color:#ffaa00;border:1px solid #ffaa0044}
  .badge-blue{background:#00d4ff22;color:#00d4ff;border:1px solid #00d4ff44}
  .flash{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:.9rem}
  .flash-ok{background:#00cc6622;border:1px solid #00cc6644;color:#00cc66}
  .flash-err{background:#ff444422;border:1px solid #ff444444;color:#ff4444}
  .tab-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
  .tab-btn{padding:8px 18px;border-radius:8px;border:1px solid #00d4ff33;
           background:transparent;color:#aaa;cursor:pointer;font-size:.85rem;text-decoration:none}
  .tab-btn.active,.tab-btn:hover{background:#00d4ff22;color:#00d4ff;border-color:#00d4ff}
  .login-wrap{display:flex;align-items:center;justify-content:center;min-height:100vh}
  .login-box{background:#1a1a2e;border:1px solid #00d4ff33;border-radius:16px;padding:40px;
             width:100%;max-width:380px;text-align:center}
  .login-box h1{color:#00d4ff;margin-bottom:8px}
  .login-box p{color:#888;margin-bottom:24px;font-size:.9rem}
  .stars{color:#ffaa00}
  @media(max-width:600px){.grid{grid-template-columns:1fr 1fr}table{font-size:.78rem}td,th{padding:7px 8px}}
</style>
"""

NAV = """
<nav class="navbar">
  <span class="brand">⚡ Dev Clin Admin</span>
  <div>
    <a href="/">📊 Dashboard</a>
    <a href="/products">📦 Products</a>
    <a href="/orders">🛒 Orders</a>
    <a href="/users">👥 Users</a>
    <a href="/reviews">⭐ Reviews</a>
    <a href="/inquiries">📩 Inquiries</a>
    <a href="/broadcast">📢 Broadcast</a>
    <a href="/downloads">📥 Downloads</a>
    <a href="/settings">⚙️ Settings</a>
    <a href="/logout">🚪 Logout</a>
  </div>
</nav>
"""

def flash_html(msgs):
    html = ""
    for cat, msg in msgs:
        cls = "flash-ok" if cat == "ok" else "flash-err"
        html += f'<div class="flash {cls}">{msg}</div>'
    return html

# ══════════════════════════════════════════════
#   LOGIN
# ══════════════════════════════════════════════
@app.route("/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        pwd = request.form.get("password","")
        if pwd == ADMIN_PWD:
            session["admin_logged_in"] = True
            return redirect("/")
        err = "❌ Wrong password."
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    <div class="login-wrap">
      <div class="login-box">
        <h1>⚡ Dev Clin</h1>
        <p>Skyline Technologies — Admin Panel</p>
        {'<div class="flash flash-err">'+err+'</div>' if err else ''}
        <form method="POST">
          <input type="password" name="password" placeholder="Admin Password" required autofocus>
          <button class="btn btn-primary" style="width:100%;padding:12px">Login</button>
        </form>
      </div>
    </div></body></html>""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ══════════════════════════════════════════════
#   DASHBOARD
# ══════════════════════════════════════════════
@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    total_users     = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_orders    = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    verified_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='verified'").fetchone()[0]
    active_products = conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
    pending_inq     = conn.execute("SELECT COUNT(*) FROM service_inquiries WHERE replied=0").fetchone()[0]
    active_dl       = conn.execute("SELECT COUNT(*) FROM user_downloads WHERE expires_at > ?", (datetime.now().isoformat(),)).fetchone()[0]
    recent_orders   = conn.execute(
        "SELECT display_name, product_name, amount, status, created_at FROM orders ORDER BY id DESC LIMIT 8"
    ).fetchall()
    recent_users = conn.execute(
        "SELECT username, display_name, points, discount_balance, joined_at FROM users ORDER BY joined_at DESC LIMIT 5"
    ).fetchall()
    conn.close()

    orders_html = "".join([
        f"""<tr>
          <td>{r['display_name']}</td>
          <td>{r['product_name']}</td>
          <td>{r['amount']}</td>
          <td><span class="badge {'badge-green' if r['status']=='verified' else 'badge-yellow'}">{r['status']}</span></td>
          <td>{r['created_at'][:10]}</td>
        </tr>""" for r in recent_orders
    ])

    users_html = "".join([
        f"""<tr>
          <td><b>{u['display_name']}</b><br><small style="color:#888">@{u['username']}</small></td>
          <td><span class="badge badge-blue">{u['points']} pts</span></td>
          <td>KSh {u['discount_balance']:,.0f}</td>
          <td>{u['joined_at'][:10] if u['joined_at'] else 'N/A'}</td>
        </tr>""" for u in recent_users
    ])

    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}
    <div class="container">
      <h1 style="color:#00d4ff;margin-bottom:20px">📊 Dashboard</h1>
      <div class="grid">
        <div class="stat"><div class="num">{total_users}</div><div class="lbl">👥 Total Users</div></div>
        <div class="stat"><div class="num">{active_products}</div><div class="lbl">📦 Active Products</div></div>
        <div class="stat"><div class="num">{verified_orders}</div><div class="lbl">✅ Verified Orders</div></div>
        <div class="stat"><div class="num">{pending_inq}</div><div class="lbl">📩 Pending Inquiries</div></div>
        <div class="stat"><div class="num">{active_dl}</div><div class="lbl">📥 Active Downloads</div></div>
        <div class="stat"><div class="num">{total_orders}</div><div class="lbl">🛒 Total Orders</div></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div class="card">
          <h2>🛒 Recent Orders</h2>
          <table><tr><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th></tr>
          {orders_html}</table>
        </div>
        <div class="card">
          <h2>👥 Recent Users</h2>
          <table><tr><th>User</th><th>Points</th><th>Discount</th><th>Joined</th></tr>
          {users_html}</table>
        </div>
      </div>
    </div></body></html>""")

# ══════════════════════════════════════════════
#   PRODUCTS
# ══════════════════════════════════════════════
@app.route("/products", methods=["GET","POST"])
@login_required
def products():
    conn = get_db()
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            pid   = request.form.get("pid","").strip()
            name  = request.form.get("name","").strip()
            cat   = request.form.get("category","").strip()
            price = request.form.get("price","").strip()
            pval  = float(request.form.get("price_value",0) or 0)
            ptype = request.form.get("type","").strip()
            desc  = request.form.get("desc","").strip()
            link  = request.form.get("link","").strip()
            icon  = request.form.get("icon","📦").strip()
            img   = request.form.get("image_url","").strip()
            sale  = float(request.form.get("sale_price",0) or 0)
            try:
                conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (pid,name,cat,price,pval,ptype,desc,link,icon,1,img,sale))
                conn.commit()
                msg = f'<div class="flash flash-ok">✅ Product <b>{name}</b> added!</div>'
            except Exception as e:
                msg = f'<div class="flash flash-err">❌ {e}</div>'
        elif action == "toggle":
            pid = request.form.get("pid")
            row = conn.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
            if row:
                conn.execute("UPDATE products SET active=? WHERE id=?", (0 if row["active"] else 1, pid))
                conn.commit()
        elif action == "delete":
            pid = request.form.get("pid")
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
        elif action == "setlink":
            pid  = request.form.get("pid")
            link = request.form.get("link","").strip()
            conn.execute("UPDATE products SET link=? WHERE id=?", (link, pid))
            conn.commit()
            msg = '<div class="flash flash-ok">✅ Link updated!</div>'
        elif action == "setsale":
            pid  = request.form.get("pid")
            sale = float(request.form.get("sale_price",0) or 0)
            conn.execute("UPDATE products SET sale_price=? WHERE id=?", (sale, pid))
            conn.commit()
            msg = '<div class="flash flash-ok">✅ Sale price updated!</div>'

    prods = conn.execute("SELECT * FROM products ORDER BY active DESC, name").fetchall()
    cats  = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    rows = ""
    for p in prods:
        status = f'<span class="badge badge-green">Active</span>' if p["active"] else f'<span class="badge badge-red">Off</span>'
        sale   = f"KSh {p['sale_price']:,.0f}" if p.get("sale_price") else "—"
        link   = f'<a href="{p["link"]}" target="_blank" style="color:#00d4ff">🔗 Link</a>' if p["link"] else '<span style="color:#ff4444">❌ No link</span>'
        rows += f"""<tr>
          <td>{p['icon']} <b>{p['name']}</b><br><small style="color:#888">{p['id']}</small></td>
          <td>{p['category']}</td><td>{p['price']}</td><td>{sale}</td>
          <td>{p['type']}</td><td>{link}</td><td>{status}</td>
          <td>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="toggle">
              <input type="hidden" name="pid" value="{p['id']}">
              <button class="btn btn-warning btn-sm">Toggle</button>
            </form>
            <button class="btn btn-primary btn-sm" onclick="showLinkForm('{p['id']}')">Set Link</button>
            <button class="btn btn-success btn-sm" onclick="showSaleForm('{p['id']}')">Sale</button>
            <form method="POST" style="display:inline" onsubmit="return confirm('Delete?')">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="pid" value="{p['id']}">
              <button class="btn btn-danger btn-sm">Del</button>
            </form>
          </td>
        </tr>"""

    cat_options = "".join([f'<option value="{c["id"]}">{c["label"]}</option>' for c in cats])

    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">📦 Products</h1>
    {msg}
    <div class="card">
      <h2>➕ Add New Product</h2>
      <form method="POST">
        <input type="hidden" name="action" value="add">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
          <div><label>Product ID</label><input name="pid" placeholder="p8" required></div>
          <div><label>Name</label><input name="name" placeholder="Product Name" required></div>
          <div><label>Category</label><select name="category">{cat_options}</select></div>
          <div><label>Price Label</label><input name="price" placeholder="KSh 500" required></div>
          <div><label>Price Value (number)</label><input name="price_value" type="number" placeholder="500" required></div>
          <div><label>Type</label><input name="type" placeholder="PDF / APK / MP4..." required></div>
          <div><label>Icon</label><input name="icon" placeholder="📦" value="📦"></div>
          <div><label>Download Link</label><input name="link" placeholder="https://drive.google.com/..."></div>
          <div><label>Sale Price (0 = off)</label><input name="sale_price" type="number" placeholder="0"></div>
        </div>
        <label>Description</label>
        <textarea name="desc" rows="2" placeholder="Describe this product..." required></textarea>
        <label>Image URL (optional)</label>
        <input name="image_url" placeholder="https://...">
        <button class="btn btn-primary">➕ Add Product</button>
      </form>
    </div>
    <div class="card">
      <h2>📦 All Products</h2>
      <table><tr><th>Product</th><th>Category</th><th>Price</th><th>Sale</th><th>Type</th><th>Link</th><th>Status</th><th>Actions</th></tr>
      {rows}</table>
    </div>
    <div id="link-form" style="display:none" class="card">
      <h2>🔗 Set Download Link</h2>
      <form method="POST">
        <input type="hidden" name="action" value="setlink">
        <input type="hidden" name="pid" id="link-pid">
        <input name="link" placeholder="https://drive.google.com/..." required>
        <button class="btn btn-primary">Save Link</button>
        <button type="button" class="btn btn-danger" onclick="document.getElementById('link-form').style.display='none'">Cancel</button>
      </form>
    </div>
    <div id="sale-form" style="display:none" class="card">
      <h2>🔥 Set Sale Price</h2>
      <form method="POST">
        <input type="hidden" name="action" value="setsale">
        <input type="hidden" name="pid" id="sale-pid">
        <input name="sale_price" type="number" placeholder="Sale price (0 to disable)">
        <button class="btn btn-success">Save Sale Price</button>
        <button type="button" class="btn btn-danger" onclick="document.getElementById('sale-form').style.display='none'">Cancel</button>
      </form>
    </div>
    <script>
    function showLinkForm(pid){{document.getElementById('link-form').style.display='block';document.getElementById('link-pid').value=pid;}}
    function showSaleForm(pid){{document.getElementById('sale-form').style.display='block';document.getElementById('sale-pid').value=pid;}}
    </script>
    </div></body></html>""")

# ══════════════════════════════════════════════
#   ORDERS
# ══════════════════════════════════════════════
@app.route("/orders")
@login_required
def orders():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    trs = ""
    for r in rows:
        s   = "verified"
        cls = "badge-green" if r["status"] == "verified" else "badge-yellow"
        trs += f"""<tr>
          <td>{r['id']}</td>
          <td>{r['display_name']}<br><small style="color:#888">@{r['username']}</small></td>
          <td>{r['product_name']}</td>
          <td>{r['amount']}</td>
          <td><span class="badge {cls}">{r['status']}</span></td>
          <td>{r['created_at'][:16]}</td>
          <td><small style="color:#888;word-break:break-all">{(r['mpesa_msg'] or '')[:60]}...</small></td>
        </tr>"""
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">🛒 Orders</h1>
    <div class="card">
      <table><tr><th>#</th><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th><th>SMS Preview</th></tr>
      {trs}</table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   USERS
# ══════════════════════════════════════════════
@app.route("/users", methods=["GET","POST"])
@login_required
def users():
    conn = get_db()
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "grant_discount":
            uid    = int(request.form.get("uid"))
            amount = float(request.form.get("amount", 0))
            conn.execute("UPDATE users SET discount_balance=discount_balance+? WHERE telegram_id=?", (amount, uid))
            conn.commit()
            msg = f'<div class="flash flash-ok">✅ KSh {amount:,.0f} discount granted!</div>'
        elif action == "reset_points":
            uid = int(request.form.get("uid"))
            conn.execute("UPDATE users SET points=0 WHERE telegram_id=?", (uid,))
            conn.commit()
            msg = '<div class="flash flash-ok">✅ Points reset to 0.</div>'
        elif action == "clear_discount":
            uid = int(request.form.get("uid"))
            conn.execute("UPDATE users SET discount_balance=0 WHERE telegram_id=?", (uid,))
            conn.commit()
            msg = '<div class="flash flash-ok">✅ Discount cleared.</div>'

    users_list = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()

    rows = ""
    for u in users_list:
        dl_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='verified'", (u["telegram_id"],)
        ).fetchone()[0]
        rows += f"""<tr>
          <td>{u['telegram_id']}</td>
          <td><b>{u['display_name']}</b><br><small style="color:#888">@{u['username']}</small></td>
          <td><span class="badge badge-blue">{u['points']} pts</span></td>
          <td><span class="badge badge-green">KSh {u['discount_balance']:,.0f}</span></td>
          <td>{dl_count}</td>
          <td>{u['joined_at'][:10] if u['joined_at'] else 'N/A'}</td>
          <td>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="grant_discount">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <input type="number" name="amount" placeholder="Amount" style="width:90px;display:inline;margin:0;padding:5px">
              <button class="btn btn-success btn-sm">+ Discount</button>
            </form>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="reset_points">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <button class="btn btn-warning btn-sm">Reset Pts</button>
            </form>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="clear_discount">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <button class="btn btn-danger btn-sm">Clear Disc</button>
            </form>
          </td>
        </tr>"""
    conn.close()

    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">👥 Users</h1>
    {msg}
    <div class="card">
      <table>
        <tr><th>ID</th><th>User</th><th>Points</th><th>Discount</th><th>Purchases</th><th>Joined</th><th>Actions</th></tr>
        {rows}
      </table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   REVIEWS
# ══════════════════════════════════════════════
@app.route("/reviews")
@login_required
def reviews():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs = ""
    for r in rows:
        stars = "⭐" * (r["rating"] or 0)
        badge = "badge-blue" if r["type"] == "bot" else "badge-green"
        trs += f"""<tr>
          <td>{r['display_name']}<br><small>@{r['username']}</small></td>
          <td><span class="badge {badge}">{r['type']}</span></td>
          <td>{r['product_name']}</td>
          <td class="stars">{stars} ({r['rating']}/5)</td>
          <td>{r['review'] or '—'}</td>
          <td>{r['created_at'][:10]}</td>
        </tr>"""
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">⭐ Reviews</h1>
    <div class="card">
      <table><tr><th>User</th><th>Type</th><th>Product</th><th>Rating</th><th>Review</th><th>Date</th></tr>
      {trs}</table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   SERVICE INQUIRIES
# ══════════════════════════════════════════════
@app.route("/inquiries", methods=["GET","POST"])
@login_required
def inquiries():
    conn = get_db()
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "mark_replied":
            iid = request.form.get("iid")
            conn.execute("UPDATE service_inquiries SET replied=1 WHERE id=?", (iid,))
            conn.commit()
            msg = '<div class="flash flash-ok">✅ Marked as replied.</div>'

    rows = conn.execute("SELECT * FROM service_inquiries ORDER BY id DESC").fetchall()
    conn.close()

    trs = ""
    for r in rows:
        badge = "badge-yellow" if not r["replied"] else "badge-green"
        status = "Pending" if not r["replied"] else "Replied"
        wa_link = f"https://wa.me/17808518629?text=Hi+{r['display_name']}%2C+regarding+your+{r['service_name']}+inquiry..."
        trs += f"""<tr>
          <td>{r['display_name']}<br><small>@{r['username']}</small></td>
          <td>{r['service_name']}</td>
          <td>{r['description']}</td>
          <td>{r['created_at'][:16]}</td>
          <td><span class="badge {badge}">{status}</span></td>
          <td>
            <a href="{wa_link}" target="_blank" class="btn btn-success btn-sm">💬 WhatsApp</a>
            {'<form method="POST" style="display:inline"><input type="hidden" name="action" value="mark_replied"><input type="hidden" name="iid" value="'+str(r["id"])+'"><button class="btn btn-primary btn-sm">✅ Done</button></form>' if not r["replied"] else ''}
          </td>
        </tr>"""

    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">📩 Service Inquiries</h1>
    {msg}
    <div class="card">
      <table><tr><th>User</th><th>Service</th><th>Description</th><th>Date</th><th>Status</th><th>Actions</th></tr>
      {trs}</table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   DOWNLOADS / ACCESS TRACKING
# ══════════════════════════════════════════════
@app.route("/downloads")
@login_required
def downloads():
    conn = get_db()
    rows = conn.execute(
        "SELECT ud.*, u.username, u.display_name FROM user_downloads ud "
        "LEFT JOIN users u ON ud.user_id=u.telegram_id ORDER BY ud.id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    trs = ""
    now = datetime.now().isoformat()
    for r in rows:
        expired   = r["expires_at"] < now
        clicks    = r["click_count"]
        badge     = "badge-red" if expired else ("badge-yellow" if clicks <= 1 else "badge-green")
        status    = "Expired" if expired else f"{clicks}/3 clicks left"
        mins_left = ""
        if not expired:
            try:
                exp = datetime.fromisoformat(r["expires_at"])
                diff = int((exp - datetime.now()).total_seconds() / 60)
                mins_left = f"({diff} min left)"
            except:
                pass
        trs += f"""<tr>
          <td>{r['display_name'] or r['user_id']}<br><small>@{r.get('username','')}</small></td>
          <td>{r['product_name']}</td>
          <td><span class="badge {badge}">{status}</span> <small>{mins_left}</small></td>
          <td>{r['expires_at'][:16]}</td>
          <td><a href="{r['file_url']}" target="_blank" style="color:#00d4ff">🔗 Link</a></td>
        </tr>"""
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">📥 Download Access</h1>
    <div class="card">
      <table><tr><th>User</th><th>Product</th><th>Status</th><th>Expires</th><th>Link</th></tr>
      {trs}</table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   BROADCAST
# ══════════════════════════════════════════════
@app.route("/broadcast", methods=["GET","POST"])
@login_required
def broadcast():
    msg = ""
    if request.method == "POST":
        text = request.form.get("message","").strip()
        if text:
            conn = get_db()
            users = conn.execute("SELECT telegram_id FROM users").fetchall()
            conn.close()
            bot_token = os.environ.get("BOT_TOKEN","")
            sent = failed = 0
            for u in users:
                try:
                    import urllib.request, urllib.parse
                    payload = _json.dumps({
                        "chat_id": u["telegram_id"],
                        "text": f"📢 *Announcement from Dev Clin Market:*\n\n{text}\n\n_Skyline Technologies_",
                        "parse_mode": "Markdown"
                    }).encode()
                    req = urllib.request.Request(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data=payload, headers={"Content-Type":"application/json"}
                    )
                    urllib.request.urlopen(req, timeout=5)
                    sent += 1
                except:
                    failed += 1
            msg = f'<div class="flash flash-ok">✅ Sent to {sent} users. ❌ Failed: {failed}</div>'
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">📢 Broadcast</h1>
    {msg}
    <div class="card">
      <h2>Send Message to All Users</h2>
      <form method="POST">
        <label>Message</label>
        <textarea name="message" rows="6" placeholder="Type your announcement here..." required></textarea>
        <button class="btn btn-primary">📢 Send to All Users</button>
      </form>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   SETTINGS
# ══════════════════════════════════════════════
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    msg = ""
    if request.method == "POST":
        fields = [
            "mpesa_name","mpesa_number","group_chat_link",
            "bot_banner_image","banner_shop","banner_payment",
            "banner_services","banner_contact","banner_about",
            "banner_group","banner_rate","banner_links","banner_account",
            "quotes_enabled","admin_logo"
        ]
        for f in fields:
            val = request.form.get(f,"")
            save_setting(f, val)
        msg = '<div class="flash flash-ok">✅ Settings saved!</div>'

    s = get_settings()

    def field(key, label, placeholder="", typ="text"):
        val = s.get(key,"")
        if typ == "select":
            opts = '<option value="1" {}>Enabled</option><option value="0" {}>Disabled</option>'.format(
                "selected" if val == "1" else "", "selected" if val == "0" else ""
            )
            return f'<label>{label}</label><select name="{key}">{opts}</select>'
        return f'<label>{label}</label><input type="{typ}" name="{key}" value="{val}" placeholder="{placeholder}">'

    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">⚙️ Settings</h1>
    {msg}
    <form method="POST">
      <div class="card">
        <h2>💳 M-Pesa</h2>
        {field("mpesa_name","Receiver Name","Clinton Oduor")}
        {field("mpesa_number","Receiver Number","0743810633")}
      </div>
      <div class="card">
        <h2>💬 Community</h2>
        {field("group_chat_link","Group Chat Link","https://t.me/...")}
      </div>
      <div class="card">
        <h2>⏰ Quotes</h2>
        {field("quotes_enabled","Daily Motivational Quotes","","select")}
      </div>
      <div class="card">
        <h2>🖼 Banner Images</h2>
        {field("bot_banner_image","Default Banner URL","")}
        {field("banner_shop","Shop Banner URL","")}
        {field("banner_payment","Payment Banner URL","")}
        {field("banner_services","Services Banner URL","")}
        {field("banner_contact","Contact Banner URL","")}
        {field("banner_about","About Banner URL","")}
        {field("banner_group","Group Chat Banner URL","")}
        {field("banner_rate","Rate Us Banner URL","")}
        {field("banner_links","Links Banner URL","")}
        {field("banner_account","Dashboard Banner URL","")}
        {field("admin_logo","Admin Logo URL","")}
      </div>
      <button class="btn btn-primary" style="padding:12px 32px">💾 Save All Settings</button>
    </form>
    </div></body></html>""")

# ══════════════════════════════════════════════
#   CATEGORIES
# ══════════════════════════════════════════════
@app.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    conn = get_db()
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            cid   = request.form.get("cid","").strip()
            icon  = request.form.get("icon","📦").strip()
            label = request.form.get("label","").strip()
            try:
                conn.execute("INSERT INTO categories VALUES (?,?,?)", (cid, f"{icon} {label}", icon))
                conn.commit()
                msg = f'<div class="flash flash-ok">✅ Category added!</div>'
            except Exception as e:
                msg = f'<div class="flash flash-err">❌ {e}</div>'
        elif action == "delete":
            cid = request.form.get("cid")
            conn.execute("DELETE FROM categories WHERE id=?", (cid,))
            conn.commit()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    rows = "".join([f"""<tr><td>{c['icon']}</td><td>{c['id']}</td><td>{c['label']}</td>
    <td><form method="POST" style="display:inline" onsubmit="return confirm('Delete?')">
    <input type="hidden" name="action" value="delete"><input type="hidden" name="cid" value="{c['id']}">
    <button class="btn btn-danger btn-sm">Delete</button></form></td></tr>""" for c in cats])
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">📂 Categories</h1>
    {msg}
    <div class="card">
      <h2>➕ Add Category</h2>
      <form method="POST">
        <input type="hidden" name="action" value="add">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
          <div><label>ID</label><input name="cid" placeholder="education" required></div>
          <div><label>Icon</label><input name="icon" placeholder="📚" required></div>
          <div><label>Label</label><input name="label" placeholder="Education" required></div>
        </div>
        <button class="btn btn-primary">➕ Add</button>
      </form>
    </div>
    <div class="card">
      <table><tr><th>Icon</th><th>ID</th><th>Label</th><th>Action</th></tr>{rows}</table>
    </div></div></body></html>""")

# ══════════════════════════════════════════════
#   MESSAGES
# ══════════════════════════════════════════════
@app.route("/messages")
@login_required
def messages():
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs = ""
    for r in rows:
        badge = "badge-blue" if r["direction"] == "user_to_admin" else "badge-green"
        label = "User → Admin" if r["direction"] == "user_to_admin" else "Admin → User"
        trs += f"""<tr>
          <td>{r['from_name']}</td>
          <td><span class="badge {badge}">{label}</span></td>
          <td>{r['message']}</td>
          <td>{r['created_at'][:16]}</td>
        </tr>"""
    return render_template_string(f"""<!DOCTYPE html><html><head>{BASE_STYLE}</head><body>
    {NAV}<div class="container">
    <h1 style="color:#00d4ff;margin-bottom:20px">💬 Messages</h1>
    <div class="card">
      <table><tr><th>From</th><th>Direction</th><th>Message</th><th>Date</th></tr>{trs}</table>
    </div></div></body></html>""")

import json as _json

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    run()
