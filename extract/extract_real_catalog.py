"""
Extracts the public-safe master catalog from the live WINEZONE SQL Server
into CSVs that ship with the Render demo.

What it extracts (public per the user):
    - Department  (id, name)
    - Category    (id, name)
    - Supplier    (id, supplier_name)
    - Item        (full row except internal HQID/notes)
    - Item velocity profile: avg daily sold over the trailing 365 days,
      hour-of-day weights, and day-of-week weights. Drives the synthetic
      transaction generator without leaking any real customer or
      transaction PII.

What it DOES NOT extract:
    - Customers, transactions, tender entries, cashier names, audit logs.
      Those are generated synthetically at deploy time.

Run once on a machine that can reach 192.168.1.99 with a SQL login that has
SELECT on the WINEZONE database:

    cd render_demo/extract
    python extract_real_catalog.py

Output CSVs are written to ../data/.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pyodbc

HERE = Path(__file__).resolve().parent
OUT = (HERE / ".." / "data").resolve()
OUT.mkdir(parents=True, exist_ok=True)

SQL_SERVER = os.environ.get("SQL_SERVER", "192.168.1.99")
SQL_DATABASE = os.environ.get("SQL_DATABASE", "WINEZONE")
SQL_AUTH = os.environ.get("SQL_AUTH", "sql").lower()
SQL_USER = os.environ.get("SQL_USER", "CELR")
SQL_PASSWORD = os.environ.get("SQL_PASSWORD", "Pow1966")
SQL_DRIVER = os.environ.get("SQL_DRIVER", "SQL Server")


def conn_str() -> str:
    base = f"DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    if SQL_AUTH == "sql":
        return base + f"UID={SQL_USER};PWD={SQL_PASSWORD};"
    return base + "Trusted_Connection=yes;"


def dump(cur, sql: str, path: Path, params: tuple = ()) -> int:
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


def main() -> None:
    print(f"Connecting to {SQL_SERVER}/{SQL_DATABASE} as {SQL_USER or 'windows'}")
    cn = pyodbc.connect(conn_str(), timeout=10)
    cur = cn.cursor()

    n = dump(cur, "SELECT ID AS id, Name AS name FROM Department WITH (NOLOCK)",
             OUT / "departments.csv")
    print(f"  departments.csv: {n}")

    n = dump(cur, "SELECT ID AS id, Name AS name FROM Category WITH (NOLOCK)",
             OUT / "categories.csv")
    print(f"  categories.csv: {n}")

    n = dump(cur,
             "SELECT ID AS id, SupplierName AS supplier_name "
             "FROM Supplier WITH (NOLOCK)",
             OUT / "suppliers.csv")
    print(f"  suppliers.csv: {n}")

    # Full item master — item data is public per the user. We keep cost,
    # price, descriptions, suppliers, etc. exactly as-is.
    n = dump(cur, """
        SELECT
            i.ID                                                AS id,
            i.ItemLookupCode                                    AS item_lookup_code,
            ISNULL(i.Description, '')                           AS description,
            i.DepartmentID                                      AS department_id,
            i.CategoryID                                        AS category_id,
            i.SupplierID                                        AS supplier_id,
            ISNULL(i.BinLocation, '')                           AS bin_location,
            CAST(i.Quantity AS DECIMAL(18,3))                   AS quantity,
            CAST(ISNULL(i.QuantityCommitted, 0) AS DECIMAL(18,3)) AS quantity_committed,
            CAST(ISNULL(i.ReorderPoint, 0) AS DECIMAL(18,3))    AS reorder_point,
            CAST(ISNULL(i.RestockLevel, 0) AS DECIMAL(18,3))    AS restock_level,
            CAST(ISNULL(i.Cost, 0) AS DECIMAL(18,4))            AS cost,
            CAST(ISNULL(i.Price, 0) AS DECIMAL(18,4))           AS price,
            i.LastReceived                                       AS last_received,
            i.LastSold                                           AS last_sold,
            i.LastCounted                                        AS last_counted,
            i.LastUpdated                                        AS last_updated,
            ISNULL(i.Inactive, 0)                                AS inactive,
            ISNULL(i.Taxable, 1)                                 AS taxable,
            ISNULL(i.DateCreated, '2010-01-01')                  AS date_created
        FROM Item i WITH (NOLOCK)
    """, OUT / "items.csv")
    print(f"  items.csv: {n}")

    # Velocity profile: per item, the units sold per day over the last
    # 365 days. This is an aggregated metric, not raw transactions, so it
    # does not leak any single transaction or customer.
    n = dump(cur, """
        SELECT
            te.ItemID                                            AS item_id,
            CAST(ROUND(SUM(CASE WHEN te.Quantity > 0
                                THEN te.Quantity ELSE 0 END)*1.0/365, 4)
                 AS DECIMAL(18,4))                               AS avg_daily_units,
            CAST(ROUND(SUM(CASE WHEN te.Quantity < 0
                                THEN -te.Quantity ELSE 0 END)*1.0/365, 4)
                 AS DECIMAL(18,4))                               AS avg_daily_returns,
            CAST(AVG(NULLIF(te.Price,0)) AS DECIMAL(18,4))       AS avg_sold_price
        FROM TransactionEntry te WITH (NOLOCK)
            INNER JOIN [Transaction] t WITH (NOLOCK)
                ON te.TransactionNumber = t.TransactionNumber
        WHERE t.Time >= DATEADD(DAY, -365, GETDATE())
        GROUP BY te.ItemID
    """, OUT / "item_velocity.csv")
    print(f"  item_velocity.csv: {n}")

    # Aggregate seasonality: month-of-year multipliers across all items.
    # 12 rows; nothing customer-specific.
    n = dump(cur, """
        WITH per_month AS (
            SELECT MONTH(t.Time) AS m,
                   SUM(CASE WHEN te.Quantity > 0
                            THEN te.Quantity*te.Price ELSE 0 END) AS rev
            FROM TransactionEntry te WITH (NOLOCK)
                INNER JOIN [Transaction] t WITH (NOLOCK)
                    ON te.TransactionNumber = t.TransactionNumber
            WHERE t.Time >= DATEADD(DAY, -730, GETDATE())
            GROUP BY MONTH(t.Time)
        ),
        avg_rev AS (SELECT AVG(rev) AS a FROM per_month)
        SELECT m AS month_of_year,
               CAST(rev / NULLIF((SELECT a FROM avg_rev),0)
                    AS DECIMAL(18,4)) AS multiplier
        FROM per_month
        ORDER BY m
    """, OUT / "month_seasonality.csv")
    print(f"  month_seasonality.csv: {n}")

    # Day-of-week multipliers (Sun..Sat).
    n = dump(cur, """
        WITH per_dow AS (
            SELECT DATEPART(WEEKDAY, t.Time) AS dow,
                   SUM(CASE WHEN te.Quantity > 0
                            THEN te.Quantity*te.Price ELSE 0 END) AS rev
            FROM TransactionEntry te WITH (NOLOCK)
                INNER JOIN [Transaction] t WITH (NOLOCK)
                    ON te.TransactionNumber = t.TransactionNumber
            WHERE t.Time >= DATEADD(DAY, -365, GETDATE())
            GROUP BY DATEPART(WEEKDAY, t.Time)
        ),
        avg_rev AS (SELECT AVG(rev) AS a FROM per_dow)
        SELECT dow AS day_of_week,
               CAST(rev / NULLIF((SELECT a FROM avg_rev),0)
                    AS DECIMAL(18,4)) AS multiplier
        FROM per_dow
        ORDER BY dow
    """, OUT / "dow_seasonality.csv")
    print(f"  dow_seasonality.csv: {n}")

    # Hour-of-day distribution (0..23).
    n = dump(cur, """
        WITH per_hour AS (
            SELECT DATEPART(HOUR, t.Time) AS h,
                   SUM(CASE WHEN te.Quantity > 0
                            THEN te.Quantity*te.Price ELSE 0 END) AS rev
            FROM TransactionEntry te WITH (NOLOCK)
                INNER JOIN [Transaction] t WITH (NOLOCK)
                    ON te.TransactionNumber = t.TransactionNumber
            WHERE t.Time >= DATEADD(DAY, -180, GETDATE())
            GROUP BY DATEPART(HOUR, t.Time)
        ),
        tot AS (SELECT SUM(rev) AS t FROM per_hour)
        SELECT h AS hour_of_day,
               CAST(rev / NULLIF((SELECT t FROM tot),0)
                    AS DECIMAL(18,6)) AS share
        FROM per_hour
        ORDER BY h
    """, OUT / "hour_distribution.csv")
    print(f"  hour_distribution.csv: {n}")

    # Baseline transactions-per-day so the generator targets realistic
    # daily volume. One number.
    cur.execute("""
        SELECT CAST(AVG(CAST(daily AS FLOAT)) AS DECIMAL(18,2)) AS avg_txns_per_day
        FROM (
            SELECT CAST(t.Time AS DATE) AS d,
                   COUNT(DISTINCT t.TransactionNumber) AS daily
            FROM [Transaction] t WITH (NOLOCK)
            WHERE t.Time >= DATEADD(DAY, -365, GETDATE())
            GROUP BY CAST(t.Time AS DATE)
        ) x
    """)
    avg_daily = cur.fetchone()[0] or 750
    with (OUT / "baseline.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["avg_txns_per_day", float(avg_daily)])
    print(f"  baseline.csv: avg_txns_per_day={float(avg_daily):.0f}")

    cn.close()
    print(f"\nDone. Output in {OUT}")
    print("Commit data/*.csv to the repo, then 'git push' to deploy on Render.")


if __name__ == "__main__":
    try:
        main()
    except pyodbc.Error as e:
        print(f"SQL error: {e}", file=sys.stderr)
        sys.exit(1)
