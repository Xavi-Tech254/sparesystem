import os, sqlite3, urllib.request, json as _json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devclin_skyline_2025")
DB_PATH   = "devclin.db"
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin1234")

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
    except: return {}

def save_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit(); conn.close()

def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if not session.get("admin_logged_in"): return redirect(url_for("login"))
        return f(*a, **kw)
    return d

def flash(msg, ok=True):
    if not msg: return ""
    return f'<div class="flash {"flash-ok" if ok else "flash-err"}">{"✅" if ok else "❌"} {msg}</div>'

# ══════════════════════════════════════════════════════════════
#  GLOBAL CSS
# ══════════════════════════════════════════════════════════════
CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#06080f;
  --surface:#0b0e1a;
  --card:#0f1221;
  --card2:#131728;
  --border:#1a2035;
  --border2:#1e2540;
  --accent:#4f9eff;
  --accent-glow:#4f9eff30;
  --violet:#7c6ff7;
  --green:#2dd4a0;
  --red:#f06060;
  --yellow:#f5a623;
  --purple:#9b6af7;
  --text:#dde4f0;
  --sub:#7a8aaa;
  --muted:#3d4a63;
  --radius:12px;
  --radius-sm:8px;
  --sidebar-w:245px;
  --topbar-h:60px;
  --transition:.2s ease;
}
html,body{height:100%;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
           font-size:14px;background:var(--bg);color:var(--text);line-height:1.6}
a{color:var(--accent);text-decoration:none}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:10px}

/* ── SIDEBAR ── */
.sidebar{
  position:fixed;top:0;left:0;bottom:0;width:var(--sidebar-w);
  background:var(--surface);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;z-index:400;
  transition:transform var(--transition);
}
.sb-top{
  padding:22px 20px 18px;
  border-bottom:1px solid var(--border);
}
.sb-logo{
  font-size:1.25rem;font-weight:800;letter-spacing:-.3px;
  background:linear-gradient(135deg,var(--accent),var(--violet));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  display:flex;align-items:center;gap:8px;
}
.sb-logo span{font-size:1.4rem;-webkit-text-fill-color:initial}
.sb-company{font-size:.72rem;color:var(--sub);margin-top:3px;padding-left:2px}
.sb-nav{flex:1;overflow-y:auto;padding:12px 10px}
.sb-section{font-size:.65rem;font-weight:700;color:var(--muted);
             text-transform:uppercase;letter-spacing:1px;
             padding:14px 10px 6px}
.nav-link{
  display:flex;align-items:center;gap:10px;
  padding:9px 12px;border-radius:var(--radius-sm);
  color:var(--sub);font-size:.85rem;font-weight:500;
  transition:all var(--transition);margin-bottom:2px;
  border:1px solid transparent;
}
.nav-link .ni{font-size:.95rem;width:20px;text-align:center;flex-shrink:0}
.nav-link:hover{color:var(--text);background:var(--card2)}
.nav-link.on{color:var(--accent);background:var(--accent-glow);border-color:var(--border2)}
.sb-bottom{padding:12px 10px;border-top:1px solid var(--border)}
.nav-link.logout{color:var(--red)}
.nav-link.logout:hover{background:#f0606015;border-color:#f0606030}

/* ── MAIN ── */
.main{margin-left:var(--sidebar-w);min-height:100vh;display:flex;flex-direction:column}

/* ── TOPBAR ── */
.topbar{
  height:var(--topbar-h);
  background:var(--surface);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 24px;gap:14px;
  position:sticky;top:0;z-index:300;
}
.topbar .ham{display:none;background:none;border:none;color:var(--text);font-size:1.2rem;cursor:pointer}
.topbar .page-title{font-size:.95rem;font-weight:700;color:var(--text)}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.live-dot{display:flex;align-items:center;gap:5px;font-size:.75rem;color:var(--green)}
.live-dot::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--green);
                   box-shadow:0 0 6px var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ── OVERLAY ── */
.overlay{display:none;position:fixed;inset:0;background:#00000080;z-index:350;backdrop-filter:blur(2px)}
.overlay.show{display:block}

/* ── CONTENT ── */
.content{padding:24px;flex:1}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:22px}
.stat-card{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px 14px;position:relative;overflow:hidden;
  transition:transform var(--transition),border-color var(--transition);
}
.stat-card:hover{transform:translateY(-2px);border-color:var(--border2)}
.stat-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--violet));
}
.stat-ico{font-size:1.4rem;margin-bottom:10px}
.stat-num{font-size:1.6rem;font-weight:800;color:var(--accent);line-height:1;margin-bottom:4px}
.stat-lbl{font-size:.72rem;color:var(--sub);font-weight:500}

/* ── CARDS ── */
.card{
  background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);margin-bottom:18px;overflow:hidden;
}
.card-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 18px;border-bottom:1px solid var(--border);
  background:var(--card2);
}
.card-title{font-size:.82rem;font-weight:700;color:var(--text);
             display:flex;align-items:center;gap:8px}
.card-title .ct-icon{font-size:1rem}
.card-actions{display:flex;gap:8px;align-items:center}
.card-body{padding:18px}
.card-body-p0{padding:0}

/* ── ADD PANEL (slides in) ── */
.add-panel{
  background:var(--surface);border-bottom:1px solid var(--border);
  padding:0;max-height:0;overflow:hidden;
  transition:max-height .35s ease,padding .35s ease;
}
.add-panel.open{max-height:900px;padding:20px 18px}

/* ── FORM ── */
.form-grid{display:grid;gap:14px}
.fg{display:flex;flex-direction:column;gap:5px}
.fg label{font-size:.75rem;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:.4px}
input,textarea,select{
  background:var(--bg);border:1px solid var(--border2);color:var(--text);
  border-radius:var(--radius-sm);padding:9px 12px;font-size:.85rem;
  width:100%;font-family:inherit;transition:border-color var(--transition),box-shadow var(--transition);
}
input:focus,textarea:focus,select:focus{
  outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow);
}
textarea{resize:vertical;min-height:80px}
.form-row-2{grid-template-columns:1fr 1fr}
.form-row-3{grid-template-columns:1fr 1fr 1fr}

/* ── TABLE ── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:540px}
thead tr{background:var(--surface)}
th{
  padding:11px 16px;text-align:left;font-size:.72rem;font-weight:700;
  color:var(--sub);text-transform:uppercase;letter-spacing:.6px;
  border-bottom:1px solid var(--border);white-space:nowrap;
}
td{
  padding:12px 16px;border-bottom:1px solid var(--border);
  font-size:.84rem;vertical-align:middle;
}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:#ffffff03}

/* ── BUTTONS ── */
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:6px;
  border:none;cursor:pointer;font-family:inherit;font-weight:600;
  border-radius:var(--radius-sm);transition:all var(--transition);white-space:nowrap;
  letter-spacing:.2px;
}
.btn:hover{filter:brightness(1.12);transform:translateY(-1px)}
.btn:active{transform:translateY(0);filter:brightness(.95)}
/* Sizes */
.btn-lg{padding:11px 24px;font-size:.88rem}
.btn-md{padding:9px 18px;font-size:.83rem}
.btn-sm{padding:6px 14px;font-size:.78rem}
.btn-xs{padding:4px 11px;font-size:.72rem;border-radius:6px}
.btn-icon{padding:7px;border-radius:8px;font-size:.85rem}
/* Variants */
.btn-primary{background:linear-gradient(135deg,#4f9eff,#2563eb);color:#fff}
.btn-success{background:linear-gradient(135deg,#2dd4a0,#059669);color:#fff}
.btn-warning{background:linear-gradient(135deg,#f5a623,#d97706);color:#000}
.btn-danger {background:linear-gradient(135deg,#f06060,#dc2626);color:#fff}
.btn-purple {background:linear-gradient(135deg,#9b6af7,#7c3aed);color:#fff}
.btn-ghost  {background:transparent;border:1px solid var(--border2);color:var(--sub)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-glow)}
.btn-accent {background:var(--accent-glow);border:1px solid var(--accent);color:var(--accent)}

/* ── BADGES ── */
.badge{
  display:inline-flex;align-items:center;gap:4px;
  padding:3px 9px;border-radius:20px;font-size:.71rem;font-weight:700;white-space:nowrap;
}
.bg{background:#2dd4a020;color:var(--green);border:1px solid #2dd4a035}
.br{background:#f0606020;color:var(--red);border:1px solid #f0606035}
.by{background:#f5a62320;color:var(--yellow);border:1px solid #f5a62335}
.bb{background:#4f9eff20;color:var(--accent);border:1px solid #4f9eff35}
.bv{background:#9b6af720;color:var(--purple);border:1px solid #9b6af735}

/* ── FLASH ── */
.flash{
  padding:12px 16px;border-radius:var(--radius-sm);margin-bottom:16px;
  font-size:.84rem;display:flex;align-items:center;gap:8px;font-weight:500;
}
.flash-ok {background:#2dd4a012;border:1px solid #2dd4a030;color:var(--green)}
.flash-err{background:#f0606012;border:1px solid #f0606030;color:var(--red)}

/* ── INLINE EDIT PANEL ── */
.edit-panel{
  display:none;margin-top:10px;
  background:var(--surface);border:1px solid var(--border2);
  border-radius:var(--radius-sm);padding:14px;
}
.edit-panel.open{display:block}

/* ── TWO COL ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}

/* ── SECTION DIVIDER ── */
.divider{height:1px;background:var(--border);margin:16px 0}

/* ── ACTION CELL ── */
.action-cell{display:flex;flex-direction:column;gap:6px;min-width:170px}
.action-row{display:flex;gap:5px;flex-wrap:wrap}

/* ── LOGIN ── */
.login-page{
  display:flex;align-items:center;justify-content:center;min-height:100vh;
  background:radial-gradient(ellipse 80% 60% at 50% 0%,#0d1a35,var(--bg));
}
.login-box{
  background:var(--card);border:1px solid var(--border2);border-radius:16px;
  padding:44px 40px;width:100%;max-width:380px;
  box-shadow:0 24px 64px #00000060;
}
.login-logo{text-align:center;margin-bottom:30px}
.login-logo .logotype{
  font-size:1.6rem;font-weight:900;
  background:linear-gradient(135deg,var(--accent),var(--violet));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.login-logo .sub{font-size:.78rem;color:var(--sub);margin-top:5px}
.login-submit{width:100%;padding:12px;font-size:.9rem;margin-top:8px}

/* ── EMPTY STATE ── */
.empty{text-align:center;padding:48px 24px;color:var(--sub)}
.empty .e-ico{font-size:2.5rem;margin-bottom:12px}
.empty .e-txt{font-size:.88rem}

/* ── RESPONSIVE ── */
@media(max-width:1100px){.stat-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:860px){
  .stat-grid{grid-template-columns:repeat(2,1fr)}
  .two-col{grid-template-columns:1fr}
  .form-row-3{grid-template-columns:1fr 1fr}
}
@media(max-width:680px){
  :root{--sidebar-w:0px}
  .sidebar{transform:translateX(-245px);width:245px}
  .sidebar.open{transform:translateX(0)}
  .overlay.show{display:block}
  .topbar .ham{display:block}
  .main{margin-left:0}
  .content{padding:14px}
  .form-row-2,.form-row-3{grid-template-columns:1fr}
  .stat-grid{grid-template-columns:1fr 1fr;gap:10px}
  .stat-num{font-size:1.3rem}
  .card-body{padding:14px}
  .login-box{padding:32px 24px}
}
@media(max-width:400px){
  .stat-grid{grid-template-columns:1fr}
}
"""

# ══════════════════════════════════════════════════════════════
#  PAGE SHELL
# ══════════════════════════════════════════════════════════════
NAV = [
    ("/",           "📊", "Dashboard",   "dashboard",  "MAIN"),
    ("/products",   "📦", "Products",    "products",   None),
    ("/categories", "📂", "Categories",  "categories", None),
    ("/orders",     "🛒", "Orders",      "orders",     "SALES"),
    ("/users",      "👥", "Users",       "users",      None),
    ("/reviews",    "⭐", "Reviews",     "reviews",    None),
    ("/inquiries",  "📩", "Inquiries",   "inquiries",  None),
    ("/broadcast",  "📢", "Broadcast",   "broadcast",  "TOOLS"),
    ("/downloads",  "📥", "Downloads",   "downloads",  None),
    ("/messages",   "💬", "Messages",    "messages",   None),
    ("/settings",   "⚙️", "Settings",    "settings",   None),
]

def shell(page_title, active, body):
    links = ""
    for href, ico, label, key, section in NAV:
        if section:
            links += f'<div class="sb-section">{section}</div>'
        cls = "on" if active == key else ""
        links += f'<a href="{href}" class="nav-link {cls}"><span class="ni">{ico}</span>{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title} · Dev Clin</title>
<style>{CSS}</style>
</head><body>
<div class="overlay" id="ov" onclick="sb(0)"></div>
<aside class="sidebar" id="sidebar">
  <div class="sb-top">
    <div class="sb-logo"><span>⚡</span>Dev Clin</div>
    <div class="sb-company">Skyline Technologies</div>
  </div>
  <nav class="sb-nav">{links}</nav>
  <div class="sb-bottom">
    <a href="/logout" class="nav-link logout"><span class="ni">🚪</span>Logout</a>
  </div>
</aside>
<div class="main">
  <header class="topbar">
    <button class="ham" onclick="sb(1)">☰</button>
    <span class="page-title">{page_title}</span>
    <div class="topbar-right">
      <span class="live-dot">Live</span>
    </div>
  </header>
  <main class="content">{body}</main>
</div>
<script>
function sb(o){{
  document.getElementById('sidebar').classList.toggle('open',o);
  document.getElementById('ov').classList.toggle('show',o);
}}
function toggle(id){{
  var el=document.getElementById(id);
  el.classList.toggle('open');
}}
function show(id){{document.getElementById(id).classList.add('open')}}
function hide(id){{document.getElementById(id).classList.remove('open')}}
function togglePanel(btnId,panelId){{
  var p=document.getElementById(panelId);
  var open=p.classList.toggle('open');
  var btn=document.getElementById(btnId);
  if(btn)btn.textContent=open?'✕ Close':'➕ Add New';
}}
</script>
</body></html>"""

# ══════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════
@app.route("/login", methods=["GET","POST"])
def login():
    err=""
    if request.method=="POST":
        if request.form.get("password","") == ADMIN_PWD:
            session["admin_logged_in"]=True; return redirect("/")
        err="Incorrect password. Try again."
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login · Dev Clin</title><style>{CSS}</style></head><body>
<div class="login-page"><div class="login-box">
  <div class="login-logo">
    <div class="logotype">⚡ Dev Clin</div>
    <div class="sub">Skyline Technologies — Admin Panel</div>
  </div>
  {flash(err,False) if err else ""}
  <form method="POST">
    <div class="fg" style="margin-bottom:16px">
      <label>Password</label>
      <input type="password" name="password" placeholder="Enter admin password" required autofocus>
    </div>
    <button class="btn btn-primary login-submit">🔓 Sign In</button>
  </form>
</div></div></body></html>"""

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def dashboard():
    conn=get_db()
    tu=conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    to=conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    vo=conn.execute("SELECT COUNT(*) FROM orders WHERE status='verified'").fetchone()[0]
    ap=conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
    pi=conn.execute("SELECT COUNT(*) FROM service_inquiries WHERE replied=0").fetchone()[0]
    try: ad=conn.execute("SELECT COUNT(*) FROM user_downloads WHERE expires_at > ?",(datetime.now().isoformat(),)).fetchone()[0]
    except: ad=0
    rec_o=conn.execute("SELECT display_name,product_name,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 8").fetchall()
    rec_u=conn.execute("SELECT username,display_name,points,discount_balance,joined_at FROM users ORDER BY joined_at DESC LIMIT 6").fetchall()
    conn.close()

    stats=f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-ico">👥</div><div class="stat-num">{tu}</div><div class="stat-lbl">Total Users</div></div>
  <div class="stat-card"><div class="stat-ico">📦</div><div class="stat-num">{ap}</div><div class="stat-lbl">Active Products</div></div>
  <div class="stat-card"><div class="stat-ico">✅</div><div class="stat-num">{vo}</div><div class="stat-lbl">Verified Sales</div></div>
  <div class="stat-card"><div class="stat-ico">🛒</div><div class="stat-num">{to}</div><div class="stat-lbl">Total Orders</div></div>
  <div class="stat-card"><div class="stat-ico">📩</div><div class="stat-num">{pi}</div><div class="stat-lbl">Pending Inquiries</div></div>
  <div class="stat-card"><div class="stat-ico">📥</div><div class="stat-num">{ad}</div><div class="stat-lbl">Active Downloads</div></div>
</div>"""

    o_rows="".join([f"""<tr>
      <td><b>{r['display_name']}</b></td><td>{r['product_name']}</td><td>{r['amount']}</td>
      <td><span class="badge {'bg' if r['status']=='verified' else 'by'}">{r['status']}</span></td>
      <td style="color:var(--sub)">{r['created_at'][:10]}</td></tr>""" for r in rec_o])

    u_rows="".join([f"""<tr>
      <td><b>{u['display_name']}</b><br><small style="color:var(--sub)">@{u['username']}</small></td>
      <td><span class="badge bb">{u['points']} pts</span></td>
      <td>KSh {u['discount_balance']:,.0f}</td>
      <td style="color:var(--sub)">{(u['joined_at'] or '')[:10]}</td></tr>""" for u in rec_u])

    body=stats+f"""
<div class="two-col">
  <div class="card">
    <div class="card-header">
      <div class="card-title"><span class="ct-icon">🛒</span>Recent Orders</div>
      <a href="/orders" class="btn btn-ghost btn-xs">View All</a>
    </div>
    <div class="card-body-p0"><div class="tbl-wrap"><table>
      <thead><tr><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
      <tbody>{o_rows if o_rows else '<tr><td colspan="5"><div class="empty"><div class="e-ico">🛒</div><div class="e-txt">No orders yet</div></div></td></tr>'}</tbody>
    </table></div></div>
  </div>
  <div class="card">
    <div class="card-header">
      <div class="card-title"><span class="ct-icon">👥</span>Recent Users</div>
      <a href="/users" class="btn btn-ghost btn-xs">View All</a>
    </div>
    <div class="card-body-p0"><div class="tbl-wrap"><table>
      <thead><tr><th>User</th><th>Points</th><th>Discount</th><th>Joined</th></tr></thead>
      <tbody>{u_rows if u_rows else '<tr><td colspan="4"><div class="empty"><div class="e-ico">👥</div><div class="e-txt">No users yet</div></div></td></tr>'}</tbody>
    </table></div></div>
  </div>
</div>"""
    return shell("📊 Dashboard","dashboard",body)

# ══════════════════════════════════════════════════════════════
#  PRODUCTS
# ══════════════════════════════════════════════════════════════
@app.route("/products", methods=["GET","POST"])
@login_required
def products():
    conn=get_db(); msg=""; ok=True
    if request.method=="POST":
        a=request.form.get("action","")
        if a=="add":
            try:
                conn.execute(
                    "INSERT INTO products (id,name,category,price,price_value,type,desc,link,icon,active,image_url,sale_price) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)",
                    (request.form.get("pid","").strip(),request.form.get("name","").strip(),
                     request.form.get("category","").strip(),request.form.get("price","").strip(),
                     float(request.form.get("price_value",0) or 0),request.form.get("ptype","").strip(),
                     request.form.get("desc","").strip(),request.form.get("link","").strip(),
                     request.form.get("icon","📦").strip(),request.form.get("image_url","").strip(),
                     float(request.form.get("sale_price",0) or 0)))
                conn.commit(); msg=f"Product added successfully!"
            except Exception as e: msg=str(e); ok=False
        elif a=="toggle":
            r=conn.execute("SELECT active FROM products WHERE id=?",(request.form.get("pid"),)).fetchone()
            if r:
                conn.execute("UPDATE products SET active=? WHERE id=?",(0 if r["active"] else 1,request.form.get("pid")))
                conn.commit()
        elif a=="delete":
            conn.execute("DELETE FROM products WHERE id=?",(request.form.get("pid"),)); conn.commit(); msg="Product deleted."
        elif a=="setlink":
            conn.execute("UPDATE products SET link=? WHERE id=?",(request.form.get("link","").strip(),request.form.get("pid")))
            conn.commit(); msg="Download link saved!"
        elif a=="setsale":
            conn.execute("UPDATE products SET sale_price=? WHERE id=?",(float(request.form.get("sale_price",0) or 0),request.form.get("pid")))
            conn.commit(); msg="Sale price updated!"

    prods=conn.execute("SELECT * FROM products ORDER BY active DESC,name").fetchall()
    cats=conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    cat_opts="".join([f'<option value="{c["id"]}">{c["label"]}</option>' for c in cats])

    rows=""
    for p in [dict(x) for x in prods]:
        sale_d=f"KSh {p['sale_price']:,.0f}" if p.get("sale_price") else "—"
        link_d=f'<span class="badge bg">🔗 Set</span>' if p.get("link") else '<span class="badge br">No link</span>'
        status=f'<span class="badge bg">Active</span>' if p["active"] else '<span class="badge br">Off</span>'
        pid=p["id"]
        rows+=f"""<tr>
          <td>
            <div style="font-weight:600;color:var(--text)">{p.get('icon','')} {p['name']}</div>
            <div style="color:var(--sub);font-size:.73rem;margin-top:2px">ID: {pid}</div>
          </td>
          <td><span class="badge bv">{p['category']}</span></td>
          <td style="font-weight:600">{p['price']}</td>
          <td>{sale_d}</td>
          <td><span class="badge bb">{p.get('type','—')}</span></td>
          <td>{link_d}</td>
          <td>{status}</td>
          <td>
            <div class="action-cell">
              <div class="action-row">
                <form method="POST" style="margin:0">
                  <input type="hidden" name="action" value="toggle">
                  <input type="hidden" name="pid" value="{pid}">
                  <button class="btn btn-warning btn-xs" title="Toggle active/inactive">
                    {'⏸ Disable' if p['active'] else '▶ Enable'}
                  </button>
                </form>
                <form method="POST" style="margin:0" onsubmit="return confirm('Delete {p['name']}?')">
                  <input type="hidden" name="action" value="delete">
                  <input type="hidden" name="pid" value="{pid}">
                  <button class="btn btn-danger btn-xs">🗑 Delete</button>
                </form>
              </div>
              <div class="action-row">
                <button class="btn btn-accent btn-xs" onclick="toggle('lp-{pid}')">🔗 Set Link</button>
                <button class="btn btn-success btn-xs" onclick="toggle('sp-{pid}')">🔥 Sale</button>
              </div>
              <div class="edit-panel" id="lp-{pid}">
                <form method="POST" style="margin:0">
                  <input type="hidden" name="action" value="setlink">
                  <input type="hidden" name="pid" value="{pid}">
                  <div class="fg" style="margin-bottom:8px">
                    <label>Download URL</label>
                    <input name="link" value="{p.get('link','')}" placeholder="https://drive.google.com/...">
                  </div>
                  <div class="action-row">
                    <button class="btn btn-primary btn-xs">💾 Save Link</button>
                    <button type="button" class="btn btn-ghost btn-xs" onclick="hide('lp-{pid}')">✕</button>
                  </div>
                </form>
              </div>
              <div class="edit-panel" id="sp-{pid}">
                <form method="POST" style="margin:0">
                  <input type="hidden" name="action" value="setsale">
                  <input type="hidden" name="pid" value="{pid}">
                  <div class="fg" style="margin-bottom:8px">
                    <label>Sale Price (0 = off)</label>
                    <input name="sale_price" type="number" step="0.01" value="{p.get('sale_price',0) or 0}">
                  </div>
                  <div class="action-row">
                    <button class="btn btn-success btn-xs">💾 Save</button>
                    <button type="button" class="btn btn-ghost btn-xs" onclick="hide('sp-{pid}')">✕</button>
                  </div>
                </form>
              </div>
            </div>
          </td>
        </tr>"""

    body=f"""
{flash(msg,ok) if msg else ""}
<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">📦</span>All Products <span class="badge bb" style="margin-left:6px">{len(prods)}</span></div>
    <div class="card-actions">
      <button id="add-prod-btn" class="btn btn-primary btn-sm" onclick="togglePanel('add-prod-btn','add-prod-panel')">➕ Add New</button>
    </div>
  </div>
  <div class="add-panel" id="add-prod-panel">
    <form method="POST">
      <input type="hidden" name="action" value="add">
      <div class="form-grid form-row-3" style="margin-bottom:14px">
        <div class="fg"><label>Product ID *</label><input name="pid" placeholder="e.g. p8" required></div>
        <div class="fg"><label>Product Name *</label><input name="name" placeholder="e.g. Python Course" required></div>
        <div class="fg"><label>Category *</label><select name="category">{cat_opts}</select></div>
        <div class="fg"><label>Price Label *</label><input name="price" placeholder="KSh 500" required></div>
        <div class="fg"><label>Price (number) *</label><input name="price_value" type="number" step="0.01" placeholder="500" required></div>
        <div class="fg"><label>File Type</label><input name="ptype" placeholder="PDF / APK / MP4"></div>
        <div class="fg"><label>Icon</label><input name="icon" value="📦" placeholder="📦"></div>
        <div class="fg"><label>Download Link</label><input name="link" placeholder="https://drive.google.com/..."></div>
        <div class="fg"><label>Sale Price (0=off)</label><input name="sale_price" type="number" step="0.01" value="0"></div>
      </div>
      <div class="fg" style="margin-bottom:14px"><label>Description *</label><textarea name="desc" placeholder="Describe this product..." required></textarea></div>
      <div class="fg" style="margin-bottom:16px"><label>Product Image URL</label><input name="image_url" placeholder="https://..."></div>
      <div class="action-row">
        <button class="btn btn-primary btn-md">➕ Add Product</button>
        <button type="button" class="btn btn-ghost btn-md" onclick="togglePanel('add-prod-btn','add-prod-panel')">✕ Cancel</button>
      </div>
    </form>
  </div>
  <div class="card-body-p0">
    <div class="tbl-wrap"><table>
      <thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Sale</th><th>Type</th><th>Link</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>{rows if rows else '<tr><td colspan="8"><div class="empty"><div class="e-ico">📦</div><div class="e-txt">No products yet. Add one above.</div></div></td></tr>'}</tbody>
    </table></div>
  </div>
</div>"""
    return shell("📦 Products","products",body)

# ══════════════════════════════════════════════════════════════
#  CATEGORIES
# ══════════════════════════════════════════════════════════════
@app.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    conn=get_db(); msg=""; ok=True
    if request.method=="POST":
        a=request.form.get("action","")
        if a=="add":
            try:
                cid=request.form.get("cid","").strip()
                icon=request.form.get("icon","📦").strip()
                label=request.form.get("label","").strip()
                conn.execute("INSERT INTO categories VALUES (?,?,?)",(cid,f"{icon} {label}",icon))
                conn.commit(); msg=f"Category '{label}' added!"
            except Exception as e: msg=str(e); ok=False
        elif a=="delete":
            conn.execute("DELETE FROM categories WHERE id=?",(request.form.get("cid"),))
            conn.commit(); msg="Category deleted."
    cats=conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    rows="".join([f"""<tr>
      <td style="font-size:1.2rem">{c['icon']}</td>
      <td><code style="background:var(--surface);padding:2px 8px;border-radius:5px;font-size:.8rem;color:var(--accent)">{c['id']}</code></td>
      <td style="font-weight:500">{c['label']}</td>
      <td>
        <form method="POST" style="margin:0" onsubmit="return confirm('Delete {c["label"]}?')">
          <input type="hidden" name="action" value="delete">
          <input type="hidden" name="cid" value="{c['id']}">
          <button class="btn btn-danger btn-xs">🗑 Delete</button>
        </form>
      </td>
    </tr>""" for c in cats])

    body=f"""
{flash(msg,ok) if msg else ""}
<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">📂</span>All Categories <span class="badge bb" style="margin-left:6px">{len(cats)}</span></div>
    <div class="card-actions">
      <button id="add-cat-btn" class="btn btn-primary btn-sm" onclick="togglePanel('add-cat-btn','add-cat-panel')">➕ Add New</button>
    </div>
  </div>
  <div class="add-panel" id="add-cat-panel">
    <form method="POST">
      <input type="hidden" name="action" value="add">
      <div class="form-grid form-row-3" style="margin-bottom:16px">
        <div class="fg"><label>ID (no spaces)</label><input name="cid" placeholder="education" required></div>
        <div class="fg"><label>Icon</label><input name="icon" placeholder="📚" required></div>
        <div class="fg"><label>Label</label><input name="label" placeholder="Education" required></div>
      </div>
      <div class="action-row">
        <button class="btn btn-primary btn-md">➕ Add Category</button>
        <button type="button" class="btn btn-ghost btn-md" onclick="togglePanel('add-cat-btn','add-cat-panel')">✕ Cancel</button>
      </div>
    </form>
  </div>
  <div class="card-body-p0">
    <div class="tbl-wrap"><table>
      <thead><tr><th>Icon</th><th>ID</th><th>Label</th><th>Action</th></tr></thead>
      <tbody>{rows if rows else '<tr><td colspan="4"><div class="empty"><div class="e-ico">📂</div><div class="e-txt">No categories yet.</div></div></td></tr>'}</tbody>
    </table></div>
  </div>
</div>"""
    return shell("📂 Categories","categories",body)

# ══════════════════════════════════════════════════════════════
#  ORDERS
# ══════════════════════════════════════════════════════════════
@app.route("/orders")
@login_required
def orders():
    conn=get_db()
    rows=conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs="".join([f"""<tr>
      <td>
        <div style="font-weight:600">{r['display_name']}</div>
        <div style="color:var(--sub);font-size:.73rem">@{r['username']}</div>
      </td>
      <td>{r['product_name']}</td>
      <td style="font-weight:600;color:var(--green)">{r['amount']}</td>
      <td><span class="badge {'bg' if r['status']=='verified' else 'by'}">{r['status']}</span></td>
      <td style="color:var(--sub)">{r['created_at'][:16]}</td>
      <td style="color:var(--sub);font-size:.78rem;max-width:200px">{(r['mpesa_msg'] or '')[:55]}{'...' if len(r['mpesa_msg'] or '')>55 else ''}</td>
    </tr>""" for r in rows])
    body=f"""<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">🛒</span>All Orders <span class="badge bb" style="margin-left:6px">{len(rows)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th><th>Date</th><th>M-Pesa SMS</th></tr></thead>
    <tbody>{trs if trs else '<tr><td colspan="6"><div class="empty"><div class="e-ico">🛒</div><div class="e-txt">No orders yet</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("🛒 Orders","orders",body)

# ══════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════
@app.route("/users", methods=["GET","POST"])
@login_required
def users():
    conn=get_db(); msg=""; ok=True
    if request.method=="POST":
        a=request.form.get("action",""); uid=request.form.get("uid")
        if a=="grant_discount":
            amt=float(request.form.get("amount",0) or 0)
            conn.execute("UPDATE users SET discount_balance=discount_balance+? WHERE telegram_id=?",(amt,uid))
            conn.commit(); msg=f"KSh {amt:,.0f} discount granted!"
        elif a=="reset_points":
            conn.execute("UPDATE users SET points=0 WHERE telegram_id=?",(uid,)); conn.commit(); msg="Points reset."
        elif a=="clear_discount":
            conn.execute("UPDATE users SET discount_balance=0 WHERE telegram_id=?",(uid,)); conn.commit(); msg="Discount cleared."

    ul=conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    rows=""
    for u in [dict(x) for x in ul]:
        p=conn.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='verified'",(u['telegram_id'],)).fetchone()[0]
        uid=u['telegram_id']
        rows+=f"""<tr>
          <td>
            <div style="font-weight:600">{u['display_name']}</div>
            <div style="color:var(--sub);font-size:.73rem">@{u['username']} · {uid}</div>
          </td>
          <td><span class="badge bb">{u['points']} pts</span></td>
          <td><span class="badge bg">KSh {u['discount_balance']:,.0f}</span></td>
          <td style="text-align:center;font-weight:600">{p}</td>
          <td style="color:var(--sub)">{(u.get('joined_at','') or '')[:10]}</td>
          <td>
            <div class="action-cell">
              <form method="POST" style="margin:0">
                <input type="hidden" name="action" value="grant_discount">
                <input type="hidden" name="uid" value="{uid}">
                <div style="display:flex;gap:6px;align-items:center">
                  <input type="number" name="amount" placeholder="KSh amount"
                         style="width:110px;padding:5px 8px;font-size:.78rem">
                  <button class="btn btn-success btn-xs">+ Grant</button>
                </div>
              </form>
              <div class="action-row" style="margin-top:4px">
                <form method="POST" style="margin:0">
                  <input type="hidden" name="action" value="reset_points">
                  <input type="hidden" name="uid" value="{uid}">
                  <button class="btn btn-warning btn-xs">↺ Reset Points</button>
                </form>
                <form method="POST" style="margin:0">
                  <input type="hidden" name="action" value="clear_discount">
                  <input type="hidden" name="uid" value="{uid}">
                  <button class="btn btn-danger btn-xs">✕ Clear Discount</button>
                </form>
              </div>
            </div>
          </td>
        </tr>"""
    conn.close()
    body=f"""
{flash(msg,ok) if msg else ""}
<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">👥</span>All Users <span class="badge bb" style="margin-left:6px">{len(ul)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>User</th><th>Points</th><th>Discount</th><th>Purchases</th><th>Joined</th><th style="min-width:220px">Actions</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="6"><div class="empty"><div class="e-ico">👥</div><div class="e-txt">No users yet</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("👥 Users","users",body)

# ══════════════════════════════════════════════════════════════
#  REVIEWS
# ══════════════════════════════════════════════════════════════
@app.route("/reviews")
@login_required
def reviews():
    conn=get_db()
    rows=conn.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs="".join([f"""<tr>
      <td><div style="font-weight:600">{r['display_name']}</div><div style="color:var(--sub);font-size:.73rem">@{r['username']}</div></td>
      <td><span class="badge {'bb' if r['type']=='bot' else 'bg'}">{r['type']}</span></td>
      <td>{r['product_name']}</td>
      <td style="color:var(--yellow)">{'⭐'*(r['rating'] or 0)} <small style="color:var(--sub)">({r['rating']}/5)</small></td>
      <td style="max-width:220px;white-space:normal">{r['review'] or '—'}</td>
      <td style="color:var(--sub)">{r['created_at'][:10]}</td>
    </tr>""" for r in rows])
    body=f"""<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">⭐</span>All Reviews <span class="badge bb" style="margin-left:6px">{len(rows)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>User</th><th>Type</th><th>Product</th><th>Rating</th><th>Review</th><th>Date</th></tr></thead>
    <tbody>{trs if trs else '<tr><td colspan="6"><div class="empty"><div class="e-ico">⭐</div><div class="e-txt">No reviews yet</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("⭐ Reviews","reviews",body)

# ══════════════════════════════════════════════════════════════
#  INQUIRIES
# ══════════════════════════════════════════════════════════════
@app.route("/inquiries", methods=["GET","POST"])
@login_required
def inquiries():
    conn=get_db(); msg=""
    if request.method=="POST":
        conn.execute("UPDATE service_inquiries SET replied=1 WHERE id=?",(request.form.get("iid"),))
        conn.commit(); msg="Marked as replied."
    rows=conn.execute("SELECT * FROM service_inquiries ORDER BY id DESC").fetchall()
    conn.close()
    trs=""
    for r in [dict(x) for x in rows]:
        wa=f"https://wa.me/17808518629?text=Hi+{r['display_name']}%2C+regarding+your+{r['service_name']}+inquiry..."
        trs+=f"""<tr>
          <td><div style="font-weight:600">{r['display_name']}</div><div style="color:var(--sub);font-size:.73rem">@{r['username']}</div></td>
          <td><span class="badge bv">{r['service_name']}</span></td>
          <td style="max-width:220px;white-space:normal">{r['description']}</td>
          <td style="color:var(--sub)">{r['created_at'][:16]}</td>
          <td><span class="badge {'by' if not r['replied'] else 'bg'}">{'Pending' if not r['replied'] else 'Done'}</span></td>
          <td>
            <div class="action-cell">
              <a href="{wa}" target="_blank" class="btn btn-success btn-xs">💬 WhatsApp</a>
              {'<form method="POST" style="margin:0;margin-top:4px"><input type="hidden" name="iid" value="'+str(r["id"])+'"><button class="btn btn-primary btn-xs">✅ Mark Done</button></form>' if not r['replied'] else ''}
            </div>
          </td>
        </tr>"""
    body=f"""
{flash(msg) if msg else ""}
<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">📩</span>Service Inquiries <span class="badge bb" style="margin-left:6px">{len(rows)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>User</th><th>Service</th><th>Description</th><th>Date</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>{trs if trs else '<tr><td colspan="6"><div class="empty"><div class="e-ico">📩</div><div class="e-txt">No inquiries yet</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("📩 Inquiries","inquiries",body)

# ══════════════════════════════════════════════════════════════
#  BROADCAST
# ══════════════════════════════════════════════════════════════
@app.route("/broadcast", methods=["GET","POST"])
@login_required
def broadcast():
    msg=""; ok=True
    if request.method=="POST":
        text=request.form.get("message","").strip()
        if text:
            conn=get_db(); users=conn.execute("SELECT telegram_id FROM users").fetchall(); conn.close()
            tok=os.environ.get("BOT_TOKEN",""); sent=failed=0
            for u in users:
                try:
                    payload=_json.dumps({"chat_id":u["telegram_id"],"text":f"📢 *Announcement:*\n\n{text}\n\n_Dev Clin Market | Skyline Technologies_","parse_mode":"Markdown"}).encode()
                    req=urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",data=payload,headers={"Content-Type":"application/json"})
                    urllib.request.urlopen(req,timeout=5); sent+=1
                except: failed+=1
            msg=f"Sent to {sent} users. {failed} failed." if failed else f"Successfully sent to all {sent} users!"
    body=f"""
{flash(msg,ok) if msg else ""}
<div class="card" style="max-width:640px">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">📢</span>Broadcast Message</div>
  </div>
  <div class="card-body">
    <p style="color:var(--sub);font-size:.83rem;margin-bottom:18px">
      Send a message to all registered users instantly.<br>
      Supports Telegram Markdown: <code>*bold*</code> <code>_italic_</code>
    </p>
    <form method="POST">
      <div class="fg" style="margin-bottom:16px">
        <label>Message</label>
        <textarea name="message" rows="8" placeholder="Write your announcement here..." required></textarea>
      </div>
      <button class="btn btn-primary btn-md">📢 Send to All Users</button>
    </form>
  </div>
</div>"""
    return shell("📢 Broadcast","broadcast",body)

# ══════════════════════════════════════════════════════════════
#  DOWNLOADS
# ══════════════════════════════════════════════════════════════
@app.route("/downloads")
@login_required
def downloads():
    conn=get_db()
    try:
        rows=conn.execute("SELECT ud.*,u.username,u.display_name FROM user_downloads ud LEFT JOIN users u ON ud.user_id=u.telegram_id ORDER BY ud.id DESC LIMIT 100").fetchall()
    except: rows=[]
    conn.close()
    now=datetime.now().isoformat(); trs=""
    for r in [dict(x) for x in rows]:
        exp=r.get("expires_at",""); expired=exp<now
        clicks=r.get("click_count",0)
        badge="br" if expired else ("by" if clicks<=1 else "bg")
        status="Expired" if expired else f"{clicks}/3 clicks"
        ml=""
        if not expired:
            try:
                diff=int((datetime.fromisoformat(exp)-datetime.now()).total_seconds()/60)
                ml=f'<div style="color:var(--sub);font-size:.72rem">{diff} min left</div>'
            except: pass
        trs+=f"""<tr>
          <td><div style="font-weight:600">{r.get('display_name','') or r['user_id']}</div><div style="color:var(--sub);font-size:.73rem">@{r.get('username','')}</div></td>
          <td>{r.get('product_name','')}</td>
          <td><span class="badge {badge}">{status}</span>{ml}</td>
          <td style="color:var(--sub)">{exp[:16]}</td>
          <td><a href="{r.get('file_url','')}" target="_blank" class="btn btn-ghost btn-xs">🔗 Open</a></td>
        </tr>"""
    body=f"""<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">📥</span>Download Access <span class="badge bb" style="margin-left:6px">{len(rows)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>User</th><th>Product</th><th>Status</th><th>Expires</th><th>Link</th></tr></thead>
    <tbody>{trs if trs else '<tr><td colspan="5"><div class="empty"><div class="e-ico">📥</div><div class="e-txt">No active downloads</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("📥 Downloads","downloads",body)

# ══════════════════════════════════════════════════════════════
#  MESSAGES
# ══════════════════════════════════════════════════════════════
@app.route("/messages")
@login_required
def messages():
    conn=get_db()
    rows=conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    trs="".join([f"""<tr>
      <td style="font-weight:600">{r['from_name']}</td>
      <td><span class="badge {'bb' if r['direction']=='user_to_admin' else 'bg'}">{'User → Admin' if r['direction']=='user_to_admin' else 'Admin → User'}</span></td>
      <td style="max-width:300px;white-space:normal">{r['message']}</td>
      <td style="color:var(--sub)">{r['created_at'][:16]}</td>
    </tr>""" for r in rows])
    body=f"""<div class="card">
  <div class="card-header">
    <div class="card-title"><span class="ct-icon">💬</span>Message Log <span class="badge bb" style="margin-left:6px">{len(rows)}</span></div>
  </div>
  <div class="card-body-p0"><div class="tbl-wrap"><table>
    <thead><tr><th>From</th><th>Direction</th><th>Message</th><th>Date</th></tr></thead>
    <tbody>{trs if trs else '<tr><td colspan="4"><div class="empty"><div class="e-ico">💬</div><div class="e-txt">No messages yet</div></div></td></tr>'}</tbody>
  </table></div></div>
</div>"""
    return shell("💬 Messages","messages",body)

# ══════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    msg=""
    if request.method=="POST":
        for f in ["mpesa_name","mpesa_number","group_chat_link","contact_whatsapp",
                  "instagram_link","portfolio_link","admin_telegram","bot_name",
                  "company_name","tagline","quotes_enabled","bot_banner_image",
                  "banner_shop","banner_payment","banner_services","banner_contact",
                  "banner_about","banner_group","banner_rate","banner_links","banner_account"]:
            v=request.form.get(f,"")
            if v!="": save_setting(f,v)
        msg="All settings saved!"
    s=get_settings()
    def fi(key,label,ph="",typ="text"):
        v=s.get(key,"")
        if typ=="select":
            o1="selected" if v=="1" else ""; o2="selected" if v=="0" else ""
            return f'<div class="fg"><label>{label}</label><select name="{key}"><option value="1" {o1}>✅ Enabled</option><option value="0" {o2}>❌ Disabled</option></select></div>'
        return f'<div class="fg"><label>{label}</label><input type="{typ}" name="{key}" value="{v}" placeholder="{ph}"></div>'

    def section(title,fields_html):
        return f"""<div class="card" style="margin-bottom:16px">
  <div class="card-header"><div class="card-title">{title}</div></div>
  <div class="card-body"><div class="form-grid form-row-2">{fields_html}</div></div>
</div>"""

    body=f"""
{flash(msg) if msg else ""}
<form method="POST">
<div class="two-col">
  <div>
    {section("💳 M-Pesa Payment", fi("mpesa_name","Receiver Name","Clinton Oduor")+fi("mpesa_number","Receiver Number","0743810633"))}
    {section("🤖 Bot Identity", fi("bot_name","Bot Name","Dev Clin Market")+fi("company_name","Company","Skyline Technologies")+fi("tagline","Tagline","Elevating Digital Solutions")+fi("admin_telegram","Admin Telegram","@yourusername"))}
    {section("🔗 Contact & Links", fi("contact_whatsapp","WhatsApp Number","17808518629")+fi("instagram_link","Instagram URL","https://instagram.com/...")+fi("portfolio_link","Portfolio URL","https://devclin.netlify.app")+fi("group_chat_link","Group Chat Link","https://t.me/..."))}
    {section("⏰ Auto Quotes", fi("quotes_enabled","Daily Motivational Quotes","","select"))}
  </div>
  <div>
    <div class="card">
      <div class="card-header"><div class="card-title">🖼 Section Banners</div></div>
      <div class="card-body">
        <p style="color:var(--sub);font-size:.78rem;margin-bottom:14px">Paste image URLs for each section banner in the bot.</p>
        {fi("bot_banner_image","Default Banner")}
        {fi("banner_shop","🛍 Shop")}
        {fi("banner_payment","💳 Payment")}
        {fi("banner_services","🛠 Services")}
        {fi("banner_contact","📞 Contact")}
        {fi("banner_about","ℹ️ About")}
        {fi("banner_group","💬 Group Chat")}
        {fi("banner_rate","⭐ Rate Us")}
        {fi("banner_links","🔗 Links")}
        {fi("banner_account","📊 Dashboard")}
      </div>
    </div>
  </div>
</div>
<button class="btn btn-primary btn-lg" style="margin-top:4px">💾 Save All Settings</button>
</form>"""
    return shell("⚙️ Settings","settings",body)

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

if __name__=="__main__":
    run()
