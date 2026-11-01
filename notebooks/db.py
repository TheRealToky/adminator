"""Shared helpers to load Adminator data into a pandas DataFrame inside notebooks."""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine, text


def get_engine():
    """Build a SQLAlchemy engine from the same env vars the backend uses."""
    user = os.environ.get("POSTGRES_USER", "adminator")
    password = os.environ.get("POSTGRES_PASSWORD", "adminator")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "adminator")
    return create_engine(f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}")


def read_sql(query, **kwargs) -> pd.DataFrame:
    return pd.read_sql(query, get_engine(), **kwargs)


def load_sales(start_date=None, end_date=None) -> pd.DataFrame:
    query = """
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
        WHERE 1=1
    """
    params = {}
    if start_date is not None:
        query += " AND s.occurred_at >= :start_date"
        params["start_date"] = start_date
    if end_date is not None:
        query += " AND s.occurred_at <= :end_date"
        params["end_date"] = end_date
    query += " ORDER BY s.occurred_at"

    stmt = text(query) if params else query
    return read_sql(stmt, params=params if params else None, parse_dates=["occurred_at"])


def load_sale_items(start_date=None, end_date=None) -> pd.DataFrame:
    query = """
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
        WHERE 1=1
    """
    params = {}
    if start_date is not None:
        query += " AND s.occurred_at >= :start_date"
        params["start_date"] = start_date
    if end_date is not None:
        query += " AND s.occurred_at <= :end_date"
        params["end_date"] = end_date
    query += " ORDER BY s.occurred_at"

    stmt = text(query) if params else query
    return read_sql(stmt, params=params if params else None, parse_dates=["occurred_at"])


def load_expenses(start_date=None, end_date=None, source="all") -> pd.DataFrame:
    """
    Load expenses from the database into a DataFrame.

    Args:
        start_date: Optional start date/timestamp filter.
        end_date: Optional end date/timestamp filter.
        source: 'all' (default: combines finance_expense & transaction expenses),
                'expenses' (only finance_expense records), or
                'transactions' (only finance_transaction records with direction='expense').
    """
    if source == "expenses":
        base_query = """
            SELECT
                e.id,
                e.title,
                e.amount,
                e.incurred_on,
                e.payment_method,
                c.name AS category,
                e.reference,
                'expense' AS source_type
            FROM finance_expense e
            JOIN finance_expensecategory c ON c.id = e.category_id
        """
    elif source == "transactions":
        base_query = """
            SELECT
                t.id,
                t.title,
                t.amount,
                t.occurred_on AS incurred_on,
                t.payment_method,
                tc.name AS category,
                t.reference,
                'transaction' AS source_type
            FROM finance_transaction t
            JOIN finance_transactioncategory tc ON tc.id = t.category_id
            WHERE t.direction = 'expense'
        """
    else:  # 'all'
        base_query = """
            SELECT
                e.id,
                e.title,
                e.amount,
                e.incurred_on,
                e.payment_method,
                c.name AS category,
                e.reference,
                'expense' AS source_type
            FROM finance_expense e
            JOIN finance_expensecategory c ON c.id = e.category_id
            UNION ALL
            SELECT
                t.id,
                t.title,
                t.amount,
                t.occurred_on AS incurred_on,
                t.payment_method,
                tc.name AS category,
                t.reference,
                'transaction' AS source_type
            FROM finance_transaction t
            JOIN finance_transactioncategory tc ON tc.id = t.category_id
            WHERE t.direction = 'expense'
        """

    query = f"""
        SELECT *
        FROM ({base_query}) exp
        WHERE 1=1
    """
    params = {}
    if start_date is not None:
        query += " AND exp.incurred_on >= :start_date"
        params["start_date"] = start_date
    if end_date is not None:
        query += " AND exp.incurred_on <= :end_date"
        params["end_date"] = end_date
    query += " ORDER BY exp.incurred_on"

    stmt = text(query) if params else query
    return read_sql(stmt, params=params if params else None, parse_dates=["incurred_on"])


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
