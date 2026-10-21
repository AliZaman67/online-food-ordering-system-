# Crave: Online Food Ordering System
FastAPI + SQLite (11 tables, 3 views, 4 triggers) + Three.js 3D front end. No build step.

## Run (easiest way)
Install Python 3.9+ from python.org (on Windows tick "Add Python to PATH"), then:

| System | Do this |
|---|---|
| Windows | double-click **run.bat** |
| Mac / Linux | run `./run.sh` in a terminal |
| Any | `python run.py` |

The launcher creates a private virtual environment, installs the packages, picks a free port, starts the server and opens your browser. The first run takes about a minute.

Manual way: `cd backend`, `pip install -r requirements.txt`, `python -m uvicorn main:app --reload`, then open http://127.0.0.1:8000.
The database is built from `database/schema.sql` + `seed.sql` on first start (delete `database/food_ordering.db` to reset).

## Demo logins
| Role | Email | Password |
|---|---|---|
| Admin | admin@crave.test | admin1234 |
| Customer | ayesha@mail.test (also bilal, sara, hamza, fatima, usman, zainab, omar, hina, daniyal) | demo1234 |

## What it does
**Customers**: sign up / log in, browse restaurants (ratings, ETA, fees), menu by category with veg markers, cart with coupons (`WELCOME10`, `FEAST20`), delivery address + kitchen note, simulated payment (Cash / Card / Wallet), live order tracker (auto-refreshes every 12 s), cancel while Pending, rate delivered orders.
**Database page** (for reviewers): live schema with PK/FK badges, row counts, trigger and view SQL, a checklist of DBMS concepts, and a query lab that runs 11 fixed queries (joins, HAVING, subquery, RANK window, views, integrity check) against the live database.
**Admin**: KPI dashboard and charts, order board with enforced status flow (Pending → Confirmed → Preparing → Out for Delivery → Delivered; cancel any time before delivery), rider assignment (offline riders blocked, a rider is required before "Out for Delivery"), menu manager (edit price, mark sold out, add items).

## Structure
    backend/main.py       API, auth (PBKDF2 + signed tokens, stdlib only), business rules
    backend/test_api.py   pytest suite (pip install -r requirements-dev.txt, then: pytest -q)
    run.py / run.bat / run.sh   one-click launcher
    database/             schema.sql, seed.sql, make_seed.py (regenerates demo data)
    sql/queries.sql       15 reporting + integrity queries
    docs/ER_Diagram.md    ER diagram (Mermaid) and design notes
    frontend/index.html   single-file UI with the 3D scene

## Security notes
Passwords are salted PBKDF2-SHA256 hashes. Prices, totals and discounts are always computed on the server. Admin routes check the role on every call. All user text is HTML-escaped in the UI. Payments are SIMULATED: no real money moves and there is no GPS tracking. Before real deployment: serve over HTTPS, set `CRAVE_SECRET`, add rate limiting, and switch to a real payment provider.
