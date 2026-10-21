"""Run:  pytest -q   (uses a throw-away database)"""
import os, tempfile
os.environ["CRAVE_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)

def tok(email, pw):
    r = c.post("/api/auth/login", json={"email": email, "password": pw}); assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}

def test_auth_and_roles():
    assert c.post("/api/auth/login", json={"email": "admin@crave.test", "password": "nope"}).status_code == 401
    cust, admin = tok("ayesha@mail.test", "demo1234"), tok("admin@crave.test", "admin1234")
    assert c.get("/api/admin/orders").status_code == 401
    assert c.get("/api/admin/orders", headers=cust).status_code == 403
    assert c.get("/api/admin/orders", headers=admin).status_code == 200
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer x.y"}).status_code == 401

def test_register_duplicate():
    b = {"name": "New Person", "email": "new@x.com", "password": "secret1"}
    assert c.post("/api/auth/register", json=b).status_code == 200
    assert c.post("/api/auth/register", json=b).status_code == 409

def test_order_flow_and_rules():
    h, a = tok("bilal@mail.test", "demo1234"), tok("admin@crave.test", "admin1234")
    body = {"restaurant_id": 1, "method": "Card", "address": "House 5, Clifton", "items": [{"item_id": 1, "quantity": 2}]}
    r = c.post("/api/orders", json={**body, "coupon_code": "WELCOME10"}, headers=h).json()
    assert r["total"] == 1300 - 130 + 150                       # server computed
    assert c.post("/api/orders", json={**body, "coupon_code": "OLD5"}, headers=h).status_code == 400   # expired
    assert c.post("/api/orders", json={**body, "items": [{"item_id": 9, "quantity": 1}]}, headers=h).status_code == 400  # wrong restaurant
    assert c.post("/api/orders", json={**body, "items": [{"item_id": 3, "quantity": 1}]}, headers=h).status_code == 400  # below minimum
    oid = r["order_id"]
    assert c.patch(f"/api/admin/orders/{oid}/status", json={"status": "Delivered"}, headers=a).status_code == 400   # skip steps
    for s in ("Confirmed", "Preparing"): assert c.patch(f"/api/admin/orders/{oid}/status", json={"status": s}, headers=a).status_code == 200
    assert c.patch(f"/api/admin/orders/{oid}/status", json={"status": "Out for Delivery"}, headers=a).status_code == 400  # no rider
    assert c.patch(f"/api/admin/orders/{oid}/rider", json={"rider_id": 4}, headers=a).status_code == 400   # offline rider
    assert c.patch(f"/api/admin/orders/{oid}/rider", json={"rider_id": 1}, headers=a).status_code == 200
    assert main.one("SELECT availability_status s FROM Delivery_Riders WHERE rider_id=1")["s"] == "Busy"   # trigger
    for s in ("Out for Delivery", "Delivered"): assert c.patch(f"/api/admin/orders/{oid}/status", json={"status": s}, headers=a).status_code == 200
    assert main.one("SELECT availability_status s FROM Delivery_Riders WHERE rider_id=1")["s"] == "Available"
    d = c.get(f"/api/orders/{oid}", headers=h).json()
    assert [x["status"] for x in d["history"]] == ["Pending", "Confirmed", "Preparing", "Out for Delivery", "Delivered"]
    assert c.get(f"/api/orders/{oid}", headers=tok("sara@mail.test", "demo1234")).status_code == 404   # not their order
    assert c.post(f"/api/orders/{oid}/review", json={"rating": 5}, headers=h).status_code == 200
    assert c.post(f"/api/orders/{oid}/review", json={"rating": 4}, headers=h).status_code == 409
    assert c.post(f"/api/orders/{oid}/cancel", headers=h).status_code == 400

def test_cancel_and_reports():
    h, a = tok("hamza@mail.test", "demo1234"), tok("admin@crave.test", "admin1234")
    oid = c.post("/api/orders", json={"restaurant_id": 3, "address": "Block 4, Karachi", "items": [{"item_id": 13, "quantity": 2}]}, headers=h).json()["order_id"]
    assert c.post(f"/api/orders/{oid}/cancel", headers=h).status_code == 200
    assert main.one("SELECT status FROM Payments WHERE order_id=?", (oid,))["status"] == "Failed"
    rp = c.get("/api/admin/reports", headers=a).json()
    assert rp["kpi"]["orders"] >= 28 and len(rp["sales"]) == 4

def test_public_catalogue():
    assert len(c.get("/api/restaurants").json()) == 4
    assert len(c.get("/api/restaurants/2/menu").json()) == 6
