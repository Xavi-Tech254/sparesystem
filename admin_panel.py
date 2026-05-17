import os
import sqlite3
import json as _json
import urllib.request
import random
from datetime import datetime
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devclin_skyline_2025")

DB_PATH   = "devclin.db"
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin1234")
COMPANY   = "Skyline Technologies"
BOT_NAME  = "Dev Clin Market"

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

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════
#   BASE STYLE — FULLY RESPONSIVE PROFESSIONAL
# ══════════════════════════════════════════════
BASE = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Dev Clin Admin</title>
<style>
:root{--bg:#0a0a14;--card:#12121f;--border:#1e2d4a;--accent:#00d4ff;--accent2:#7c3aed;
      --text:#e2e8f0;--muted:#64748b;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--white:#fff}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:15px}
a{color:var(--accent);text-decoration:none}
/* SIDEBAR */
.sidebar{position:fixed;left:0;top:0;bottom:0;width:220px;background:var(--card);
         border-right:1px solid var(--border);z-index:200;overflow-y:auto;transition:.3s}
.sidebar-brand{padding:20px 16px;border-bottom:1px solid var(--border)}
.sidebar-brand h2{color:var(--accent);font-size:1.1rem;font-weight:700}
.sidebar-brand p{color:var(--muted);font-size:.75rem;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:11px 16px;color:var(--muted);
          font-size:.88rem;border-left:3px solid transparent;transition:.2s;cursor:pointer}
.nav-item:hover,.nav-item.active{color:var(--accent);background:#00d4ff0a;border-left-color:var(--accent)}
.nav-item span{font-size:1rem}
/* MAIN */
.main{margin-left:220px;min-height:100vh;padding:20px}
/* TOPBAR */
.topbar{display:flex;align-items:center;justify-content:space-between;
        background:var(--card);border:1px solid var(--border);border-radius:12px;
        padding:12px 20px;margin-bottom:20px}
.topbar h1{font-size:1.1rem;font-weight:600;color:var(--text)}
.topbar-right{display:flex;gap:8px;align-items:center}
/* CARDS */
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:16px}
.card-title{font-size:.9rem;font-weight:600;color:var(--accent);margin-bottom:16px;
            display:flex;align-items:center;gap:8px}
/* GRID */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
/* STAT CARDS */
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;
      padding:18px;text-align:center;position:relative;overflow:hidden}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
              background:linear-gradient(90deg,var(--accent),var(--accent2))}
.stat .num{font-size:1.8rem;font-weight:700;color:var(--accent);line-height:1}
.stat .lbl{font-size:.78rem;color:var(--muted);margin-top:6px}
.stat .ico{font-size:1.5rem;margin-bottom:8px}
/* TABLE */
.table-wrap{overflow-x:auto;border-radius:8px}
table{width:100%;border-collapse:collapse;min-width:500px}
th{background:#0f1929;color:var(--accent);padding:11px 14px;text-align:left;
   font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid #ffffff08;font-size:.85rem;vertical-align:middle}
tr:hover td{background:#ffffff04}
/* FORMS */
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500}
input,textarea,select{width:100%;background:#0d0d1a;border:1px solid var(--border);
                       color:var(--text);border-radius:8px;padding:10px 12px;
                       font-size:.88rem;transition:.2s;font-family:inherit}
input:focus,textarea:focus,select:focus{outline:none;border-color:var(--accent);
                                         box-shadow:0 0 0 3px #00d4ff15}
textarea{resize:vertical;min-height:90px}
/* BUTTONS */
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:8px;
     border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:.2s;white-space:nowrap}
.btn:hover{transform:translateY(-1px);opacity:.9}
.btn-primary{background:linear-gradient(135deg,var(--accent),#0099cc);color:#000}
.btn-danger{background:linear-gradient(135deg,var(--red),#b91c1c);color:#fff}
.btn-success{background:linear-gradient(135deg,var(--green),#059669);color:#fff}
.btn-warning{background:linear-gradient(135deg,var(--yellow),#d97706);color:#000}
.btn-purple{background:linear-gradient(135deg,var(--accent2),#5b21b6);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--muted)}
.btn-sm{padding:5px 12px;font-size:.78rem}
.btn-xs{padding:3px 8px;font-size:.72rem}
/* BADGES */
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;
       font-size:.72rem;font-weight:600;white-space:nowrap}
.badge-green{background:#10b98120;color:var(--green);border:1px solid #10b98140}
.badge-red{background:#ef444420;color:var(--red);border:1px solid #ef444440}
.badge-yellow{background:#f59e0b20;color:var(--yellow);border:1px solid #f59e0b40}
.badge-blue{background:#00d4ff20;color:var(--accent);border:1px solid #00d4ff40}
.badge-purple{background:#7c3aed20;color:var(--accent2);border:1px solid #7c3aed40}
/* ALERT */
.alert{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:.88rem;display:flex;align-items:center;gap:8px}
.alert-ok{background:#10b98115;border:1px solid #10b98140;color:var(--green)}
.alert-err{background:#ef444415;border:1px solid #ef444440;color:var(--red)}
/* LOGIN */
.login-page{display:flex;align-items:center;justify-content:center;min-height:100vh;
            background:radial-gradient(ellipse at top,#0f1929 0%,var(--bg) 70%)}
.login-box{background:var(--card);border:1px solid var(--border);border-radius:16px;
           padding:40px;width:100%;max-width:360px;text-align:center}
.login-box .logo{font-size:2.5rem;margin-bottom:8px}
.login-box h1{color:var(--accent);font-size:1.3rem;margin-bottom:4px}
.login-box p{color:var(--muted);font-size:.85rem;margin-bottom:28px}
/* HAMBURGER */
.hamburger{display:none;background:none;border:none;color:var(--text);font-size:1.4rem;cursor:pointer;padding:4px}
.overlay{display:none;position:fixed;inset:0;background:#00000080;z-index:150}
/* TABS */
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px}
.tab{padding:7px 16px;border-radius:8px;border:1px solid var(--border);
     background:transparent;color:var(--muted);cursor:pointer;font-size:.83rem;font-weight:500}
.tab.active,.tab:hover{background:#00d4ff15;color:var(--accent);border-color:var(--accent)}
/* SECTION HIDDEN */
.tab-section{display:none}.tab-section.active{display:block}
/* RESPONSIVE */
@media(max-width:768px){
  .sidebar{transform:translateX(-100%)}
  .sidebar.open{transform:translateX(0)}
  .overlay.open{display:block}
  .main{margin-left:0;padding:12px}
  .hamburger{display:block}
  .grid-2,.grid-3,.grid-4{grid-template-columns:1fr}
  .stat .num{font-size:1.4rem}
  th,td{padding:8px 10px}
  .btn{padding:8px 14px}
  .topbar{padding:10px 14px}
  .topbar h1{font-size:.95rem}
}
@media(max-width:480px){
  .grid-2{grid-template-columns:1fr 1fr}
  .card{padding:14px}
}
</style></head><body>"""

def sidebar(active=""):
    links = [
        ("dashboard","📊","Dashboard","/"),
        ("products","📦","Products","/products"),
        ("orders","🛒","Orders","/orders"),
        ("users","👥","Users","/users"),
        ("reviews","⭐","Reviews","/reviews"),
        ("inquiries","📩","Inquiries","/inquiries"),
        ("broadcast","📢","Broadcast","/broadcast"),
        ("downloads","📥","Downloads","/downloads"),
        ("messages","💬","Messages","/messages"),
        ("categories","📂","Categories","/categories"),
        ("settings","⚙️","Settings","/settings"),
    ]
    items = ""
    for key,icon,label,href in links:
        cls = "active" if active==key else ""
        items += f'<a href="{href}" class="nav-item {cls}"><span>{icon}</span>{label}</a>'
    return f"""
<div class="overlay" id="overlay" onclick="closeSidebar()"></div>
<div class="sidebar" id="sidebar">
  <div class="sidebar-brand">
    <h2>⚡ Dev Clin</h2>
    <p>Skyline Technologies</p>
  </div>
  {items}
  <a href="/logout" class="nav-item" style="margin-top:20px;color:var(--red)"><span>🚪</span>Logout</a>
</div>
<script>
function openSidebar(){{document.getElementById('sidebar').classList.add('open');document.getElementById('overlay').classList.add('open')}}
function closeSidebar(){{document.getElementById('sidebar').classList.remove('open');document.getElementById('overlay').classList.remove('open')}}
</script>"""

def topbar(title, active=""):
    return f"""
{sidebar(active)}
<div class="main"><div class="topbar">
  <div style="display:flex;align-items:center;gap:12px">
    <button class="hamburger" onclick="openSidebar()">☰</button>
    <h1>{title}</h1>
  </div>
  <div class="topbar-right">
    <span style="font-size:.8rem;color:var(--muted)">Admin Panel</span>
  </div>
</div>"""

def alert(msg, ok=True):
    if not msg: return ""
    cls = "alert-ok" if ok else "alert-err"
    ico = "✅" if ok else "❌"
    return f'<div class="alert {cls}">{ico} {msg}</div>'

# ══════════════════════════════════════════════
#   LOGIN
# ══════════════════════════════════════════════
@app.route("/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        if request.form.get("password","") == ADMIN_PWD:
            session["admin_logged_in"] = True
            return redirect("/")
        err = "Wrong password. Try again."
    return BASE + f"""
<div class="login-page">
  <div class="login-box">
    <div class="logo">⚡</div>
    <h1>Dev Clin Admin</h1>
    <p>Skyline Technologies — Control Panel</p>
    {alert(err, False) if err else ""}
    <form method="POST">
      <div class="form-group" style="text-align:left">
        <label>Admin Password</label>
        <input type="password" name="password" placeholder="Enter password" required autofocus>
      </div>
      <button class="btn btn-primary" style="width:100%;justify-content:center;padding:12px">
        🔓 Login
      </button>
    </form>
  </div>
</div></body></html>"""

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

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
    try:
        active_dl = conn.execute("SELECT COUNT(*) FROM user_downloads WHERE expires_at > ?", (datetime.now().isoformat(),)).fetchone()[0]
    except:
        active_dl = 0
    recent_orders = conn.execute("SELECT display_name,product_name,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 8").fetchall()
    recent_users  = conn.execute("SELECT username,display_name,points,discount_balance,joined_at FROM users ORDER BY joined_at DESC LIMIT 6").fetchall()
    conn.close()

    order_rows = "".join([f"""<tr>
      <td><b>{r['display_name']}</b></td><td>{r['product_name']}</td><td>{r['amount']}</td>
      <td><span class="badge {'badge-green' if r['status']=='verified' else 'badge-yellow'}">{r['status']}</span></td>
      <td style="color:var(--muted)">{r['created_at'][:10]}</td></tr>""" for r in recent_orders])

    user_rows = "".join([f"""<tr>
      <td><b>{u['display_name']}</b><br><small style="color:var(--muted)">@{u['username']}</small></td>
      <td><span class="badge badge-blue">{u['points']} pts</span></td>
      <td>KSh {u['discount_balance']:,.0f}</td>
      <td style="color:var(--muted)">{(u['joined_at'] or '')[:10]}</td></tr>""" for u in recent_users])

    return BASE + topbar("📊 Dashboard","dashboard") + f"""
<div class="grid-4" style="margin-bottom:16px">
  <div class="stat"><div class="ico">👥</div><div class="num">{total_users}</div><div class="lbl">Total Users</div></div>
  <div class="stat"><div class="ico">📦</div><div class="num">{active_products}</div><div class="lbl">Active Products</div></div>
  <div class="stat"><div class="ico">✅</div><div class="num">{verified_orders}</div><div class="lbl">Verified Orders</div></div>
  <div class="stat"><div class="ico">📩</div><div class="num">{pending_inq}</div><div class="lbl">Pending Inquiries</div></div>
</div>
<div class="grid-2">
  <div class="card">
    <div class="card-title">🛒 Recent Orders</div>
    <div class="table-wrap"><table>
      <tr><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th></tr>
      {order_rows}
    </table></div>
  </div>
  <div class="card">
    <div class="card-title">👥 Recent Users</div>
    <div class="table-wrap"><table>
      <tr><th>User</th><th>Points</th><th>Discount</th><th>Joined</th></tr>
      {user_rows}
    </table></div>
  </div>
</div>
</div></body></html>"""

# ══════════════════════════════════════════════
#   PRODUCTS
# ══════════════════════════════════════════════
@app.route("/products", methods=["GET","POST"])
@login_required
def products():
    conn = get_db()
    msg = ""; ok = True
    if request.method == "POST":
        action = request.form.get("action","")
        if action == "add":
            try:
                pid   = request.form.get("pid","").strip()
                name  = request.form.get("name","").strip()
                cat   = request.form.get("category","").strip()
                price = request.form.get("price","").strip()
                pval  = float(request.form.get("price_value",0) or 0)
                ptype = request.form.get("ptype","").strip()
                desc  = request.form.get("desc","").strip()
                link  = request.form.get("link","").strip()
                icon  = request.form.get("icon","📦").strip()
                img   = request.form.get("image_url","").strip()
                sale  = float(request.form.get("sale_price",0) or 0)
                conn.execute("INSERT INTO products (id,name,category,price,price_value,type,desc,link,icon,active,image_url,sale_price) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)",
                             (pid,name,cat,price,pval,ptype,desc,link,icon,img,sale))
                conn.commit()
                msg = f"Product '{name}' added successfully!"
            except Exception as e:
                msg = f"Error: {e}"; ok = False
        elif action == "toggle":
            pid = request.form.get("pid")
            row = conn.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
            if row:
                conn.execute("UPDATE products SET active=? WHERE id=?", (0 if row["active"] else 1, pid))
                conn.commit()
        elif action == "delete":
            conn.execute("DELETE FROM products WHERE id=?", (request.form.get("pid"),))
            conn.commit(); msg = "Product deleted."
        elif action == "setlink":
            conn.execute("UPDATE products SET link=? WHERE id=?",
                        (request.form.get("link","").strip(), request.form.get("pid")))
            conn.commit(); msg = "Download link updated!"
        elif action == "setsale":
            conn.execute("UPDATE products SET sale_price=? WHERE id=?",
                        (float(request.form.get("sale_price",0) or 0), request.form.get("pid")))
            conn.commit(); msg = "Sale price updated!"

    prods = conn.execute("SELECT * FROM products ORDER BY active DESC, name").fetchall()
    cats  = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    cat_opts = "".join([f'<option value="{c["id"]}">{c["label"]}</option>' for c in cats])

    rows = ""
    for p in prods:
        p = dict(p)
        sale_display = f"KSh {p['sale_price']:,.0f}" if p.get("sale_price") else "—"
        link_display = f'<a href="{p["link"]}" target="_blank" class="badge badge-green">🔗 Link</a>' if p.get("link") else '<span class="badge badge-red">No link</span>'
        status = f'<span class="badge badge-green">Active</span>' if p["active"] else '<span class="badge badge-red">Off</span>'
        rows += f"""<tr>
          <td><b>{p.get('icon','')} {p['name']}</b><br><small style="color:var(--muted)">{p['id']}</small></td>
          <td><span class="badge badge-purple">{p['category']}</span></td>
          <td>{p['price']}</td><td>{sale_display}</td><td>{p.get('type','')}</td>
          <td>{link_display}</td><td>{status}</td>
          <td>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="toggle">
              <input type="hidden" name="pid" value="{p['id']}">
              <button class="btn btn-warning btn-xs">Toggle</button>
            </form>
            <button class="btn btn-primary btn-xs" onclick="setLink('{p['id']}')">Link</button>
            <button class="btn btn-success btn-xs" onclick="setSale('{p['id']}')">Sale</button>
            <form method="POST" style="display:inline" onsubmit="return confirm('Delete?')">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="pid" value="{p['id']}">
              <button class="btn btn-danger btn-xs">Del</button>
            </form>
          </td></tr>"""

    return BASE + topbar("📦 Products","products") + f"""
{alert(msg, ok) if msg else ""}
<div class="card">
  <div class="card-title">➕ Add New Product</div>
  <form method="POST">
    <input type="hidden" name="action" value="add">
    <div class="grid-3">
      <div class="form-group"><label>Product ID</label><input name="pid" placeholder="p8" required></div>
      <div class="form-group"><label>Name</label><input name="name" placeholder="Product Name" required></div>
      <div class="form-group"><label>Category</label><select name="category">{cat_opts}</select></div>
      <div class="form-group"><label>Price Label</label><input name="price" placeholder="KSh 500" required></div>
      <div class="form-group"><label>Price Value</label><input name="price_value" type="number" step="0.01" placeholder="500" required></div>
      <div class="form-group"><label>Type</label><input name="ptype" placeholder="PDF / APK / MP4"></div>
      <div class="form-group"><label>Icon</label><input name="icon" placeholder="📦" value="📦"></div>
      <div class="form-group"><label>Download Link</label><input name="link" placeholder="https://drive.google.com/..."></div>
      <div class="form-group"><label>Sale Price (0=off)</label><input name="sale_price" type="number" step="0.01" placeholder="0"></div>
    </div>
    <div class="form-group"><label>Description</label><textarea name="desc" placeholder="Describe this product..." required></textarea></div>
    <div class="form-group"><label>Image URL (optional)</label><input name="image_url" placeholder="https://..."></div>
    <button class="btn btn-primary">➕ Add Product</button>
  </form>
</div>
<div class="card">
  <div class="card-title">📦 All Products</div>
  <div class="table-wrap"><table>
    <tr><th>Product</th><th>Category</th><th>Price</th><th>Sale</th><th>Type</th><th>Link</th><th>Status</th><th>Actions</th></tr>
    {rows}
  </table></div>
</div>
<div class="card" id="link-card" style="display:none">
  <div class="card-title">🔗 Set Download Link</div>
  <form method="POST">
    <input type="hidden" name="action" value="setlink">
    <input type="hidden" name="pid" id="link-pid">
    <div class="form-group"><label>Download URL</label><input name="link" placeholder="https://drive.google.com/..." required></div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-primary">💾 Save Link</button>
      <button type="button" class="btn btn-ghost" onclick="document.getElementById('link-card').style.display='none'">Cancel</button>
    </div>
  </form>
</div>
<div class="card" id="sale-card" style="display:none">
  <div class="card-title">🔥 Set Sale Price</div>
  <form method="POST">
    <input type="hidden" name="action" value="setsale">
    <input type="hidden" name="pid" id="sale-pid">
    <div class="form-group"><label>Sale Price (0 to disable)</label><input name="sale_price" type="number" step="0.01" placeholder="0"></div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-success">💾 Save</button>
      <button type="button" class="btn btn-ghost" onclick="document.getElementById('sale-card').style.display='none'">Cancel</button>
    </div>
  </form>
</div>
<script>
function setLink(pid){{document.getElementById('link-card').style.display='block';document.getElementById('link-pid').value=pid;window.scrollTo(0,document.body.scrollHeight)}}
function setSale(pid){{document.getElementById('sale-card').style.display='block';document.getElementById('sale-pid').value=pid;window.scrollTo(0,document.body.scrollHeight)}}
</script>
</div></body></html>"""

# ══════════════════════════════════════════════
#   ORDERS
# ══════════════════════════════════════════════
@app.route("/orders")
@login_required
def orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs = "".join([f"""<tr>
      <td><b>{r['display_name']}</b><br><small style="color:var(--muted)">@{r['username']}</small></td>
      <td>{r['product_name']}</td><td>{r['amount']}</td>
      <td><span class="badge {'badge-green' if r['status']=='verified' else 'badge-yellow'}">{r['status']}</span></td>
      <td style="color:var(--muted)">{r['created_at'][:16]}</td>
      <td><small style="color:var(--muted)">{(r['mpesa_msg'] or '')[:50]}...</small></td>
    </tr>""" for r in rows])
    return BASE + topbar("🛒 Orders","orders") + f"""
<div class="card">
  <div class="card-title">🛒 All Orders</div>
  <div class="table-wrap"><table>
    <tr><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th><th>SMS</th></tr>
    {trs}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   USERS
# ══════════════════════════════════════════════
@app.route("/users", methods=["GET","POST"])
@login_required
def users():
    conn = get_db()
    msg = ""; ok = True
    if request.method == "POST":
        action = request.form.get("action","")
        uid = request.form.get("uid")
        if action == "grant_discount":
            amount = float(request.form.get("amount",0) or 0)
            conn.execute("UPDATE users SET discount_balance=discount_balance+? WHERE telegram_id=?", (amount,uid))
            conn.commit(); msg = f"KSh {amount:,.0f} discount granted!"
        elif action == "reset_points":
            conn.execute("UPDATE users SET points=0 WHERE telegram_id=?", (uid,))
            conn.commit(); msg = "Points reset to 0."
        elif action == "clear_discount":
            conn.execute("UPDATE users SET discount_balance=0 WHERE telegram_id=?", (uid,))
            conn.commit(); msg = "Discount cleared."

    users_list = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    rows = ""
    for u in users_list:
        u = dict(u)
        purchases = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='verified'", (u['telegram_id'],)).fetchone()[0]
        rows += f"""<tr>
          <td><b>{u['display_name']}</b><br><small style="color:var(--muted)">@{u['username']}</small><br><small style="color:var(--muted)">{u['telegram_id']}</small></td>
          <td><span class="badge badge-blue">{u['points']} pts</span></td>
          <td><span class="badge badge-green">KSh {u['discount_balance']:,.0f}</span></td>
          <td>{purchases}</td>
          <td style="color:var(--muted)">{(u.get('joined_at','') or '')[:10]}</td>
          <td>
            <form method="POST" style="display:inline;white-space:nowrap">
              <input type="hidden" name="action" value="grant_discount">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <input type="number" name="amount" placeholder="Amount" style="width:80px;display:inline;padding:4px 8px;margin:0 4px 0 0">
              <button class="btn btn-success btn-xs">+Disc</button>
            </form>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="reset_points">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <button class="btn btn-warning btn-xs">Rst Pts</button>
            </form>
            <form method="POST" style="display:inline">
              <input type="hidden" name="action" value="clear_discount">
              <input type="hidden" name="uid" value="{u['telegram_id']}">
              <button class="btn btn-danger btn-xs">Clr Disc</button>
            </form>
          </td></tr>"""
    conn.close()
    return BASE + topbar("👥 Users","users") + f"""
{alert(msg,ok) if msg else ""}
<div class="card">
  <div class="card-title">👥 All Users ({len(users_list)})</div>
  <div class="table-wrap"><table>
    <tr><th>User</th><th>Points</th><th>Discount</th><th>Purchases</th><th>Joined</th><th>Actions</th></tr>
    {rows}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   REVIEWS
# ══════════════════════════════════════════════
@app.route("/reviews")
@login_required
def reviews():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs = "".join([f"""<tr>
      <td><b>{r['display_name']}</b><br><small style="color:var(--muted)">@{r['username']}</small></td>
      <td><span class="badge {'badge-blue' if r['type']=='bot' else 'badge-green'}">{r['type']}</span></td>
      <td>{r['product_name']}</td>
      <td style="color:#f59e0b">{'⭐'*(r['rating'] or 0)} <small style="color:var(--muted)">({r['rating']}/5)</small></td>
      <td>{r['review'] or '—'}</td>
      <td style="color:var(--muted)">{r['created_at'][:10]}</td>
    </tr>""" for r in rows])
    return BASE + topbar("⭐ Reviews","reviews") + f"""
<div class="card">
  <div class="card-title">⭐ All Reviews</div>
  <div class="table-wrap"><table>
    <tr><th>User</th><th>Type</th><th>Product</th><th>Rating</th><th>Review</th><th>Date</th></tr>
    {trs}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   INQUIRIES
# ══════════════════════════════════════════════
@app.route("/inquiries", methods=["GET","POST"])
@login_required
def inquiries():
    conn = get_db()
    msg = ""
    if request.method == "POST":
        conn.execute("UPDATE service_inquiries SET replied=1 WHERE id=?", (request.form.get("iid"),))
        conn.commit(); msg = "Marked as replied."
    rows = conn.execute("SELECT * FROM service_inquiries ORDER BY id DESC").fetchall()
    conn.close()
    trs = ""
    for r in rows:
        wa = f"https://wa.me/17808518629?text=Hi+{r['display_name']}%2C+about+your+{r['service_name']}+inquiry..."
        trs += f"""<tr>
          <td><b>{r['display_name']}</b><br><small style="color:var(--muted)">@{r['username']}</small></td>
          <td>{r['service_name']}</td><td>{r['description']}</td>
          <td style="color:var(--muted)">{r['created_at'][:16]}</td>
          <td><span class="badge {'badge-yellow' if not r['replied'] else 'badge-green'}">{'Pending' if not r['replied'] else 'Replied'}</span></td>
          <td>
            <a href="{wa}" target="_blank" class="btn btn-success btn-xs">💬 WhatsApp</a>
            {'<form method="POST" style="display:inline"><input type="hidden" name="iid" value="'+str(r["id"])+'"><button class="btn btn-primary btn-xs">✅ Done</button></form>' if not r['replied'] else ''}
          </td></tr>"""
    return BASE + topbar("📩 Inquiries","inquiries") + f"""
{alert(msg) if msg else ""}
<div class="card">
  <div class="card-title">📩 Service Inquiries</div>
  <div class="table-wrap"><table>
    <tr><th>User</th><th>Service</th><th>Description</th><th>Date</th><th>Status</th><th>Actions</th></tr>
    {trs}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   DOWNLOADS
# ══════════════════════════════════════════════
@app.route("/downloads")
@login_required
def downloads():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT ud.*,u.username,u.display_name FROM user_downloads ud "
            "LEFT JOIN users u ON ud.user_id=u.telegram_id ORDER BY ud.id DESC LIMIT 100"
        ).fetchall()
    except:
        rows = []
    conn.close()
    now = datetime.now().isoformat()
    trs = ""
    for r in rows:
        r = dict(r)
        expired = r.get("expires_at","") < now
        clicks  = r.get("click_count",0)
        badge   = "badge-red" if expired else ("badge-yellow" if clicks<=1 else "badge-green")
        status  = "Expired" if expired else f"{clicks}/3 clicks"
        mins_left = ""
        if not expired:
            try:
                diff = int((datetime.fromisoformat(r["expires_at"])-datetime.now()).total_seconds()/60)
                mins_left = f"({diff}min left)"
            except: pass
        trs += f"""<tr>
          <td><b>{r.get('display_name','') or r['user_id']}</b><br><small>@{r.get('username','')}</small></td>
          <td>{r.get('product_name','')}</td>
          <td><span class="badge {badge}">{status}</span> <small style="color:var(--muted)">{mins_left}</small></td>
          <td style="color:var(--muted)">{r.get('expires_at','')[:16]}</td>
          <td><a href="{r.get('file_url','')}" target="_blank" class="badge badge-blue">🔗 Link</a></td>
        </tr>"""
    return BASE + topbar("📥 Downloads","downloads") + f"""
<div class="card">
  <div class="card-title">📥 Active Download Access</div>
  <div class="table-wrap"><table>
    <tr><th>User</th><th>Product</th><th>Status</th><th>Expires</th><th>Link</th></tr>
    {trs}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   BROADCAST
# ══════════════════════════════════════════════
@app.route("/broadcast", methods=["GET","POST"])
@login_required
def broadcast():
    msg = ""; ok = True
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
                    payload = _json.dumps({"chat_id":u["telegram_id"],"text":f"📢 *Announcement:*\n\n{text}\n\n_Dev Clin Market | Skyline Technologies_","parse_mode":"Markdown"}).encode()
                    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/sendMessage",data=payload,headers={"Content-Type":"application/json"})
                    urllib.request.urlopen(req,timeout=5); sent+=1
                except: failed+=1
            msg = f"Sent to {sent} users. Failed: {failed}."
    return BASE + topbar("📢 Broadcast","broadcast") + f"""
{alert(msg) if msg else ""}
<div class="card" style="max-width:600px">
  <div class="card-title">📢 Send to All Users</div>
  <form method="POST">
    <div class="form-group">
      <label>Message (supports Markdown bold *text*, italic _text_)</label>
      <textarea name="message" rows="6" placeholder="Type your announcement..." required></textarea>
    </div>
    <button class="btn btn-primary">📢 Send to All Users</button>
  </form>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   MESSAGES
# ══════════════════════════════════════════════
@app.route("/messages")
@login_required
def messages():
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs = "".join([f"""<tr>
      <td>{r['from_name']}</td>
      <td><span class="badge {'badge-blue' if r['direction']=='user_to_admin' else 'badge-green'}">{'User→Admin' if r['direction']=='user_to_admin' else 'Admin→User'}</span></td>
      <td>{r['message']}</td>
      <td style="color:var(--muted)">{r['created_at'][:16]}</td>
    </tr>""" for r in rows])
    return BASE + topbar("💬 Messages","messages") + f"""
<div class="card">
  <div class="card-title">💬 Message Log</div>
  <div class="table-wrap"><table>
    <tr><th>From</th><th>Direction</th><th>Message</th><th>Date</th></tr>
    {trs}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   CATEGORIES
# ══════════════════════════════════════════════
@app.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    conn = get_db()
    msg = ""; ok = True
    if request.method == "POST":
        action = request.form.get("action","")
        if action == "add":
            try:
                cid = request.form.get("cid","").strip()
                icon = request.form.get("icon","📦").strip()
                label = request.form.get("label","").strip()
                conn.execute("INSERT INTO categories VALUES (?,?,?)", (cid, f"{icon} {label}", icon))
                conn.commit(); msg = f"Category '{label}' added!"
            except Exception as e:
                msg = str(e); ok = False
        elif action == "delete":
            conn.execute("DELETE FROM categories WHERE id=?", (request.form.get("cid"),))
            conn.commit(); msg = "Category deleted."
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    rows = "".join([f"""<tr>
      <td>{c['icon']}</td><td>{c['id']}</td><td>{c['label']}</td>
      <td><form method="POST" style="display:inline" onsubmit="return confirm('Delete?')">
        <input type="hidden" name="action" value="delete">
        <input type="hidden" name="cid" value="{c['id']}">
        <button class="btn btn-danger btn-xs">Delete</button>
      </form></td></tr>""" for c in cats])
    return BASE + topbar("📂 Categories","categories") + f"""
{alert(msg,ok) if msg else ""}
<div class="card" style="max-width:500px">
  <div class="card-title">➕ Add Category</div>
  <form method="POST">
    <input type="hidden" name="action" value="add">
    <div class="grid-3">
      <div class="form-group"><label>ID</label><input name="cid" placeholder="education" required></div>
      <div class="form-group"><label>Icon</label><input name="icon" placeholder="📚" required></div>
      <div class="form-group"><label>Label</label><input name="label" placeholder="Education" required></div>
    </div>
    <button class="btn btn-primary">➕ Add</button>
  </form>
</div>
<div class="card">
  <div class="card-title">📂 All Categories</div>
  <div class="table-wrap"><table>
    <tr><th>Icon</th><th>ID</th><th>Label</th><th>Action</th></tr>
    {rows}
  </table></div>
</div></div></body></html>"""

# ══════════════════════════════════════════════
#   SETTINGS — FULL WITH BOT SETTINGS
# ══════════════════════════════════════════════
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    msg = ""
    if request.method == "POST":
        fields = [
            "mpesa_name","mpesa_number","group_chat_link",
            "whatsapp_number","instagram_link","portfolio_link",
            "bot_banner_image","banner_shop","banner_payment",
            "banner_services","banner_contact","banner_about",
            "banner_group","banner_rate","banner_links","banner_account",
            "quotes_enabled","bot_name","company_name","tagline",
            "admin_telegram","contact_whatsapp"
        ]
        for f in fields:
            val = request.form.get(f,"")
            if val != "":
                save_setting(f, val)
        msg = "Settings saved!"
    s = get_settings()
    def f(key, label, placeholder="", typ="text"):
        val = s.get(key,"")
        if typ == "select":
            o1 = "selected" if val=="1" else ""
            o2 = "selected" if val=="0" else ""
            return f'<div class="form-group"><label>{label}</label><select name="{key}"><option value="1" {o1}>Enabled</option><option value="0" {o2}>Disabled</option></select></div>'
        return f'<div class="form-group"><label>{label}</label><input type="{typ}" name="{key}" value="{val}" placeholder="{placeholder}"></div>'

    return BASE + topbar("⚙️ Settings","settings") + f"""
{alert(msg) if msg else ""}
<form method="POST">
  <div class="grid-2">
    <div>
      <div class="card">
        <div class="card-title">💳 M-Pesa Settings</div>
        {f("mpesa_name","Receiver Name","Clinton Oduor")}
        {f("mpesa_number","Receiver Number","0743810633")}
      </div>
      <div class="card">
        <div class="card-title">🤖 Bot Identity</div>
        {f("bot_name","Bot Name","Dev Clin Market")}
        {f("company_name","Company Name","Skyline Technologies")}
        {f("tagline","Tagline","Elevating Digital Solutions")}
        {f("admin_telegram","Admin Telegram Handle","@yourusername")}
      </div>
      <div class="card">
        <div class="card-title">🔗 Contact Links</div>
        {f("contact_whatsapp","WhatsApp Number (full)","17808518629")}
        {f("instagram_link","Instagram URL","https://instagram.com/...")}
        {f("portfolio_link","Portfolio URL","https://devclin.netlify.app")}
        {f("group_chat_link","Group Chat Link","https://t.me/...")}
      </div>
      <div class="card">
        <div class="card-title">⏰ Auto Quotes</div>
        {f("quotes_enabled","Daily Motivational Quotes","","select")}
      </div>
    </div>
    <div>
      <div class="card">
        <div class="card-title">🖼 Banner Images (paste image URLs)</div>
        {f("bot_banner_image","Default Banner")}
        {f("banner_shop","Shop Banner")}
        {f("banner_payment","Payment Banner")}
        {f("banner_services","Services Banner")}
        {f("banner_contact","Contact Banner")}
        {f("banner_about","About Banner")}
        {f("banner_group","Group Chat Banner")}
        {f("banner_rate","Rate Us Banner")}
        {f("banner_links","Links Banner")}
        {f("banner_account","Dashboard Banner")}
      </div>
    </div>
  </div>
  <button class="btn btn-primary" style="padding:12px 32px">💾 Save All Settings</button>
</form>
</div></body></html>"""

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    run()
