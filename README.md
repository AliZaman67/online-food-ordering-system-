# Crave: Online Food Ordering System

FastAPI + SQLite (11 tables, 3 views, 4 triggers) + Three.js 3D front end. No build step.

## Run (easiest way)

Install Python 3.9+ from [python.org](https://www.python.org/downloads/). On Windows, tick **Add Python to PATH**.

| System | How to run |
|---|---|
| Windows | Double-click `run.bat` |
| Mac / Linux | Run `./run.sh` in terminal |
| Any | Run `python run.py` |

The launcher creates a private virtual environment, installs packages, picks a free port, starts the server, and opens your browser. First run takes about a minute.

## Demo logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@crave.test` | `admin1234` |
| Customer | `ayesha@mail.test` | `demo1234` |

## Features

- **Customers:** Sign up, log in, browse restaurants and menus, manage cart, apply coupons, simulate payments, track orders, cancel pending orders, and rate delivered orders.
- **Database page:** Live schema, PK/FK badges, row counts, trigger and view SQL, DBMS concepts checklist, and query lab.
- **Admin:** Dashboard, order management, rider assignment, and menu management.

## Project structure

- `backend/main.py` — API, authentication, business rules
- `backend/test_api.py` — pytest suite
- `database/` — schema, seed data, database generator
- `sql/queries.sql` — reporting and integrity queries
- `docs/ER_Diagram.md` — ER diagram and design notes
- `frontend/index.html` — user interface with 3D scene
- `run.py`, `run.bat`, `run.sh` — launchers

## Security notes

Passwords use salted PBKDF2-SHA256 hashes. Prices, totals, and discounts are computed server-side. Admin routes check user roles. Payments are simulated; no real money moves.

Before real deployment, use HTTPS, set `CRAVE_SECRET`, add rate limiting, and integrate a real payment provider.
