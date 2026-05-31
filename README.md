# Adminator

A production-grade admin & finance app for a small bakery / pastry shop
(~10–15 staff). Built so a non-technical assistant can run daily operations,
while a data-science notebook is right there for deeper analysis.

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   React (Vite + TS + Tailwind)        ←─→  Django REST API + JWT       │
│   localhost:5173                           localhost:8000              │
│                  ▲                              ▲                      │
│                  │                              │                      │
│                  └──── Postgres 17 ─────────────┘                      │
│                            ▲                                           │
│                            │                                           │
│              JupyterLab (Prophet, Plotly, etc.)                        │
│              localhost:8888                                            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

## Features

### Operations
- Daily sales receipts (cash / mobile money / card / bank / credit)
- Production runs that automatically consume raw materials per recipe
- Real-time inventory with low-stock alerts and a full movement audit log
- Manual stock adjustments with reason and note

### Finance
- Expense tracking by category, supplier, payment method
- Outbound invoices with statuses (draft → sent → partially paid → paid)
- Monthly budgets per category
- Payment recording and overdue tracking

### Catalog
- Products with SKU, price, recipe (bill of materials)
- Raw materials with cost, units, preferred supplier, reorder threshold
- Suppliers
- Product & expense categories

### Dashboard
- Revenue, profit, COGS, OpEx, average ticket — with period-over-period change
- Daily revenue & profit trend
- Hour-of-day demand heatmap (busy hours)
- Top products, payment mix, expense breakdown, low-stock list, production by day

### Staff & access
- Email + password login with JWT (access + refresh, auto-rotating)
- Roles: admin / manager / accountant / cashier / staff

### Data lab
- Three Jupyter notebooks ready to run
- EDA, multi-model forecasting (weekday avg / Holt-Winters / Prophet),
  inventory & production optimization
- All connected to the same Postgres database

---

## Tech stack

| Layer | Choice |
| --- | --- |
| **Backend** | Python 3.13 · Django 5 · DRF · simple-jwt · drf-spectacular |
| **Database** | PostgreSQL 17 |
| **Frontend** | React 18 · TypeScript 5 · Vite 5 · TailwindCSS 3 · TanStack Query 5 · Recharts |
| **Lab** | JupyterLab + pandas, plotly, prophet, scikit-learn |
| **Infra** | Docker · Docker Compose |

---

## Getting started

> Requirements: **Docker Desktop** (or Docker Engine + Compose v2). Nothing else.

```bash
# 1. Copy environment defaults
cp .env.example .env

# 2. Build & start everything
docker compose up --build
```

First boot takes ~2 minutes. The backend will:
1. Run `makemigrations` & `migrate`
2. Seed the DB with 30 products, 20 raw materials, 6 staff users, and ~90 days
   of realistic sales / production / expenses (if the DB is empty).

### Open it

| Service | URL | Credentials |
| --- | --- | --- |
| Frontend | <http://localhost:5173> | `admin@adminator.local` / `admin12345` |
| API root | <http://localhost:8000/api/v1/> | JWT (see `/api/v1/auth/login/`) |
| API docs (Swagger) | <http://localhost:8000/api/docs/> | |
| API docs (Redoc) | <http://localhost:8000/api/redoc/> | |
| Django admin | <http://localhost:8000/admin/> | same admin creds |
| JupyterLab | <http://localhost:8888/?token=adminator-lab> | token from `.env` |

### Other seeded users

All non-admin demo users share the password **`demo12345`**:

| Email | Role |
| --- | --- |
| `manager@adminator.local` | Manager |
| `accountant@adminator.local` | Accountant |
| `cashier1@adminator.local` | Cashier |
| `cashier2@adminator.local` | Cashier |
| `baker@adminator.local` | Staff |

---

## Environment variables

All configuration lives in `.env` at the repo root (template: `.env.example`).
Highlights:

| Variable | Purpose | Default |
| --- | --- | --- |
| `POSTGRES_*` | DB connection | `adminator` / `adminator` |
| `DJANGO_SECRET_KEY` | **Replace in production** | insecure default |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` or `config.settings.prod` | `dev` |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Access token TTL | `60` |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Refresh token TTL | `7` |
| `BUSINESS_NAME` | Display name | `Sweet Hills Bakery` |
| `BUSINESS_CURRENCY` | ISO-4217 code (formatting is locale-aware) | `RWF` |
| `BUSINESS_CURRENCY_SYMBOL` | Fallback symbol if `Intl` lacks it | `FRw` |
| `BUSINESS_TIMEZONE` | IANA tz name (applied to Django `TIME_ZONE`) | `Africa/Kigali` |
| `BUSINESS_LOCALE` | BCP-47 tag, used by the React `Intl` formatters | `en-RW` |
| `VITE_API_BASE_URL` | Where the frontend should reach the API | `http://localhost:8000/api/v1` |
| `JUPYTER_TOKEN` | Token to access JupyterLab | `adminator-lab` |

Changing the currency is a one-line change — set `BUSINESS_CURRENCY`,
`BUSINESS_CURRENCY_SYMBOL`, and `BUSINESS_LOCALE` in `.env`, then rebuild the
frontend image (so Vite picks the new values up):

```bash
docker compose build frontend && docker compose up -d frontend
```

---

## Common operations

```bash
# Tail logs for a single service
docker compose logs -f backend

# Reset the DB and reseed
docker compose down -v
docker compose up --build

# Force-reseed without dropping the volume (DEV ONLY)
docker compose exec backend python manage.py seed --fresh

# Open a Django shell
docker compose exec backend python manage.py shell

# Run backend tests
docker compose exec backend pytest

# One-off ruff lint
docker compose exec backend ruff check .
```

---

## Project layout

```
adminator/
├── backend/                       Django REST API
│   ├── apps/
│   │   ├── core/                 base models, permissions, seed command
│   │   ├── accounts/             User + JWT auth
│   │   ├── catalog/              products, raw materials, recipes, suppliers
│   │   ├── inventory/            stock items + movement ledger
│   │   ├── production/           production runs
│   │   ├── sales/                receipts + line items
│   │   ├── finance/              expenses, invoices, budgets
│   │   └── analytics/            dashboard aggregations & forecasting
│   ├── config/                   Django settings (base / dev / prod)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                      React SPA
│   ├── src/
│   │   ├── api/                  axios client + endpoint definitions
│   │   ├── components/           layout shell, DataTable, Modal, ...
│   │   ├── hooks/                useCrudList
│   │   ├── pages/                Dashboard, Sales, Inventory, ...
│   │   └── store/                AuthContext
│   ├── package.json
│   └── Dockerfile
├── notebooks/                     Jupyter notebooks
│   ├── db.py                     shared SQLAlchemy loader
│   ├── 01_exploratory_data_analysis.ipynb
│   ├── 02_sales_forecasting.ipynb
│   └── 03_inventory_optimization.ipynb
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Architecture notes

### Clean separation of concerns

- **Models** describe data + invariants only (DB constraints, default values).
- **Services** (`apps/*/services.py`) hold all multi-step business logic
  (creating a sale, executing production, adjusting stock). They are the only
  code allowed to mutate stock — everything else calls into them. They run
  inside `transaction.atomic` and use `select_for_update` for row locks.
- **Serializers** validate input and shape output. Thin.
- **Views** wire HTTP → services → serializers. They never compute.

### Atomicity & correctness

Two write paths matter:

1. **Sale creation** decrements stock per line item. The whole thing is
   transactional — if any decrement would push stock below zero (and the
   `allow_negative` flag is off), the whole sale rolls back.
2. **Production execution** consumes raw materials per recipe and then
   increments finished product stock. Same atomic guarantee.

Each `StockItem` is row-locked (`select_for_update`) while computing the new
balance, so concurrent sales/production runs can't race.

### Audit trail

Every stock change writes a `StockMovement` row with reason, signed delta,
balance after, and (when known) the acting user. The Inventory page exposes the
full movement log.

### API conventions

- Endpoints live under `/api/v1/<app>/`.
- Lists are paginated (`?page=1&page_size=25`, max 200).
- Most lists also support `?search=`, `?ordering=`, and resource-specific
  filters (e.g. `?status=overdue` on invoices).
- Auth: `Authorization: Bearer <access>`; refresh via `POST /auth/refresh/`.
- Errors come back as `{"detail": "..."}` (HTTP 4xx) — the frontend's
  `extractErrorMessage` flattens these.

---

## Production deployment

This repo runs in dev mode out of the box. Before shipping:

1. **Secrets** — generate a real `DJANGO_SECRET_KEY`, change Postgres
   credentials, rotate the JWT secret (it derives from `SECRET_KEY`).
2. **Settings module** — set `DJANGO_SETTINGS_MODULE=config.settings.prod`.
3. **Static files** — `python manage.py collectstatic`. Whitenoise is already
   wired.
4. **App server** — switch from `runserver` to `gunicorn config.wsgi`. It's
   already in `pyproject.toml`.
5. **TLS** — terminate HTTPS at a reverse proxy (Nginx, Caddy, Traefik). The
   prod settings enable HSTS and `SECURE_PROXY_SSL_HEADER`.
6. **Jupyter** — disable the lab service for production unless you intend
   analysts to share the box; protect it with a strong token / VPN.
7. **DB backups** — `pg_dump` on a schedule; for serious use, point Postgres
   at a managed service.
