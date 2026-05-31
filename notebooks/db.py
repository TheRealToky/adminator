"""Shared helpers to load Adminator data into a pandas DataFrame inside notebooks."""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine


def get_engine():
    """Build a SQLAlchemy engine from the same env vars the backend uses."""
    user = os.environ.get("POSTGRES_USER", "adminator")
    password = os.environ.get("POSTGRES_PASSWORD", "adminator")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "adminator")
    return create_engine(f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}")


def read_sql(query: str, **kwargs) -> pd.DataFrame:
    return pd.read_sql(query, get_engine(), **kwargs)


def load_sales() -> pd.DataFrame:
    df = read_sql("""
        SELECT
            s.id,
            s.receipt_number,
            s.occurred_at,
            s.channel,
            s.payment_method,
            s.subtotal,
            s.discount,
            s.total,
            s.cost_of_goods,
            (s.total - s.cost_of_goods) AS profit
        FROM sales_sale s
        ORDER BY s.occurred_at
    """, parse_dates=["occurred_at"])
    return df


def load_sale_items() -> pd.DataFrame:
    df = read_sql("""
        SELECT
            si.id,
            si.sale_id,
            s.occurred_at,
            si.product_id,
            p.name AS product_name,
            p.sku AS product_sku,
            c.name AS category,
            si.quantity,
            si.unit_price,
            si.unit_cost,
            si.line_total
        FROM sales_saleitem si
        JOIN sales_sale s          ON s.id = si.sale_id
        JOIN catalog_product p     ON p.id = si.product_id
        JOIN catalog_productcategory c ON c.id = p.category_id
        ORDER BY s.occurred_at
    """, parse_dates=["occurred_at"])
    return df


def load_expenses() -> pd.DataFrame:
    return read_sql("""
        SELECT
            e.id,
            e.title,
            e.amount,
            e.incurred_on,
            e.payment_method,
            c.name AS category
        FROM finance_expense e
        JOIN finance_expensecategory c ON c.id = e.category_id
        ORDER BY e.incurred_on
    """, parse_dates=["incurred_on"])


def load_production() -> pd.DataFrame:
    return read_sql("""
        SELECT
            pr.id,
            pr.scheduled_for,
            pr.completed_at,
            pr.status,
            pr.quantity,
            pr.cost,
            p.name AS product_name,
            p.sku AS product_sku,
            c.name AS category
        FROM production_productionrun pr
        JOIN catalog_product p ON p.id = pr.product_id
        JOIN catalog_productcategory c ON c.id = p.category_id
        ORDER BY pr.scheduled_for
    """, parse_dates=["scheduled_for", "completed_at"])


def load_stock() -> pd.DataFrame:
    return read_sql("""
        SELECT
            si.id,
            si.kind,
            si.quantity,
            COALESCE(p.name, rm.name) AS name,
            COALESCE(p.sku, rm.sku) AS sku,
            COALESCE(p.unit, rm.unit) AS unit,
            COALESCE(p.reorder_threshold, rm.reorder_threshold) AS reorder_threshold
        FROM inventory_stockitem si
        LEFT JOIN catalog_product p   ON p.id = si.product_id
        LEFT JOIN catalog_rawmaterial rm ON rm.id = si.raw_material_id
        ORDER BY name
    """)
