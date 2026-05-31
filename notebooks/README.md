# Adminator — Notebooks

JupyterLab connected to the same Postgres database as the backend.

## Notebooks

| File | Purpose |
| --- | --- |
| `01_exploratory_data_analysis.ipynb` | Tour of sales, expenses, production, stock |
| `02_sales_forecasting.ipynb` | Weekday-average / Holt-Winters / Prophet comparison |
| `03_inventory_optimization.ipynb` | Suggested production + raw-material risk |

## Getting started

After `docker compose up`, open <http://localhost:8888/?token=adminator-lab>
(the token comes from `.env`).

All notebooks share `db.py`, which builds a SQLAlchemy engine using
the same `POSTGRES_*` environment variables as the backend.

```python
from db import load_sales, load_sale_items, load_expenses
df = load_sales()
```

## Adding a new notebook

1. Drop it under `notebooks/`.
2. Use `from db import …` so your data loaders stay in one place.
3. If you need a new SQL query, prefer adding a helper to `db.py`.
