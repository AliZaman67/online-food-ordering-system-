"""Crave backend: FastAPI + SQLite. Auth uses only the standard library (PBKDF2 + signed tokens)."""
import base64, hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
DBDIR = os.path.join(HERE, "..", "database")
DB = os.environ.get("CRAVE_DB", os.path.join(DBDIR, "food_ordering.db"))
STATUSES = ['Pending', 'Confirmed', 'Preparing', 'Out for Delivery', 'Delivered', 'Cancelled']
NEXT = {'Pending': ['Confirmed', 'Cancelled'], 'Confirmed': ['Preparing', 'Cancelled'],
        'Preparing': ['Out for Delivery', 'Cancelled'], 'Out for Delivery': ['Delivered', 'Cancelled'],
        'Delivered': [], 'Cancelled': []}
TOKEN_TTL = 60 * 60 * 24 * 7


# ---------- database helpers ----------
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")      # must be enabled on EVERY connection
    return c

def q(sql, args=()):
    c = conn()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()

def one(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None

if not os.path.exists(DB):
    _c = conn()
    for f in ("schema.sql", "seed.sql"):
        _c.executescript(open(os.path.join(DBDIR, f), encoding="utf-8").read())
    _c.commit(); _c.close()


# ---------- auth: PBKDF2 passwords + HMAC-signed tokens ----------
def _secret():
    if os.environ.get("CRAVE_SECRET"):
        return os.environ["CRAVE_SECRET"].encode()
    path = os.path.join(os.path.dirname(DB), ".secret")
    if not os.path.exists(path):
        open(path, "w").write(secrets.token_hex(32))
    return open(path).read().strip().encode()
SECRET = _secret()

def hash_pw(pw, iters=120_000):
    salt = secrets.token_hex(8)
    return f"pbkdf2${iters}${salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), iters).hex()}"

def check_pw(pw, stored):
    try:
        _, iters, salt, h = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(got, h)
    except ValueError:
        return False

def make_token(uid, role):
    body = base64.urlsafe_b64encode(json.dumps({"uid": uid, "role": role, "exp": int(time.time()) + TOKEN_TTL}).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()

def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in")
    try:
        body, sig = authorization[7:].split(".")
        if not hmac.compare_digest(sig, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(body))
        if data["exp"] < time.time():
            raise ValueError
    except Exception:
        raise HTTPException(401, "Session expired, please log in again")
    u = one("SELECT user_id,name,email,phone,address,role FROM Users WHERE user_id=?", (data["uid"],))
    if not u:
        raise HTTPException(401, "Account no longer exists")
    return u

def admin_only(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Admin access only")
    return u


# ---------- request models ----------
class Register(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=200)
class Login(BaseModel): email: str; password: str
class Line(BaseModel): item_id: int; quantity: int = Field(gt=0, le=50)
class NewOrder(BaseModel):
    restaurant_id: int
    method: str = "Cash"
    items: List[Line] = Field(min_length=1)
    coupon_code: Optional[str] = None
    address: str = Field(min_length=5, max_length=200)
    notes: Optional[str] = Field(None, max_length=200)
class Status(BaseModel): status: str
class Rider(BaseModel): rider_id: Optional[int] = None
class ItemPatch(BaseModel):
    price: Optional[float] = Field(None, ge=0)
    is_available: Optional[int] = Field(None, ge=0, le=1)
class NewItem(BaseModel):
    restaurant_id: int; category_id: int
    name: str = Field(min_length=2, max_length=60)
    description: Optional[str] = Field(None, max_length=120)
    emoji: str = Field("🍴", max_length=8)
    price: float = Field(ge=0); is_veg: int = Field(0, ge=0, le=1)
class NewCoupon(BaseModel):
    code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    discount_percent: int = Field(ge=1, le=90); min_order: float = Field(0, ge=0)
    expires_on: Optional[str] = None
class NewReview(BaseModel): rating: int = Field(ge=1, le=5); comment: Optional[str] = Field(None, max_length=300)

app = FastAPI(title="Crave Online Food Ordering System")
# CORS: the page also works if it is opened from another origin (tokens travel in a header, not cookies)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(sqlite3.Error)
async def db_error(_, exc):
    return JSONResponse({"detail": f"Database error: {exc}"}, status_code=500)

@app.get("/api/health")
def health(): return {"ok": True, "tables": one("SELECT COUNT(*) n FROM sqlite_master WHERE type='table'")["n"]}

@app.get("/api/stats")
def stats():
    return one("""SELECT (SELECT COUNT(*) FROM Restaurants) restaurants, (SELECT COUNT(*) FROM Menu_Items) items,
                  (SELECT COUNT(*) FROM Orders) orders, (SELECT COUNT(*) FROM Users WHERE role='customer') customers""")


# ---------- auth endpoints ----------
@app.post("/api/auth/register")
def register(b: Register):
    c = conn()
    try:
        with c:
            uid = c.execute("INSERT INTO Users(name,email,phone,address,password_hash) VALUES(?,?,?,?,?)",
                            (b.name.strip(), b.email.lower(), b.phone, b.address, hash_pw(b.password))).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That email is already registered")
    finally:
        c.close()
    return {"token": make_token(uid, "customer")}

@app.post("/api/auth/login")
def login(b: Login):
    u = one("SELECT user_id,role,password_hash FROM Users WHERE email=?", (b.email.lower(),))
    if not u or not check_pw(b.password, u["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(u["user_id"], u["role"])}

@app.get("/api/auth/me")
def me(u=Depends(current_user)): return u


# ---------- public catalogue ----------
@app.get("/api/restaurants")
def restaurants():
    return q("""SELECT r.*, COALESCE(x.avg_rating,0) avg_rating, x.review_count FROM Restaurants r
                JOIN Restaurant_Ratings x ON x.restaurant_id=r.restaurant_id ORDER BY r.restaurant_id""")

@app.get("/api/restaurants/{rid}/menu")
def menu(rid: int):
    return q("""SELECT m.*, c.name category FROM Menu_Items m JOIN Categories c ON c.category_id=m.category_id
                WHERE m.restaurant_id=? ORDER BY m.category_id, m.item_id""", (rid,))

@app.get("/api/restaurants/{rid}/reviews")
def rest_reviews(rid: int):
    return q("""SELECT v.rating, v.comment, v.created_at, u.name FROM Reviews v JOIN Users u ON u.user_id=v.user_id
                WHERE v.restaurant_id=? ORDER BY v.review_id DESC LIMIT 5""", (rid,))

def coupon_discount(code, subtotal):
    """Returns (code, discount) or raises 400. Single source of truth for validation."""
    cp = one("SELECT * FROM Coupons WHERE code=? COLLATE NOCASE", (code,))
    if not cp or not cp["is_active"]: raise HTTPException(400, "Coupon not found")
    if cp["expires_on"] and cp["expires_on"] < date.today().isoformat(): raise HTTPException(400, "Coupon has expired")
    if subtotal < cp["min_order"]: raise HTTPException(400, f"Coupon needs an order of at least Rs {int(cp['min_order'])}")
    return cp["code"], round(subtotal * cp["discount_percent"] / 100)

@app.get("/api/coupons/{code}")
def check_coupon(code: str, subtotal: float = 0):
    code, disc = coupon_discount(code, subtotal)
    return {"code": code, "discount": disc}


# ---------- customer orders ----------
@app.post("/api/orders")
def create_order(b: NewOrder, u=Depends(current_user)):
    if b.method not in ("Cash", "Card", "Wallet"): raise HTTPException(400, "Invalid payment method")
    c = conn()
    try:
        with c:   # one atomic transaction: any error rolls back the order, its lines and the payment
            r = c.execute("SELECT * FROM Restaurants WHERE restaurant_id=?", (b.restaurant_id,)).fetchone()
            if not r: raise HTTPException(400, "Unknown restaurant")
            if not r["is_open"]: raise HTTPException(400, f"{r['name']} is closed right now")
            oid = c.execute("INSERT INTO Orders(user_id,restaurant_id,delivery_address,notes,delivery_fee) VALUES(?,?,?,?,?)",
                            (u["user_id"], b.restaurant_id, b.address, b.notes, r["delivery_fee"])).lastrowid
            sub = 0
            for ln in b.items:
                it = c.execute("SELECT price,is_available,name FROM Menu_Items WHERE item_id=? AND restaurant_id=?",
                               (ln.item_id, b.restaurant_id)).fetchone()
                if not it: raise HTTPException(400, f"Item {ln.item_id} does not belong to this restaurant")
                if not it["is_available"]: raise HTTPException(400, f"{it['name']} is sold out")
                sub += it["price"] * ln.quantity            # server-side price: never trust the browser
                c.execute("INSERT INTO Order_Items(order_id,item_id,quantity,unit_price) VALUES(?,?,?,?)",
                          (oid, ln.item_id, ln.quantity, it["price"]))
            if sub < r["min_order"]: raise HTTPException(400, f"Minimum order for {r['name']} is Rs {int(r['min_order'])}")
            code, disc = (coupon_discount(b.coupon_code, sub) if b.coupon_code else (None, 0))
            total = sub - disc + r["delivery_fee"]
            c.execute("UPDATE Orders SET subtotal=?,discount=?,total_amount=?,coupon_code=? WHERE order_id=?", (sub, disc, total, code, oid))
            paid = "Pending" if b.method == "Cash" else "Paid"   # payments are SIMULATED
            c.execute("INSERT INTO Payments(order_id,amount,method,status,payment_date) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
                      (oid, total, b.method, paid))
        return {"order_id": oid, "total": total}
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, str(e))
    finally:
        c.close()

ORDER_SQL = """SELECT o.order_id,o.order_date,o.status,o.subtotal,o.discount,o.delivery_fee,o.total_amount,o.rider_id,
  o.delivery_address,o.notes,o.coupon_code,u.name customer,r.name restaurant,r.emoji,r.eta_minutes,
  p.method,p.status pay_status,d.name rider,
  (SELECT group_concat(m.name||' x'||oi.quantity,', ') FROM Order_Items oi JOIN Menu_Items m ON m.item_id=oi.item_id
     WHERE oi.order_id=o.order_id) items,
  (SELECT rating FROM Reviews v WHERE v.order_id=o.order_id) rating
  FROM Orders o JOIN Users u ON u.user_id=o.user_id JOIN Restaurants r ON r.restaurant_id=o.restaurant_id
  LEFT JOIN Payments p ON p.order_id=o.order_id LEFT JOIN Delivery_Riders d ON d.rider_id=o.rider_id"""

@app.get("/api/orders/mine")
def my_orders(u=Depends(current_user)):
    return q(ORDER_SQL + " WHERE o.user_id=? ORDER BY o.order_id DESC", (u["user_id"],))

@app.get("/api/orders/{oid}")
def order_detail(oid: int, u=Depends(current_user)):
    o = one(ORDER_SQL + " WHERE o.order_id=?", (oid,))
    owner = one("SELECT user_id FROM Orders WHERE order_id=?", (oid,))
    if not o or (u["role"] != "admin" and owner["user_id"] != u["user_id"]):
        raise HTTPException(404, "Order not found")
    o["history"] = q("SELECT status,changed_at FROM Order_Status_History WHERE order_id=? ORDER BY history_id", (oid,))
    o["lines"] = q("""SELECT m.name,m.emoji,oi.quantity,oi.unit_price FROM Order_Items oi
                      JOIN Menu_Items m ON m.item_id=oi.item_id WHERE oi.order_id=?""", (oid,))
    return o

@app.post("/api/orders/{oid}/cancel")
def cancel_order(oid: int, u=Depends(current_user)):
    o = one("SELECT status FROM Orders WHERE order_id=? AND user_id=?", (oid, u["user_id"]))
    if not o: raise HTTPException(404, "Order not found")
    if o["status"] != "Pending": raise HTTPException(400, "Only orders that are still Pending can be cancelled")
    set_status_db(oid, "Cancelled")
    return {"ok": True}

@app.post("/api/orders/{oid}/review")
def review(oid: int, b: NewReview, u=Depends(current_user)):
    o = one("SELECT status,restaurant_id FROM Orders WHERE order_id=? AND user_id=?", (oid, u["user_id"]))
    if not o: raise HTTPException(404, "Order not found")
    if o["status"] != "Delivered": raise HTTPException(400, "You can review an order once it is delivered")
    c = conn()
    try:
        with c:
            c.execute("INSERT INTO Reviews(order_id,user_id,restaurant_id,rating,comment) VALUES(?,?,?,?,?)",
                      (oid, u["user_id"], o["restaurant_id"], b.rating, b.comment))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "You already reviewed this order")
    finally:
        c.close()
    return {"ok": True}


# ---------- admin ----------
def set_status_db(oid, status):
    c = conn()
    with c:
        c.execute("UPDATE Orders SET status=? WHERE order_id=?", (status, oid))
        if status == "Delivered":
            c.execute("UPDATE Payments SET status='Paid' WHERE order_id=? AND status='Pending'", (oid,))
        if status == "Cancelled":
            c.execute("UPDATE Payments SET status='Failed' WHERE order_id=? AND status='Pending'", (oid,))
    c.close()

@app.get("/api/admin/orders")
def admin_orders(status: Optional[str] = None, _=Depends(admin_only)):
    return q(ORDER_SQL + (" WHERE o.status=?" if status else "") + " ORDER BY o.order_id DESC", (status,) if status else ())

@app.patch("/api/admin/orders/{oid}/status")
def admin_status(oid: int, b: Status, _=Depends(admin_only)):
    if b.status not in STATUSES: raise HTTPException(400, "Invalid status")
    o = one("SELECT status,rider_id FROM Orders WHERE order_id=?", (oid,))
    if not o: raise HTTPException(404, "Order not found")
    if b.status not in NEXT[o["status"]]:
        raise HTTPException(400, f"An order that is {o['status']} cannot move to {b.status}")
    if b.status == "Out for Delivery" and not o["rider_id"]:
        raise HTTPException(400, "Assign a rider before sending the order out")
    set_status_db(oid, b.status)
    return {"ok": True}

@app.patch("/api/admin/orders/{oid}/rider")
def admin_rider(oid: int, b: Rider, _=Depends(admin_only)):
    c = conn()
    try:
        with c:
            if b.rider_id is not None:
                rd = c.execute("SELECT availability_status FROM Delivery_Riders WHERE rider_id=?", (b.rider_id,)).fetchone()
                if not rd: raise HTTPException(400, "Rider does not exist")
                if rd["availability_status"] == "Offline": raise HTTPException(400, "That rider is offline")
            c.execute("UPDATE Orders SET rider_id=? WHERE order_id=?", (b.rider_id, oid))
    finally:
        c.close()
    return {"ok": True}

@app.get("/api/admin/riders")
def riders(_=Depends(admin_only)): return q("SELECT * FROM Delivery_Riders")

@app.get("/api/admin/coupons")
def coupons(_=Depends(admin_only)): return q("SELECT * FROM Coupons")

@app.post("/api/admin/coupons")
def add_coupon(b: NewCoupon, _=Depends(admin_only)):
    c = conn()
    try:
        with c: c.execute("INSERT INTO Coupons VALUES(?,?,?,?,1)", (b.code.upper(), b.discount_percent, b.min_order, b.expires_on))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That coupon code already exists")
    finally:
        c.close()
    return {"ok": True}

@app.post("/api/admin/menu-items")
def add_item(b: NewItem, _=Depends(admin_only)):
    c = conn()
    try:
        with c:
            iid = c.execute("INSERT INTO Menu_Items(restaurant_id,category_id,name,description,emoji,price,is_veg) VALUES(?,?,?,?,?,?,?)",
                            (b.restaurant_id, b.category_id, b.name, b.description, b.emoji, b.price, b.is_veg)).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Unknown restaurant or category")
    finally:
        c.close()
    return {"item_id": iid}

@app.patch("/api/admin/menu-items/{iid}")
def patch_item(iid: int, b: ItemPatch, _=Depends(admin_only)):
    c = conn()
    with c:
        if b.price is not None: c.execute("UPDATE Menu_Items SET price=? WHERE item_id=?", (b.price, iid))
        if b.is_available is not None: c.execute("UPDATE Menu_Items SET is_available=? WHERE item_id=?", (b.is_available, iid))
    c.close()
    return {"ok": True}

@app.get("/api/categories")
def categories(): return q("SELECT * FROM Categories")

@app.get("/api/admin/reports")
def reports(_=Depends(admin_only)):
    return {
        "kpi": one("""SELECT COALESCE(SUM(CASE WHEN status='Delivered' THEN total_amount END),0) revenue,
                      COUNT(*) orders, SUM(status IN ('Pending','Confirmed','Preparing','Out for Delivery')) active,
                      COALESCE(ROUND(AVG(CASE WHEN status<>'Cancelled' THEN total_amount END)),0) avg_order FROM Orders"""),
        "sales": q("""SELECT r.name,COALESCE(SUM(o.total_amount),0) sales FROM Restaurants r
                      LEFT JOIN Orders o ON o.restaurant_id=r.restaurant_id AND o.status='Delivered'
                      GROUP BY r.restaurant_id ORDER BY sales DESC"""),
        "popular": q("""SELECT m.name,SUM(oi.quantity) units FROM Order_Items oi JOIN Menu_Items m ON m.item_id=oi.item_id
                        JOIN Orders o ON o.order_id=oi.order_id WHERE o.status<>'Cancelled'
                        GROUP BY m.item_id ORDER BY units DESC LIMIT 6"""),
        "riders": q("""SELECT d.name,COUNT(o.order_id) n FROM Delivery_Riders d LEFT JOIN Orders o ON o.rider_id=d.rider_id
                       GROUP BY d.rider_id ORDER BY n DESC"""),
        "by_status": q("SELECT status name,COUNT(*) n FROM Orders GROUP BY status ORDER BY n DESC"),
    }

# ---------- database showcase (read-only; only fixed, pre-written queries can run) ----------
LAB = [
 ("Join: recent orders with customer and restaurant", "INNER JOIN",
  "SELECT o.order_id, u.name AS customer, r.name AS restaurant, o.total_amount, o.status\nFROM Orders o\nJOIN Users u ON u.user_id = o.user_id\nJOIN Restaurants r ON r.restaurant_id = o.restaurant_id\nORDER BY o.order_id DESC LIMIT 10"),
 ("Group by: delivered sales per restaurant", "GROUP BY + SUM",
  "SELECT r.name, COUNT(o.order_id) AS orders, SUM(o.total_amount) AS sales\nFROM Restaurants r JOIN Orders o ON o.restaurant_id = r.restaurant_id\nWHERE o.status = 'Delivered'\nGROUP BY r.restaurant_id ORDER BY sales DESC"),
 ("Top 5 most ordered dishes", "JOIN + aggregate",
  "SELECT m.name, SUM(oi.quantity) AS units\nFROM Order_Items oi\nJOIN Menu_Items m ON m.item_id = oi.item_id\nJOIN Orders o ON o.order_id = oi.order_id\nWHERE o.status <> 'Cancelled'\nGROUP BY m.item_id ORDER BY units DESC LIMIT 5"),
 ("Repeat customers", "HAVING",
  "SELECT u.name, COUNT(*) AS orders\nFROM Users u JOIN Orders o ON o.user_id = u.user_id\nGROUP BY u.user_id HAVING COUNT(*) > 1\nORDER BY orders DESC"),
 ("Dishes nobody has ordered yet", "LEFT JOIN ... IS NULL",
  "SELECT m.name, r.name AS restaurant\nFROM Menu_Items m\nJOIN Restaurants r ON r.restaurant_id = m.restaurant_id\nLEFT JOIN Order_Items oi ON oi.item_id = m.item_id\nWHERE oi.item_id IS NULL"),
 ("Customers who spent above average", "Subquery",
  "SELECT u.name, SUM(o.total_amount) AS spent\nFROM Users u JOIN Orders o ON o.user_id = u.user_id\nWHERE o.status <> 'Cancelled'\nGROUP BY u.user_id\nHAVING SUM(o.total_amount) > (SELECT AVG(t) FROM (SELECT SUM(total_amount) t FROM Orders WHERE status <> 'Cancelled' GROUP BY user_id))\nORDER BY spent DESC"),
 ("Rank restaurants by sales", "Window function RANK()",
  "SELECT name, sales, RANK() OVER (ORDER BY sales DESC) AS position\nFROM (SELECT r.name, COALESCE(SUM(o.total_amount),0) AS sales\n      FROM Restaurants r LEFT JOIN Orders o ON o.restaurant_id = r.restaurant_id AND o.status = 'Delivered'\n      GROUP BY r.restaurant_id)"),
 ("Restaurant ratings", "VIEW: Restaurant_Ratings",
  "SELECT r.name, x.avg_rating, x.review_count\nFROM Restaurant_Ratings x JOIN Restaurants r ON r.restaurant_id = x.restaurant_id"),
 ("Revenue per day", "VIEW: Daily_Revenue", "SELECT * FROM Daily_Revenue ORDER BY day"),
 ("Latest status changes (written by a trigger)", "TRIGGER output",
  "SELECT h.history_id, h.order_id, h.status, h.changed_at\nFROM Order_Status_History h ORDER BY h.history_id DESC LIMIT 10"),
 ("Integrity check: totals that do not add up", "Data integrity (expect 0 rows)",
  "SELECT order_id, subtotal, discount, delivery_fee, total_amount\nFROM Orders WHERE total_amount <> subtotal - discount + delivery_fee"),
]

@app.get("/api/db/schema")
def db_schema():
    c = conn()
    try:
        tables = []
        for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid").fetchall():
            fks = {r["from"]: f"{r['table']}.{r['to']}" for r in c.execute(f"PRAGMA foreign_key_list({name})")}
            cols = [{"name": r["name"], "type": r["type"] or "", "pk": bool(r["pk"]), "notnull": bool(r["notnull"]), "fk": fks.get(r["name"])}
                    for r in c.execute(f"PRAGMA table_info({name})")]
            tables.append({"name": name, "rows": c.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0], "columns": cols})
        other = lambda kind: [dict(r) for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type=? AND sql IS NOT NULL ORDER BY rowid", (kind,))]
        return {"tables": tables, "views": other("view"), "triggers": other("trigger"), "indexes": other("index")}
    finally:
        c.close()

@app.get("/api/db/queries")
def db_queries(): return [{"id": i, "title": t, "concept": k, "sql": s} for i, (t, k, s) in enumerate(LAB)]

@app.get("/api/db/queries/{qid}")
def db_run(qid: int):
    if not 0 <= qid < len(LAB): raise HTTPException(404, "Unknown query")
    c = conn()
    try:
        cur = c.execute(LAB[qid][2])
        return {"columns": [d[0] for d in cur.description], "rows": [list(r) for r in cur.fetchmany(50)]}
    except sqlite3.Error as e:
        raise HTTPException(400, f"This query needs a newer SQLite ({e})")
    finally:
        c.close()

@app.get("/")
def index(): return FileResponse(os.path.join(HERE, "..", "frontend", "index.html"))
