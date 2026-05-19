"""
Postgres dialect port of the WINEZONE procurement intelligence tool set.

Mirrors the analytical logic from `mcp-procurement/server.py` and
`mcp-procurement/intel.py` (originally written against MSSQL on the live
RMS database). Each function takes parameters identical to the original
MCP tool and returns the same shape (list[dict] or dict) so consumers
that worked against the original tools work here unchanged.

Key dialect translations applied throughout:
    TOP (n)                  -> LIMIT n at end of query
    ? placeholders           -> $1, $2, ... (asyncpg)
    DATEADD(DAY, -n, GETDATE) -> NOW() - make_interval(days := n)
    DATEDIFF(DAY, a, b)      -> (b::date - a::date)
    DATEPART(WEEKDAY, t)     -> EXTRACT(DOW FROM t) + 1   (to match MSSQL)
    DATENAME(WEEKDAY, t)     -> TRIM(to_char(t, 'Day'))
    DATEPART(HOUR, t)        -> EXTRACT(HOUR FROM t)
    DATEFROMPARTS(y, m, 1)   -> date_trunc('month', t)::date
    CAST(t AS DATE)          -> t::date
    ISNULL(x, y)              -> COALESCE(x, y)
    OUTER APPLY              -> LEFT JOIN LATERAL ... ON true
    [Transaction]            -> "transaction"
    a + b   (string concat)  -> a || b
    NOLOCK hints             -> dropped (Postgres is MVCC)
"""
from __future__ import annotations

from typing import Any

from .db import fetch, fetchrow


# --------------------------------------------------------------------------- #
# Health / smoke test
# --------------------------------------------------------------------------- #

async def ping() -> dict:
    row = await fetchrow(
        "SELECT current_database() AS db, "
        "       version()          AS server, "
        "       NOW()              AS now"
    )
    return {"ok": True, "connection": row}


# --------------------------------------------------------------------------- #
# Core procurement / inventory tools
# --------------------------------------------------------------------------- #

async def reorder_recommendations(lookback_days: int = 365,
                                  horizon_days: int = 7,
                                  only_active: bool = True,
                                  limit: int = 200) -> list[dict]:
    sql = """
    WITH sales AS (
        SELECT te.item_id,
               SUM(te.quantity)                     AS total_qty,
               MAX(te.transaction_time)             AS last_sale
        FROM transaction_entry te
        WHERE te.transaction_time >= NOW() - make_interval(days => $1)
          AND te.quantity > 0
        GROUP BY te.item_id
    )
    SELECT
        d.name                                                   AS "Department",
        c.name                                                   AS "Category",
        s.supplier_name                                          AS "Supplier",
        i.item_lookup_code                                       AS "ItemCode",
        i.description                                            AS "Description",
        i.bin_location                                           AS "BinLocation",
        i.quantity                                               AS "QtyOnHand",
        i.quantity_committed                                     AS "QtyCommitted",
        (i.quantity - i.quantity_committed)                      AS "QtyAvailable",
        i.reorder_point                                          AS "ReorderPoint",
        i.restock_level                                          AS "RestockLevel",
        COALESCE(sa.total_qty, 0)                                AS "TotalQtySold",
        ROUND(COALESCE(sa.total_qty,0)::numeric / $1, 2)         AS "AvgDailySales",
        ROUND(COALESCE(sa.total_qty,0)::numeric / $1 * $2, 0)    AS "HorizonSupplyNeed",
        CASE WHEN COALESCE(sa.total_qty,0) > 0
             THEN ROUND((i.quantity - i.quantity_committed)
                        / (sa.total_qty::numeric / $1), 1)
             ELSE 999 END                                        AS "DaysOfStock",
        CEIL(
          ROUND(COALESCE(sa.total_qty,0)::numeric / $1 * $2, 0)
          - (i.quantity - i.quantity_committed)
        )                                                        AS "SuggestedReorderQty",
        CASE
            WHEN (i.quantity - i.quantity_committed) <= 0
                THEN 'OUT OF STOCK'
            WHEN (i.quantity - i.quantity_committed) <= i.reorder_point
                THEN 'REORDER NOW'
            ELSE 'LOW STOCK' END                                 AS "ReorderStatus",
        i.cost                                                   AS "UnitCost",
        i.price                                                  AS "UnitPrice",
        sa.last_sale                                             AS "LastSaleDate"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
        LEFT JOIN sales      sa ON i.id = sa.item_id
    WHERE ($3 = false OR i.inactive = 0)
      AND ROUND(COALESCE(sa.total_qty,0)::numeric / $1 * $2, 0) > 0
      AND (i.quantity - i.quantity_committed)
          < ROUND(COALESCE(sa.total_qty,0)::numeric / $1 * $2, 0)
    ORDER BY ROUND(COALESCE(sa.total_qty,0)::numeric / $1 * $2, 0) DESC
    LIMIT $4
    """
    return await fetch(sql, lookback_days, horizon_days, only_active, limit)


async def dead_stock(no_sales_days: int = 180,
                     min_inventory_value: float = 0.0,
                     limit: int = 200) -> list[dict]:
    sql = """
    SELECT
        d.name AS "Department", c.name AS "Category",
        s.supplier_name AS "Supplier",
        i.item_lookup_code AS "ItemCode", i.description AS "Description",
        i.quantity AS "QtyOnHand", i.cost AS "UnitCost",
        (i.cost * i.quantity) AS "InventoryValue",
        last_sale.last_sale AS "LastSaleDate",
        (CURRENT_DATE - COALESCE(last_sale.last_sale::date,
                                  DATE '1900-01-01'))::int
          AS "DaysSinceLastSale"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
        LEFT JOIN LATERAL (
            SELECT MAX(te.transaction_time) AS last_sale
            FROM transaction_entry te
            WHERE te.item_id = i.id AND te.quantity > 0
        ) last_sale ON TRUE
    WHERE i.inactive = 0
      AND i.quantity > 0
      AND (i.cost * i.quantity) >= $1
      AND (last_sale.last_sale IS NULL
           OR last_sale.last_sale < NOW() - make_interval(days => $2))
    ORDER BY (i.cost * i.quantity) DESC
    LIMIT $3
    """
    return await fetch(sql, min_inventory_value, no_sales_days, limit)


async def supplier_spend(lookback_days: int = 365, top: int = 25) -> list[dict]:
    sql = """
    SELECT
        s.supplier_name AS "Supplier",
        COUNT(DISTINCT i.id)                  AS "ActiveSkus",
        SUM(te.quantity)                      AS "UnitsSold",
        SUM(te.quantity * te.cost)            AS "Cogs",
        SUM(te.quantity * te.price)           AS "Revenue",
        SUM(te.quantity * (te.price-te.cost)) AS "GrossProfit",
        CASE WHEN SUM(te.quantity * te.price) > 0
             THEN SUM(te.quantity*(te.price-te.cost))*100.0
                  / SUM(te.quantity * te.price)
             ELSE 0 END                       AS "GrossMarginPct"
    FROM transaction_entry te
        JOIN item     i ON te.item_id     = i.id
        LEFT JOIN supplier s ON i.supplier_id = s.id
    WHERE te.transaction_time >= NOW() - make_interval(days => $1)
      AND te.quantity > 0
    GROUP BY s.supplier_name
    ORDER BY "Cogs" DESC
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def category_performance(lookback_days: int = 365,
                               top: int = 50) -> list[dict]:
    sql = """
    SELECT
        d.name AS "Department", c.name AS "Category",
        COUNT(DISTINCT i.id)                       AS "Skus",
        SUM(te.quantity)                           AS "UnitsSold",
        SUM(te.quantity * te.price)                AS "Revenue",
        SUM(te.quantity * te.cost)                 AS "Cogs",
        SUM(te.quantity * (te.price - te.cost))    AS "GrossProfit",
        CASE WHEN SUM(te.quantity * te.price) > 0
             THEN SUM(te.quantity*(te.price-te.cost))*100.0
                  / SUM(te.quantity * te.price)
             ELSE 0 END                            AS "GrossMarginPct"
    FROM transaction_entry te
        JOIN item       i ON te.item_id       = i.id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
    WHERE te.transaction_time >= NOW() - make_interval(days => $1)
      AND te.quantity > 0
    GROUP BY d.name, c.name
    ORDER BY "Revenue" DESC NULLS LAST
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def fast_movers(lookback_days: int = 30, top: int = 25) -> list[dict]:
    sql = """
    SELECT
        i.item_lookup_code AS "ItemCode", i.description AS "Description",
        d.name AS "Department", c.name AS "Category",
        s.supplier_name AS "Supplier",
        SUM(te.quantity)                              AS "UnitsSold",
        SUM(te.quantity * te.price)                   AS "Revenue",
        i.quantity                                    AS "QtyOnHand",
        ROUND(SUM(te.quantity)::numeric / $1, 2)      AS "AvgDailySales",
        CASE WHEN SUM(te.quantity) > 0
             THEN ROUND(i.quantity / (SUM(te.quantity)::numeric / $1), 1)
             ELSE 999 END                             AS "DaysOfStock"
    FROM transaction_entry te
        JOIN item       i ON te.item_id       = i.id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE te.transaction_time >= NOW() - make_interval(days => $1)
      AND te.quantity > 0
    GROUP BY i.item_lookup_code, i.description, d.name, c.name,
             s.supplier_name, i.quantity
    ORDER BY "UnitsSold" DESC
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def overstock(min_days_of_stock: int = 120,
                    top: int = 100) -> list[dict]:
    sql = """
    WITH sales AS (
        SELECT te.item_id, SUM(te.quantity) AS qty
        FROM transaction_entry te
        WHERE te.transaction_time >= NOW() - make_interval(days => 365)
          AND te.quantity > 0
        GROUP BY te.item_id
    )
    SELECT
        d.name AS "Department", c.name AS "Category",
        s.supplier_name AS "Supplier",
        i.item_lookup_code AS "ItemCode", i.description AS "Description",
        i.quantity AS "QtyOnHand", i.cost AS "UnitCost",
        (i.cost * i.quantity)                         AS "InventoryValue",
        COALESCE(sa.qty,0)                            AS "UnitsSold1Yr",
        ROUND(COALESCE(sa.qty,0)::numeric / 365, 2)   AS "AvgDailySales",
        CASE WHEN COALESCE(sa.qty,0) > 0
             THEN ROUND(i.quantity / (sa.qty::numeric / 365), 0)
             ELSE 9999 END                            AS "DaysOfStock"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
        LEFT JOIN sales      sa ON i.id = sa.item_id
    WHERE i.inactive = 0 AND i.quantity > 0
      AND (COALESCE(sa.qty,0) = 0
           OR i.quantity / (sa.qty::numeric / 365) >= $1)
    ORDER BY (i.cost * i.quantity) DESC
    LIMIT $2
    """
    return await fetch(sql, min_days_of_stock, top)


async def stockouts() -> list[dict]:
    sql = """
    SELECT
        d.name AS "Department", c.name AS "Category",
        s.supplier_name AS "Supplier",
        i.item_lookup_code AS "ItemCode", i.description AS "Description",
        i.quantity AS "QtyOnHand", i.quantity_committed AS "QtyCommitted",
        (i.quantity - i.quantity_committed) AS "QtyAvailable",
        i.reorder_point AS "ReorderPoint",
        i.restock_level AS "RestockLevel", i.cost AS "UnitCost"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.inactive = 0
      AND (i.quantity - i.quantity_committed) <= 0
    ORDER BY s.supplier_name, i.item_lookup_code
    LIMIT 1000
    """
    return await fetch(sql)


async def inventory_valuation(group_by: str = "department") -> list[dict]:
    gmap = {
        "total":      ("'ALL'", ""),
        "department": ("d.name", "GROUP BY d.name"),
        "category":   ("COALESCE(d.name,'(none)') || ' / ' || COALESCE(c.name,'(none)')",
                       "GROUP BY d.name, c.name"),
        "supplier":   ("s.supplier_name", "GROUP BY s.supplier_name"),
    }
    if group_by not in gmap:
        raise ValueError(f"group_by must be one of {list(gmap)}")
    sel, grp = gmap[group_by]
    sql = f"""
    SELECT
        {sel}                              AS "Bucket",
        COUNT(*)                           AS "Skus",
        SUM(i.quantity)                    AS "Units",
        SUM(i.cost  * i.quantity)          AS "CostValue",
        SUM(i.price * i.quantity)          AS "RetailValue",
        SUM((i.price - i.cost) * i.quantity) AS "PotentialMargin"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.inactive = 0 AND i.quantity > 0
    {grp}
    ORDER BY "CostValue" DESC NULLS LAST
    """
    return await fetch(sql)


async def item_lookup(query: str, limit: int = 25) -> list[dict]:
    like = f"%{query}%"
    sql = """
    SELECT
        i.item_lookup_code AS "ItemCode", i.description AS "Description",
        d.name AS "Department", c.name AS "Category",
        s.supplier_name AS "Supplier",
        i.quantity AS "QtyOnHand", i.quantity_committed AS "QtyCommitted",
        (i.quantity - i.quantity_committed) AS "QtyAvailable",
        i.reorder_point AS "ReorderPoint", i.restock_level AS "RestockLevel",
        i.cost AS "Cost", i.price AS "Price",
        i.bin_location AS "BinLocation", i.inactive AS "Inactive"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.item_lookup_code ILIKE $1 OR i.description ILIKE $1
    ORDER BY i.inactive, i.item_lookup_code
    LIMIT $2
    """
    return await fetch(sql, like, limit)


# --------------------------------------------------------------------------- #
# Sales trend / sales between
# --------------------------------------------------------------------------- #

_BUCKET = {
    "day":   "transaction_time::date",
    "week":  "date_trunc('week', transaction_time)::date",
    "month": "date_trunc('month', transaction_time)::date",
}


async def sales_trend(lookback_days: int = 90,
                      granularity: str = "day") -> list[dict]:
    if granularity not in _BUCKET:
        raise ValueError("granularity must be day, week, or month")
    bucket = _BUCKET[granularity]
    sql = f"""
    SELECT
        {bucket}                                                AS "Bucket",
        COUNT(DISTINCT transaction_number)                      AS "Transactions",
        SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END)    AS "UnitsSold",
        SUM(CASE WHEN quantity < 0 THEN -quantity ELSE 0 END)   AS "UnitsReturned",
        SUM(quantity * price)                                   AS "NetRevenue",
        SUM(CASE WHEN quantity > 0
                 THEN quantity*price ELSE 0 END)                AS "GrossRevenue",
        SUM(CASE WHEN quantity < 0
                 THEN quantity*price ELSE 0 END)                AS "Returns",
        CASE WHEN COUNT(DISTINCT transaction_number) > 0
             THEN SUM(quantity * price)::numeric
                  / COUNT(DISTINCT transaction_number)
             ELSE 0 END                                         AS "AvgBasket"
    FROM transaction_entry
    WHERE transaction_time >= NOW() - make_interval(days => $1)
    GROUP BY {bucket}
    ORDER BY "Bucket"
    """
    return await fetch(sql, lookback_days)


async def sales_between(start_date: str, end_date: str,
                        group_by: str = "day") -> dict:
    from datetime import date as _d
    try:
        _d.fromisoformat(start_date)
        _d.fromisoformat(end_date)
    except ValueError as e:
        raise ValueError(f"dates must be YYYY-MM-DD: {e}")

    where = ("transaction_time >= $1::date "
             "AND transaction_time < ($2::date + INTERVAL '1 day')")

    totals = await fetchrow(f"""
        SELECT
            COUNT(DISTINCT transaction_number)                       AS "Transactions",
            SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END)     AS "UnitsSold",
            SUM(CASE WHEN quantity < 0 THEN -quantity ELSE 0 END)    AS "UnitsReturned",
            SUM(CASE WHEN quantity > 0
                     THEN quantity*price ELSE 0 END)                 AS "GrossRevenue",
            SUM(CASE WHEN quantity < 0
                     THEN quantity*price ELSE 0 END)                 AS "Returns",
            SUM(quantity * price)                                    AS "NetRevenue",
            SUM(quantity * cost)                                     AS "Cogs",
            SUM(quantity * (price - cost))                           AS "GrossProfit"
        FROM transaction_entry
        WHERE {where}
    """, start_date, end_date)

    recon = await fetchrow(f"""
        SELECT
            SUM(total)            AS "HeaderTotal",
            SUM(sales_tax)        AS "HeaderTax",
            SUM(total - sales_tax) AS "HeaderNetSales"
        FROM "transaction"
        WHERE time >= $1::date AND time < ($2::date + INTERVAL '1 day')
    """, start_date, end_date)

    result: dict[str, Any] = {
        "range": {"start": start_date, "end": end_date},
        "totals": totals or {},
        "rms_header_reconciliation": recon or {},
    }

    if group_by != "none":
        if group_by not in _BUCKET:
            raise ValueError("group_by must be day, week, month, or none")
        bucket = _BUCKET[group_by]
        result["buckets"] = await fetch(f"""
            SELECT
                {bucket}                                          AS "Bucket",
                COUNT(DISTINCT transaction_number)                AS "Transactions",
                SUM(CASE WHEN quantity > 0
                         THEN quantity*price ELSE 0 END)          AS "GrossRevenue",
                SUM(CASE WHEN quantity < 0
                         THEN quantity*price ELSE 0 END)          AS "Returns",
                SUM(quantity * price)                             AS "NetRevenue",
                SUM(quantity * (price - cost))                    AS "GrossProfit"
            FROM transaction_entry
            WHERE {where}
            GROUP BY {bucket}
            ORDER BY "Bucket"
        """, start_date, end_date)

    return result


# --------------------------------------------------------------------------- #
# Customer intelligence
# --------------------------------------------------------------------------- #

async def customer_360(query: str) -> dict:
    like = f"%{query}%"
    prof = await fetch("""
        SELECT
            id AS "ID", account_number AS "AccountNumber",
            first_name AS "FirstName", last_name AS "LastName",
            company AS "Company",
            email_address AS "EmailAddress", phone_number AS "PhoneNumber",
            address AS "Address", city AS "City", state AS "State",
            zip AS "Zip", account_opened AS "AccountOpened",
            last_visit AS "LastVisit", total_visits AS "TotalVisits",
            total_sales AS "TotalSales", total_savings AS "TotalSavings",
            account_balance AS "AccountBalance",
            credit_limit AS "CreditLimit",
            current_discount AS "CurrentDiscount",
            price_level AS "PriceLevel", tax_exempt AS "TaxExempt",
            notes AS "Notes"
        FROM customer
        WHERE first_name ILIKE $1 OR last_name ILIKE $1
           OR company ILIKE $1 OR account_number ILIKE $1
           OR id::text = $2
        ORDER BY total_sales DESC NULLS LAST
        LIMIT 1
    """, like, query)
    if not prof:
        return {"error": f"no customer matched '{query}'"}
    c = prof[0]
    cid = int(c["ID"])

    rfm = await fetchrow("""
        SELECT
            COUNT(DISTINCT t.transaction_number)              AS "Visits",
            SUM(te.quantity * te.price)                       AS "Net",
            SUM(te.quantity * (te.price - te.cost))           AS "GrossProfit",
            MAX(t.time)                                       AS "LastVisit",
            MIN(t.time)                                       AS "FirstVisit",
            (CURRENT_DATE - MAX(t.time)::date)::int           AS "DaysSinceLastVisit",
            CASE WHEN COUNT(DISTINCT t.transaction_number) > 0
                 THEN SUM(te.quantity * te.price)::numeric
                      / COUNT(DISTINCT t.transaction_number)
                 ELSE 0 END                                   AS "AvgBasket"
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
        WHERE t.customer_id = $1
    """, cid)

    recent = await fetch("""
        SELECT
            t.transaction_number AS "TransactionNumber", t.time AS "Time",
            SUM(te.quantity * te.price) AS "Amount",
            COUNT(te.id) AS "Lines"
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
        WHERE t.customer_id = $1
        GROUP BY t.transaction_number, t.time
        ORDER BY t.time DESC
        LIMIT 10
    """, cid)

    top_items = await fetch("""
        SELECT
            i.item_lookup_code AS "ItemLookupCode",
            i.description AS "Description",
            SUM(te.quantity)              AS "Units",
            SUM(te.quantity * te.price)   AS "Spend"
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
            JOIN item i ON te.item_id = i.id
        WHERE t.customer_id = $1
        GROUP BY i.item_lookup_code, i.description
        ORDER BY "Spend" DESC NULLS LAST
        LIMIT 10
    """, cid)

    dept_mix = await fetch("""
        SELECT
            d.name AS "Department",
            SUM(te.quantity * te.price) AS "Spend",
            SUM(te.quantity)            AS "Units"
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
            JOIN item i ON te.item_id = i.id
            LEFT JOIN department d ON i.department_id = d.id
        WHERE t.customer_id = $1
        GROUP BY d.name
        ORDER BY "Spend" DESC NULLS LAST
    """, cid)

    return {
        "profile": c,
        "rfm": rfm or {},
        "recent_transactions": recent,
        "top_items": top_items,
        "department_mix": dept_mix,
    }


async def customer_rfm() -> list[dict]:
    sql = """
    WITH base AS (
        SELECT
            c.id, c.first_name, c.last_name, c.company,
            (CURRENT_DATE - MAX(t.time)::date)::int      AS recency,
            COUNT(DISTINCT t.transaction_number)         AS frequency,
            SUM(te.quantity * te.price)                  AS monetary,
            MAX(t.time)                                  AS last_visit
        FROM customer c
            JOIN "transaction" t ON t.customer_id = c.id
            JOIN transaction_entry te ON te.transaction_number = t.transaction_number
        GROUP BY c.id, c.first_name, c.last_name, c.company
    ),
    scored AS (
        SELECT *,
            NTILE(5) OVER (ORDER BY recency DESC) AS r,
            NTILE(5) OVER (ORDER BY frequency)    AS f,
            NTILE(5) OVER (ORDER BY monetary)     AS m
        FROM base
    )
    SELECT
        id AS "ID", first_name AS "FirstName", last_name AS "LastName",
        company AS "Company",
        recency AS "DaysSinceLastVisit", frequency AS "Visits",
        monetary AS "LifetimeNet", last_visit AS "LastVisit",
        r AS "R", f AS "F", m AS "M",
        CASE
            WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
            WHEN r >= 4 AND f >= 3            THEN 'Loyal'
            WHEN r >= 4 AND f <= 2            THEN 'New / Promising'
            WHEN r <= 2 AND f >= 4 AND m >= 4 THEN 'At Risk (high value)'
            WHEN r <= 2 AND f >= 3            THEN 'At Risk'
            WHEN r <= 2 AND f <= 2            THEN 'Hibernating'
            ELSE 'Steady'
        END AS "Segment"
    FROM scored
    ORDER BY monetary DESC NULLS LAST
    LIMIT 2000
    """
    return await fetch(sql)


async def top_customers(by: str = "spend", top: int = 25,
                        lookback_days: int = 365) -> list[dict]:
    order = {
        "spend":      '"Net" DESC',
        "visits":     '"Visits" DESC',
        "margin":     '"GrossProfit" DESC',
        "avg_basket": '"AvgBasket" DESC',
    }
    if by not in order:
        raise ValueError(f"`by` must be one of {list(order)}")
    sql = f"""
    SELECT
        c.id AS "ID", c.first_name AS "FirstName", c.last_name AS "LastName",
        c.company AS "Company",
        COUNT(DISTINCT t.transaction_number)            AS "Visits",
        SUM(te.quantity)                                AS "Units",
        SUM(te.quantity * te.price)                     AS "Net",
        SUM(te.quantity * te.cost)                      AS "Cogs",
        SUM(te.quantity * (te.price - te.cost))         AS "GrossProfit",
        CASE WHEN COUNT(DISTINCT t.transaction_number) > 0
             THEN SUM(te.quantity * te.price)::numeric
                  / COUNT(DISTINCT t.transaction_number)
             ELSE 0 END                                 AS "AvgBasket",
        MAX(t.time)                                     AS "LastVisit"
    FROM customer c
        JOIN "transaction" t ON t.customer_id = c.id
        JOIN transaction_entry te
            ON te.transaction_number = t.transaction_number
    WHERE t.time >= NOW() - make_interval(days => $1)
    GROUP BY c.id, c.first_name, c.last_name, c.company
    ORDER BY {order[by]}
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def customer_churn_risk(min_lifetime_spend: float = 5000.0,
                              no_purchase_days: int = 90) -> list[dict]:
    sql = """
    SELECT
        c.id AS "ID", c.first_name AS "FirstName", c.last_name AS "LastName",
        c.company AS "Company", c.phone_number AS "PhoneNumber",
        c.email_address AS "EmailAddress",
        c.total_sales AS "LifetimeSales",
        c.total_visits AS "LifetimeVisits",
        c.last_visit AS "LastVisit",
        (CURRENT_DATE - c.last_visit::date)::int AS "DaysSinceLastVisit"
    FROM customer c
    WHERE c.total_sales >= $1
      AND (c.last_visit IS NULL
           OR c.last_visit < NOW() - make_interval(days => $2))
      AND c.employee = 0
    ORDER BY c.total_sales DESC NULLS LAST
    LIMIT 500
    """
    return await fetch(sql, min_lifetime_spend, no_purchase_days)


async def customer_purchase_history(customer_id: int,
                                    lookback_days: int = 365) -> list[dict]:
    sql = """
    SELECT
        t.transaction_number AS "TransactionNumber", t.time AS "Time",
        COUNT(te.id)                              AS "Lines",
        SUM(te.quantity)                          AS "Units",
        SUM(te.quantity * te.price)               AS "Net",
        SUM(te.quantity * (te.price - te.cost))   AS "GrossProfit",
        t.total                                   AS "HeaderTotal"
    FROM "transaction" t
        JOIN transaction_entry te
            ON t.transaction_number = te.transaction_number
    WHERE t.customer_id = $1
      AND t.time >= NOW() - make_interval(days => $2)
    GROUP BY t.transaction_number, t.time, t.total
    ORDER BY t.time DESC
    LIMIT 500
    """
    return await fetch(sql, customer_id, lookback_days)


# --------------------------------------------------------------------------- #
# Cashier intelligence
# --------------------------------------------------------------------------- #

async def cashier_scorecard(lookback_days: int = 30) -> list[dict]:
    sql = """
    SELECT
        ca.id AS "CashierID", ca.name AS "Cashier", ca.inactive AS "Inactive",
        COUNT(DISTINCT t.transaction_number)                          AS "Transactions",
        SUM(CASE WHEN te.quantity > 0 THEN te.quantity ELSE 0 END)    AS "UnitsSold",
        SUM(CASE WHEN te.quantity < 0 THEN -te.quantity ELSE 0 END)   AS "UnitsReturned",
        SUM(CASE WHEN te.quantity > 0
                 THEN te.quantity*te.price ELSE 0 END)                AS "GrossRevenue",
        SUM(CASE WHEN te.quantity < 0
                 THEN -te.quantity*te.price ELSE 0 END)               AS "ReturnValue",
        SUM(te.quantity * te.price)                                   AS "NetRevenue",
        SUM(te.quantity * (te.price - te.cost))                       AS "GrossProfit",
        CASE WHEN COUNT(DISTINCT t.transaction_number) > 0
             THEN SUM(te.quantity * te.price)::numeric
                  / COUNT(DISTINCT t.transaction_number)
             ELSE 0 END                                               AS "AvgBasket",
        CASE WHEN SUM(CASE WHEN te.quantity > 0
                           THEN te.quantity*te.price ELSE 0 END) > 0
             THEN SUM(CASE WHEN te.quantity < 0
                           THEN -te.quantity*te.price ELSE 0 END)*100.0
                  / SUM(CASE WHEN te.quantity > 0
                             THEN te.quantity*te.price ELSE 0 END)
             ELSE 0 END                                               AS "ReturnRatePct"
    FROM "transaction" t
        JOIN transaction_entry te
            ON t.transaction_number = te.transaction_number
        JOIN cashier ca ON t.cashier_id = ca.id
    WHERE t.time >= NOW() - make_interval(days => $1)
    GROUP BY ca.id, ca.name, ca.inactive
    ORDER BY "NetRevenue" DESC
    """
    return await fetch(sql, lookback_days)


async def cashier_loss_prevention_signals(lookback_days: int = 90) -> list[dict]:
    sql = """
    WITH sales AS (
        SELECT t.cashier_id,
            SUM(CASE WHEN te.quantity > 0
                     THEN te.quantity*te.price ELSE 0 END) AS gross,
            SUM(CASE WHEN te.quantity < 0
                     THEN -te.quantity*te.price ELSE 0 END) AS returns,
            COUNT(DISTINCT CASE WHEN te.quantity < 0
                                THEN t.transaction_number END) AS return_txns,
            COUNT(DISTINCT t.transaction_number) AS txns
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
        WHERE t.time >= NOW() - make_interval(days => $1)
        GROUP BY t.cashier_id
    ),
    nosale AS (
        SELECT cashier_id, COUNT(*) AS events
        FROM non_tender_transaction
        WHERE transaction_type = 13
          AND time >= NOW() - make_interval(days => $1)
        GROUP BY cashier_id
    ),
    drops AS (
        SELECT cashier_id, COUNT(*) AS evt, SUM(amount) AS tot
        FROM drop_payout
        WHERE time >= NOW() - make_interval(days => $1)
        GROUP BY cashier_id
    )
    SELECT
        ca.id AS "CashierID", ca.name AS "Cashier", ca.inactive AS "Inactive",
        ca.return_limit AS "ReturnLimit", ca.floor_limit AS "FloorLimit",
        ca.security_level AS "SecurityLevel",
        COALESCE(s.txns, 0)        AS "Transactions",
        COALESCE(s.gross, 0)       AS "GrossSales",
        COALESCE(s.returns, 0)     AS "ReturnValue",
        COALESCE(s.return_txns, 0) AS "ReturnTransactions",
        CASE WHEN COALESCE(s.gross,0) > 0
             THEN COALESCE(s.returns,0)*100.0/s.gross ELSE 0 END AS "ReturnRatePct",
        COALESCE(n.events, 0) AS "NoSaleEvents",
        COALESCE(d.evt, 0)    AS "DropEvents",
        COALESCE(d.tot, 0)    AS "DropTotal"
    FROM cashier ca
        LEFT JOIN sales s  ON ca.id = s.cashier_id
        LEFT JOIN nosale n ON ca.id = n.cashier_id
        LEFT JOIN drops d  ON ca.id = d.cashier_id
    WHERE COALESCE(s.txns,0) + COALESCE(n.events,0) + COALESCE(d.evt,0) > 0
    ORDER BY (
        CASE WHEN COALESCE(s.gross,0) > 0
             THEN COALESCE(s.returns,0)*100.0/s.gross ELSE 0 END
        + COALESCE(n.events, 0)*0.5
    ) DESC
    """
    return await fetch(sql, lookback_days)


async def cashier_no_sale_drawer_opens(lookback_days: int = 30) -> list[dict]:
    sql = """
    SELECT
        ca.id AS "CashierID", ca.name AS "Cashier",
        COUNT(*)        AS "Events",
        MIN(nt.time)    AS "FirstEvent",
        MAX(nt.time)    AS "LastEvent"
    FROM non_tender_transaction nt
        LEFT JOIN cashier ca ON nt.cashier_id = ca.id
    WHERE nt.transaction_type = 13
      AND nt.time >= NOW() - make_interval(days => $1)
    GROUP BY ca.id, ca.name
    ORDER BY "Events" DESC
    """
    return await fetch(sql, lookback_days)


async def cashier_hourly_productivity(lookback_days: int = 30) -> list[dict]:
    sql = """
    WITH hrs AS (
        SELECT cashier_id, SUM(hours) AS h
        FROM time_card
        WHERE time_in >= NOW() - make_interval(days => $1)
          AND time_out IS NOT NULL
        GROUP BY cashier_id
    ),
    sales AS (
        SELECT t.cashier_id,
            COUNT(DISTINCT t.transaction_number) AS txns,
            SUM(te.quantity * te.price)          AS net
        FROM "transaction" t
            JOIN transaction_entry te
                ON t.transaction_number = te.transaction_number
        WHERE t.time >= NOW() - make_interval(days => $1)
        GROUP BY t.cashier_id
    )
    SELECT
        ca.id AS "CashierID", ca.name AS "Cashier",
        COALESCE(hrs.h, 0)         AS "HoursWorked",
        COALESCE(s.txns, 0)        AS "Transactions",
        COALESCE(s.net, 0)         AS "NetRevenue",
        CASE WHEN COALESCE(hrs.h,0) > 0
             THEN COALESCE(s.net,0)/hrs.h ELSE 0 END AS "DollarsPerHour",
        CASE WHEN COALESCE(hrs.h,0) > 0
             THEN COALESCE(s.txns,0)::numeric/hrs.h ELSE 0 END AS "TxnsPerHour"
    FROM cashier ca
        LEFT JOIN hrs ON ca.id = hrs.cashier_id
        LEFT JOIN sales s ON ca.id = s.cashier_id
    WHERE COALESCE(hrs.h,0) > 0 OR COALESCE(s.net,0) > 0
    ORDER BY "DollarsPerHour" DESC
    """
    return await fetch(sql, lookback_days)


# --------------------------------------------------------------------------- #
# Tender / payment mix
# --------------------------------------------------------------------------- #

async def tender_mix(start_date: str, end_date: str) -> list[dict]:
    sql = """
    WITH window_total AS (
        SELECT SUM(amount) AS total
        FROM tender_entry
        WHERE time >= $1::date
          AND time < $2::date + INTERVAL '1 day'
    )
    SELECT
        te.tender_id AS "TenderID", t.description AS "Tender",
        t.code AS "Code",
        COUNT(*)             AS "Entries",
        SUM(te.amount)       AS "Amount",
        CASE WHEN (SELECT total FROM window_total) > 0
             THEN SUM(te.amount)*100.0
                  / (SELECT total FROM window_total)
             ELSE 0 END      AS "PctOfTotal"
    FROM tender_entry te
        JOIN tender t ON te.tender_id = t.id
    WHERE te.time >= $1::date
      AND te.time < $2::date + INTERVAL '1 day'
    GROUP BY te.tender_id, t.description, t.code
    ORDER BY "Amount" DESC NULLS LAST
    """
    return await fetch(sql, start_date, end_date)


async def cash_drops(days: int = 30) -> list[dict]:
    sql = """
    SELECT
        dp.time AS "Time", ca.name AS "Cashier", dp.amount AS "Amount",
        dp.recipient AS "Recipient", dp.comment AS "Comment",
        rc.description AS "Reason"
    FROM drop_payout dp
        LEFT JOIN cashier ca ON dp.cashier_id = ca.id
        LEFT JOIN reason_code rc ON dp.reason_code_id = rc.id
    WHERE dp.time >= NOW() - make_interval(days => $1)
    ORDER BY dp.time DESC
    LIMIT 500
    """
    return await fetch(sql, days)


# --------------------------------------------------------------------------- #
# Procurement / supplier
# --------------------------------------------------------------------------- #

async def supplier_scorecard(lookback_days: int = 365) -> list[dict]:
    sql = """
    WITH sales AS (
        SELECT i.supplier_id,
               COUNT(DISTINCT i.id)            AS skus,
               SUM(te.quantity)                AS units,
               SUM(te.quantity * te.price)     AS revenue,
               SUM(te.quantity * te.cost)      AS cogs,
               SUM(te.quantity * (te.price - te.cost)) AS gp
        FROM transaction_entry te
            JOIN item i ON te.item_id = i.id
        WHERE te.transaction_time >= NOW() - make_interval(days => $1)
        GROUP BY i.supplier_id
    ),
    po AS (
        SELECT
            po.supplier_id,
            COUNT(DISTINCT po.id) AS pos,
            SUM(poe.quantity_ordered) AS ordered,
            SUM(poe.quantity_received) AS received,
            AVG(CASE WHEN poe.last_received_date IS NOT NULL
                     THEN (poe.last_received_date::date
                           - po.date_created::date)::float
                     END) AS lead_days
        FROM purchase_order po
            JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        WHERE po.date_created >= NOW() - make_interval(days => $1)
        GROUP BY po.supplier_id
    )
    SELECT
        s.supplier_name AS "SupplierName",
        COALESCE(sa.skus, 0)    AS "ActiveSkus",
        COALESCE(sa.revenue, 0) AS "Revenue",
        COALESCE(sa.gp, 0)      AS "GrossProfit",
        CASE WHEN COALESCE(sa.revenue,0) > 0
             THEN COALESCE(sa.gp,0)*100.0/sa.revenue
             ELSE 0 END         AS "GrossMarginPct",
        COALESCE(po.pos, 0)     AS "POs",
        COALESCE(po.ordered, 0) AS "UnitsOrdered",
        COALESCE(po.received,0) AS "UnitsReceived",
        CASE WHEN COALESCE(po.ordered,0) > 0
             THEN COALESCE(po.received,0)*100.0/po.ordered
             ELSE NULL END      AS "FillRatePct",
        po.lead_days            AS "AvgLeadTimeDays"
    FROM supplier s
        LEFT JOIN sales sa ON s.id = sa.supplier_id
        LEFT JOIN po       ON s.id = po.supplier_id
    WHERE COALESCE(sa.revenue,0) > 0 OR COALESCE(po.pos,0) > 0
    ORDER BY COALESCE(sa.revenue,0) DESC
    LIMIT 500
    """
    return await fetch(sql, lookback_days)


async def purchase_orders_open(top: int = 100) -> list[dict]:
    sql = """
    SELECT
        po.po_number AS "PONumber", s.supplier_name AS "SupplierName",
        po.status AS "Status",
        po.date_created AS "DateCreated", po.date_placed AS "DatePlaced",
        po.required_date AS "RequiredDate",
        (CURRENT_DATE - po.date_created::date)::int AS "AgeDays",
        SUM(poe.quantity_ordered)  AS "UnitsOrdered",
        SUM(poe.quantity_received) AS "UnitsReceived",
        CASE WHEN SUM(poe.quantity_ordered) > 0
             THEN SUM(poe.quantity_received)*100.0
                  / SUM(poe.quantity_ordered)
             ELSE 0 END           AS "FillPct",
        COUNT(poe.id)             AS "Lines"
    FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
    WHERE po.status < 5
    GROUP BY po.po_number, s.supplier_name, po.status, po.date_created,
             po.date_placed, po.required_date
    ORDER BY po.date_created DESC
    LIMIT $1
    """
    return await fetch(sql, top)


async def lead_time_analysis(supplier_query: str | None = None,
                             lookback_days: int = 365) -> list[dict]:
    like = f"%{supplier_query}%" if supplier_query else "%"
    sql = """
    SELECT
        s.supplier_name AS "SupplierName",
        COUNT(*) AS "ReceivedPOs",
        MIN((poe.last_received_date::date - po.date_created::date)::int) AS "MinDays",
        AVG((poe.last_received_date::date - po.date_created::date)::float) AS "AvgDays",
        MAX((poe.last_received_date::date - po.date_created::date)::int) AS "MaxDays",
        SUM(poe.quantity_received) AS "TotalUnitsReceived"
    FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
    WHERE poe.last_received_date IS NOT NULL
      AND po.date_created >= NOW() - make_interval(days => $1)
      AND s.supplier_name ILIKE $2
    GROUP BY s.supplier_name
    ORDER BY "AvgDays" DESC NULLS LAST
    """
    return await fetch(sql, lookback_days, like)


async def purchase_history_for_item(item_code: str,
                                    lookback_days: int = 730) -> list[dict]:
    sql = """
    SELECT
        po.po_number AS "PONumber",
        po.date_created AS "DateCreated",
        poe.last_received_date AS "LastReceivedDate",
        s.supplier_name AS "SupplierName",
        poe.quantity_ordered AS "QuantityOrdered",
        poe.quantity_received AS "QuantityReceived",
        poe.price AS "UnitCost",
        (poe.quantity_received * poe.price) AS "LineCost"
    FROM purchase_order_entry poe
        JOIN purchase_order po ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
    WHERE i.item_lookup_code = $1
      AND po.date_created >= NOW() - make_interval(days => $2)
    ORDER BY po.date_created DESC
    LIMIT 500
    """
    return await fetch(sql, item_code, lookback_days)


async def receiving_anomalies(lookback_days: int = 90,
                              min_variance_pct: float = 20.0) -> list[dict]:
    sql = """
    SELECT
        po.po_number AS "PONumber", po.date_created AS "DateCreated",
        s.supplier_name AS "SupplierName",
        i.item_lookup_code AS "ItemLookupCode",
        i.description AS "Description",
        poe.quantity_ordered AS "QuantityOrdered",
        poe.quantity_received AS "QuantityReceived",
        (poe.quantity_received - poe.quantity_ordered) AS "Variance",
        CASE WHEN poe.quantity_ordered > 0
             THEN (poe.quantity_received - poe.quantity_ordered)*100.0
                  / poe.quantity_ordered
             ELSE NULL END AS "VariancePct"
    FROM purchase_order_entry poe
        JOIN purchase_order po ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
    WHERE po.date_created >= NOW() - make_interval(days => $1)
      AND poe.quantity_received > 0
      AND poe.quantity_ordered > 0
      AND ABS(poe.quantity_received - poe.quantity_ordered)*100.0
              / poe.quantity_ordered >= $2
    ORDER BY ABS(poe.quantity_received - poe.quantity_ordered) DESC
    LIMIT 500
    """
    return await fetch(sql, lookback_days, min_variance_pct)


# --------------------------------------------------------------------------- #
# Inventory intelligence
# --------------------------------------------------------------------------- #

async def inventory_turns(group_by: str = "department",
                          lookback_days: int = 365) -> list[dict]:
    gmap = {
        "total":      "'ALL'",
        "department": "COALESCE(d.name,'(none)')",
        "category":   "COALESCE(d.name,'(none)') || ' / ' || COALESCE(c.name,'(none)')",
        "supplier":   "COALESCE(s.supplier_name,'(none)')",
    }
    gby = {
        "total":      "",
        "department": "GROUP BY d.name",
        "category":   "GROUP BY d.name, c.name",
        "supplier":   "GROUP BY s.supplier_name",
    }
    if group_by not in gmap:
        raise ValueError(f"group_by must be one of {list(gmap)}")
    sql = f"""
    WITH sales AS (
        SELECT i.id AS item_id,
               SUM(te.quantity)                     AS units,
               SUM(te.quantity * te.cost)           AS cogs,
               SUM(te.quantity * (te.price - te.cost)) AS gp
        FROM transaction_entry te
            JOIN item i ON te.item_id = i.id
        WHERE te.transaction_time >= NOW() - make_interval(days => $1)
        GROUP BY i.id
    )
    SELECT
        {gmap[group_by]} AS "Bucket",
        COUNT(DISTINCT i.id) AS "Skus",
        SUM(i.cost * i.quantity)                AS "InventoryValueAtCost",
        SUM(COALESCE(sa.cogs, 0))               AS "CogsInWindow",
        SUM(COALESCE(sa.gp, 0))                 AS "GrossProfit",
        CASE WHEN SUM(i.cost * i.quantity) > 0
             THEN SUM(COALESCE(sa.cogs,0)) / SUM(i.cost * i.quantity)
             ELSE 0 END                         AS "Turns",
        CASE WHEN SUM(i.cost * i.quantity) > 0
             THEN SUM(COALESCE(sa.gp,0)) / SUM(i.cost * i.quantity)
             ELSE 0 END                         AS "GMROI"
    FROM item i
        LEFT JOIN sales sa ON i.id = sa.item_id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.inactive = 0 AND i.quantity > 0
    {gby[group_by]}
    ORDER BY "GrossProfit" DESC NULLS LAST
    """
    return await fetch(sql, lookback_days)


async def price_change_history(item_code: str, days: int = 365) -> list[dict]:
    sql = """
    SELECT
        ivl.last_updated AS "LastUpdated",
        ivl.amount_type AS "AmountType",
        ivl.old_amount AS "OldAmount",
        ivl.new_amount AS "NewAmount",
        (ivl.new_amount - ivl.old_amount) AS "Delta",
        CASE WHEN ivl.old_amount <> 0
             THEN (ivl.new_amount - ivl.old_amount)*100.0/ivl.old_amount
             ELSE NULL END AS "DeltaPct"
    FROM item_value_log ivl
        JOIN item i ON ivl.item_id = i.id
    WHERE i.item_lookup_code = $1
      AND ivl.last_updated >= NOW() - make_interval(days => $2)
    ORDER BY ivl.last_updated DESC
    """
    return await fetch(sql, item_code, days)


async def cost_change_alerts(min_pct: float = 10.0, days: int = 30,
                             top: int = 100) -> list[dict]:
    sql = """
    SELECT
        i.item_lookup_code AS "ItemLookupCode",
        i.description AS "Description",
        d.name AS "Department", s.supplier_name AS "Supplier",
        ivl.last_updated AS "ChangedAt",
        ivl.old_amount AS "OldCost",
        ivl.new_amount AS "NewCost",
        (ivl.new_amount - ivl.old_amount) AS "Delta",
        CASE WHEN ivl.old_amount <> 0
             THEN (ivl.new_amount - ivl.old_amount)*100.0/ivl.old_amount
             ELSE NULL END AS "DeltaPct"
    FROM item_value_log ivl
        JOIN item i ON ivl.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE ivl.amount_type = 'C'
      AND ivl.last_updated >= NOW() - make_interval(days => $2)
      AND ivl.old_amount <> 0
      AND ABS((ivl.new_amount - ivl.old_amount)*100.0/ivl.old_amount) >= $1
    ORDER BY ABS((ivl.new_amount - ivl.old_amount)*100.0/ivl.old_amount) DESC
    LIMIT $3
    """
    return await fetch(sql, min_pct, days, top)


async def negative_inventory(top: int = 100) -> list[dict]:
    sql = """
    SELECT
        i.item_lookup_code AS "ItemLookupCode",
        i.description AS "Description",
        d.name AS "Department", s.supplier_name AS "Supplier",
        i.quantity AS "QtyOnHand",
        i.quantity_committed AS "QtyCommitted",
        i.last_received AS "LastReceived",
        i.last_sold AS "LastSold",
        i.last_counted AS "LastCounted",
        i.cost AS "Cost"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.quantity < 0
    ORDER BY i.quantity ASC
    LIMIT $1
    """
    return await fetch(sql, top)


async def aging_inventory_buckets() -> list[dict]:
    sql = """
    SELECT
        CASE
            WHEN i.last_sold IS NULL THEN '5: Never sold'
            WHEN (CURRENT_DATE - i.last_sold::date) <= 30  THEN '1: 0-30 days'
            WHEN (CURRENT_DATE - i.last_sold::date) <= 90  THEN '2: 31-90 days'
            WHEN (CURRENT_DATE - i.last_sold::date) <= 180 THEN '3: 91-180 days'
            WHEN (CURRENT_DATE - i.last_sold::date) <= 365 THEN '4: 181-365 days'
            ELSE '6: >365 days'
        END AS "Bucket",
        COUNT(*) AS "Skus",
        SUM(i.quantity) AS "Units",
        SUM(i.cost * i.quantity) AS "InventoryValue"
    FROM item i
    WHERE i.inactive = 0 AND i.quantity > 0
    GROUP BY 1
    ORDER BY 1
    """
    return await fetch(sql)


# --------------------------------------------------------------------------- #
# Margin / P&L
# --------------------------------------------------------------------------- #

async def pnl_summary(start_date: str, end_date: str,
                      group_by: str = "department") -> list[dict]:
    gmap = {
        "total":      ("'ALL'", ""),
        "department": ("COALESCE(d.name,'(none)')", "GROUP BY d.name"),
        "category":   ("COALESCE(d.name,'(none)') || ' / ' || COALESCE(c.name,'(none)')",
                       "GROUP BY d.name, c.name"),
        "supplier":   ("COALESCE(s.supplier_name,'(none)')",
                       "GROUP BY s.supplier_name"),
    }
    if group_by not in gmap:
        raise ValueError(f"group_by must be one of {list(gmap)}")
    sel, grp = gmap[group_by]
    sql = f"""
    SELECT
        {sel} AS "Bucket",
        COUNT(DISTINCT te.transaction_number) AS "Transactions",
        SUM(CASE WHEN te.quantity > 0 THEN te.quantity ELSE 0 END) AS "UnitsSold",
        SUM(CASE WHEN te.quantity < 0 THEN -te.quantity ELSE 0 END) AS "UnitsReturned",
        SUM(CASE WHEN te.quantity > 0
                 THEN te.quantity*te.price ELSE 0 END) AS "GrossRevenue",
        SUM(CASE WHEN te.quantity < 0
                 THEN te.quantity*te.price ELSE 0 END) AS "Returns",
        SUM(te.quantity * te.price) AS "NetRevenue",
        SUM(te.quantity * te.cost)  AS "Cogs",
        SUM(te.quantity * (te.price - te.cost)) AS "GrossProfit",
        CASE WHEN SUM(te.quantity * te.price) > 0
             THEN SUM(te.quantity * (te.price - te.cost))*100.0
                  / SUM(te.quantity * te.price)
             ELSE 0 END AS "GrossMarginPct"
    FROM transaction_entry te
        JOIN item i ON te.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE te.transaction_time >= $1::date
      AND te.transaction_time < $2::date + INTERVAL '1 day'
    {grp}
    ORDER BY "NetRevenue" DESC NULLS LAST
    """
    return await fetch(sql, start_date, end_date)


async def discount_impact(start_date: str, end_date: str) -> dict:
    sql = """
    SELECT
        SUM(CASE WHEN te.full_price > te.price AND te.quantity > 0
                 THEN (te.full_price - te.price) * te.quantity
                 ELSE 0 END) AS "DiscountGiven",
        SUM(CASE WHEN te.full_price > te.price AND te.quantity > 0
                 THEN te.quantity ELSE 0 END) AS "DiscountedUnits",
        SUM(CASE WHEN te.quantity > 0
                 THEN te.quantity * te.full_price
                 ELSE 0 END) AS "GrossAtFullPrice",
        SUM(CASE WHEN te.quantity > 0
                 THEN te.quantity * te.price
                 ELSE 0 END) AS "ActualGross",
        COUNT(DISTINCT CASE WHEN te.full_price > te.price
                            THEN te.transaction_number END) AS "DiscountedTxns"
    FROM transaction_entry te
    WHERE te.transaction_time >= $1::date
      AND te.transaction_time < $2::date + INTERVAL '1 day'
    """
    r = await fetchrow(sql, start_date, end_date)
    return r or {}


async def items_below_cost(top: int = 50) -> list[dict]:
    sql = """
    SELECT
        i.item_lookup_code AS "ItemLookupCode",
        i.description AS "Description",
        d.name AS "Department", s.supplier_name AS "Supplier",
        i.cost AS "Cost", i.price AS "Price",
        (i.price - i.cost) AS "UnitMargin",
        i.quantity AS "QtyOnHand",
        (i.cost * i.quantity) AS "InventoryValue"
    FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE i.inactive = 0
      AND i.cost > 0
      AND i.price <= i.cost
    ORDER BY (i.cost * i.quantity) DESC
    LIMIT $1
    """
    return await fetch(sql, top)


# --------------------------------------------------------------------------- #
# Time / pattern
# --------------------------------------------------------------------------- #

async def hourly_heatmap(lookback_days: int = 90) -> list[dict]:
    sql = """
    SELECT
        (EXTRACT(DOW FROM transaction_time)::int + 1) AS "DayOfWeek",
        TRIM(to_char(transaction_time, 'Day'))        AS "DayName",
        EXTRACT(HOUR FROM transaction_time)::int      AS "Hour",
        COUNT(DISTINCT transaction_number)             AS "Txns",
        SUM(quantity * price)                          AS "NetRevenue"
    FROM transaction_entry
    WHERE transaction_time >= NOW() - make_interval(days => $1)
    GROUP BY 1, 2, 3
    ORDER BY 1, 3
    """
    return await fetch(sql, lookback_days)


async def peak_hours(lookback_days: int = 30, top: int = 10) -> list[dict]:
    sql = """
    SELECT
        TRIM(to_char(transaction_time, 'Day'))   AS "DayName",
        EXTRACT(HOUR FROM transaction_time)::int AS "Hour",
        COUNT(DISTINCT transaction_number)        AS "Txns",
        SUM(quantity * price)                     AS "NetRevenue",
        SUM(quantity)                             AS "Units"
    FROM transaction_entry
    WHERE transaction_time >= NOW() - make_interval(days => $1)
    GROUP BY 1, 2
    ORDER BY "NetRevenue" DESC NULLS LAST
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def weekday_seasonality(lookback_days: int = 365) -> list[dict]:
    sql = """
    WITH per_day AS (
        SELECT transaction_time::date AS d,
               TRIM(to_char(transaction_time, 'Day')) AS day_name,
               (EXTRACT(DOW FROM transaction_time)::int + 1) AS dow,
               SUM(quantity * price) AS net
        FROM transaction_entry
        WHERE transaction_time >= NOW() - make_interval(days => $1)
        GROUP BY 1, 2, 3
    )
    SELECT
        dow AS "DOW", day_name AS "DayName",
        COUNT(*) AS "DaysObserved",
        AVG(net) AS "AvgNet",
        SUM(net) AS "TotalNet"
    FROM per_day
    GROUP BY dow, day_name
    ORDER BY dow
    """
    return await fetch(sql, lookback_days)


# --------------------------------------------------------------------------- #
# Basket / cross-sell
# --------------------------------------------------------------------------- #

async def basket_size_distribution(lookback_days: int = 30) -> list[dict]:
    sql = """
    WITH baskets AS (
        SELECT transaction_number,
               SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS items
        FROM transaction_entry
        WHERE transaction_time >= NOW() - make_interval(days => $1)
        GROUP BY transaction_number
    )
    SELECT
        CASE
            WHEN items <= 1 THEN '1'
            WHEN items <= 2 THEN '2'
            WHEN items <= 3 THEN '3'
            WHEN items <= 5 THEN '4-5'
            WHEN items <= 10 THEN '6-10'
            WHEN items <= 20 THEN '11-20'
            ELSE '20+'
        END AS "BasketSize",
        COUNT(*) AS "Baskets"
    FROM baskets
    GROUP BY 1
    ORDER BY 1
    """
    return await fetch(sql, lookback_days)


async def item_affinity(item_code: str, lookback_days: int = 90,
                        top: int = 20) -> list[dict]:
    sql = """
    WITH anchor AS (
        SELECT DISTINCT te.transaction_number
        FROM transaction_entry te
            JOIN item i ON te.item_id = i.id
        WHERE i.item_lookup_code = $1
          AND te.transaction_time >= NOW() - make_interval(days => $2)
          AND te.quantity > 0
    )
    SELECT
        i2.item_lookup_code AS "ItemLookupCode",
        i2.description AS "Description",
        COUNT(DISTINCT te2.transaction_number) AS "CoOccurrences",
        SUM(te2.quantity)                       AS "UnitsBoughtWith"
    FROM anchor a
        JOIN transaction_entry te2
            ON te2.transaction_number = a.transaction_number
        JOIN item i2 ON te2.item_id = i2.id
    WHERE i2.item_lookup_code <> $1
      AND te2.quantity > 0
    GROUP BY i2.item_lookup_code, i2.description
    ORDER BY "CoOccurrences" DESC NULLS LAST
    LIMIT $3
    """
    return await fetch(sql, item_code, lookback_days, top)


# --------------------------------------------------------------------------- #
# Anomaly / forecast
# --------------------------------------------------------------------------- #

async def outlier_transactions(lookback_days: int = 30,
                               top: int = 25) -> list[dict]:
    sql = """
    SELECT
        t.transaction_number AS "TransactionNumber",
        t.time AS "Time",
        ca.name AS "Cashier",
        TRIM(BOTH ' ' FROM
             COALESCE(cu.first_name,'') || ' ' || COALESCE(cu.last_name,'')) AS "Customer",
        SUM(te.quantity) AS "Units",
        COUNT(te.id)     AS "Lines",
        SUM(te.quantity * te.price) AS "NetRevenue",
        SUM(te.quantity * (te.price - te.cost)) AS "GrossProfit"
    FROM "transaction" t
        JOIN transaction_entry te
            ON t.transaction_number = te.transaction_number
        LEFT JOIN cashier  ca ON t.cashier_id  = ca.id
        LEFT JOIN customer cu ON t.customer_id = cu.id
    WHERE t.time >= NOW() - make_interval(days => $1)
    GROUP BY t.transaction_number, t.time, ca.name,
             cu.first_name, cu.last_name
    ORDER BY "NetRevenue" DESC NULLS LAST
    LIMIT $2
    """
    return await fetch(sql, lookback_days, top)


async def expected_stockout_date(item_code: str,
                                 lookback_days: int = 90) -> dict:
    sql = """
    SELECT
        i.item_lookup_code AS "ItemLookupCode",
        i.description AS "Description",
        i.quantity AS "QtyOnHand",
        i.quantity_committed AS "QtyCommitted",
        (i.quantity - i.quantity_committed) AS "QtyAvailable",
        sales.units_sold AS "UnitsSold",
        ROUND(COALESCE(sales.units_sold,0)::numeric / $1, 2) AS "AvgDailySales",
        CASE WHEN COALESCE(sales.units_sold,0) > 0
             THEN (CURRENT_DATE +
                   ((i.quantity - i.quantity_committed)
                    / (sales.units_sold::numeric / $1))::int)
             ELSE NULL END AS "ExpectedStockoutDate"
    FROM item i
        LEFT JOIN LATERAL (
            SELECT SUM(te.quantity) AS units_sold
            FROM transaction_entry te
            WHERE te.item_id = i.id
              AND te.quantity > 0
              AND te.transaction_time >= NOW() - make_interval(days => $1)
        ) sales ON TRUE
    WHERE i.item_lookup_code = $2
    """
    r = await fetchrow(sql, lookback_days, item_code)
    return r or {"error": "item not found"}


async def forecast_revenue(days_ahead: int = 30) -> dict:
    rr = await fetchrow("""
        SELECT SUM(quantity*price) AS rev30
        FROM transaction_entry
        WHERE transaction_time >= NOW() - INTERVAL '30 days'
    """)
    py = await fetchrow("""
        SELECT SUM(quantity*price) AS rev_py
        FROM transaction_entry
        WHERE transaction_time >= NOW() - make_interval(days => $1 + 365)
          AND transaction_time <  NOW() - INTERVAL '365 days'
    """, days_ahead)
    a = float((rr or {}).get("rev30") or 0) / 30.0 * days_ahead
    b = float((py or {}).get("rev_py") or 0)
    blended = (a + b) / 2 if (a and b) else (a or b)
    return {
        "DaysAhead": days_ahead,
        "RunRate30dProjection": a,
        "PriorYearSameWindow": b,
        "BlendedForecast": blended,
    }


# --------------------------------------------------------------------------- #
# Universal helpers + dashboards
# --------------------------------------------------------------------------- #

async def entity_lookup(query: str, top: int = 10) -> dict:
    like = f"%{query}%"
    out = {}
    out["items"] = await fetch("""
        SELECT item_lookup_code AS "ItemLookupCode",
               description AS "Description",
               quantity AS "Quantity",
               price AS "Price", cost AS "Cost"
        FROM item
        WHERE item_lookup_code ILIKE $1 OR description ILIKE $1
        ORDER BY inactive, item_lookup_code
        LIMIT $2
    """, like, top)
    out["customers"] = await fetch("""
        SELECT id AS "ID", first_name AS "FirstName",
               last_name AS "LastName", company AS "Company",
               phone_number AS "PhoneNumber",
               email_address AS "EmailAddress",
               total_sales AS "TotalSales"
        FROM customer
        WHERE first_name ILIKE $1 OR last_name ILIKE $1
           OR company ILIKE $1 OR phone_number ILIKE $1
           OR email_address ILIKE $1
        ORDER BY total_sales DESC NULLS LAST
        LIMIT $2
    """, like, top)
    out["cashiers"] = await fetch("""
        SELECT id AS "ID", name AS "Name", number AS "Number",
               inactive AS "Inactive"
        FROM cashier WHERE name ILIKE $1 OR number ILIKE $1
        LIMIT $2
    """, like, top)
    out["suppliers"] = await fetch("""
        SELECT id AS "ID", supplier_name AS "SupplierName"
        FROM supplier WHERE supplier_name ILIKE $1
        LIMIT $2
    """, like, top)
    out["departments"] = await fetch("""
        SELECT id AS "ID", name AS "Name" FROM department WHERE name ILIKE $1
        LIMIT $2
    """, like, top)
    out["categories"] = await fetch("""
        SELECT id AS "ID", name AS "Name" FROM category WHERE name ILIKE $1
        LIMIT $2
    """, like, top)
    return out


async def procurement_briefing() -> dict:
    kpi = await fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM item WHERE inactive = 0)              AS "ActiveSkus",
            (SELECT SUM(cost * quantity) FROM item
               WHERE inactive = 0 AND quantity > 0)                     AS "InventoryCostValue",
            (SELECT COUNT(*) FROM item
               WHERE inactive = 0 AND (quantity - quantity_committed) <= 0) AS "StockoutSkus",
            (SELECT SUM(quantity * price) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '30 days'
                 AND quantity > 0)                                      AS "Revenue30d",
            (SELECT SUM(quantity * price) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '365 days'
                 AND quantity > 0)                                      AS "Revenue1y"
    """)
    return {
        "kpis": kpi or {},
        "top_reorder": await reorder_recommendations(limit=10),
        "dead_stock_top": await dead_stock(limit=10),
        "supplier_spend_top": await supplier_spend(top=10),
    }


async def executive_dashboard() -> dict:
    kpis = await fetchrow("""
        SELECT
            (SELECT SUM(quantity*price) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '7 days')  AS "NetRev7d",
            (SELECT SUM(quantity*price) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '30 days') AS "NetRev30d",
            (SELECT SUM(quantity*price) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '365 days') AS "NetRev365d",
            (SELECT SUM(quantity*(price-cost)) FROM transaction_entry
               WHERE transaction_time >= NOW() - INTERVAL '30 days') AS "GrossProfit30d",
            (SELECT COUNT(*) FROM item WHERE inactive=0)             AS "ActiveSkus",
            (SELECT SUM(cost*quantity) FROM item
               WHERE inactive=0 AND quantity > 0)                    AS "InventoryAtCost",
            (SELECT COUNT(*) FROM item
               WHERE inactive=0 AND (quantity-quantity_committed) <= 0) AS "Stockouts",
            (SELECT COUNT(*) FROM item WHERE quantity < 0)            AS "NegativeStockSkus",
            (SELECT COUNT(*) FROM purchase_order WHERE status < 5)    AS "OpenPOs",
            (SELECT COUNT(*) FROM customer)                           AS "NamedCustomers",
            (SELECT COUNT(*) FROM cashier WHERE COALESCE(inactive,0)=0) AS "ActiveCashiers",
            (SELECT COUNT(*) FROM non_tender_transaction
               WHERE transaction_type=13
                 AND time >= NOW() - INTERVAL '7 days')              AS "NoSaleEvents7d"
    """)
    now_row = await fetchrow("SELECT NOW() AS now")
    return {
        "as_of": now_row["now"] if now_row else None,
        "kpis": kpis or {},
        "top_reorder": await fetch("""
            SELECT i.item_lookup_code AS "ItemLookupCode",
                   i.description AS "Description",
                   (i.quantity - i.quantity_committed) AS "QtyAvailable",
                   i.reorder_point AS "ReorderPoint"
            FROM item i
            WHERE i.inactive = 0
              AND (i.quantity - i.quantity_committed) <= i.reorder_point
              AND i.reorder_point > 0
            ORDER BY (i.reorder_point - (i.quantity - i.quantity_committed)) DESC
            LIMIT 5
        """),
        "top_customers_30d": await fetch("""
            SELECT c.first_name AS "FirstName", c.last_name AS "LastName",
                   c.company AS "Company",
                   SUM(te.quantity*te.price) AS "Net30d"
            FROM customer c
                JOIN "transaction" t ON t.customer_id = c.id
                JOIN transaction_entry te
                    ON te.transaction_number = t.transaction_number
            WHERE t.time >= NOW() - INTERVAL '30 days'
            GROUP BY c.first_name, c.last_name, c.company
            ORDER BY "Net30d" DESC NULLS LAST
            LIMIT 5
        """),
        "top_cashiers_30d": await fetch("""
            SELECT ca.name AS "Cashier",
                   SUM(te.quantity*te.price) AS "Net30d",
                   COUNT(DISTINCT t.transaction_number) AS "Txns"
            FROM cashier ca
                JOIN "transaction" t ON t.cashier_id = ca.id
                JOIN transaction_entry te
                    ON te.transaction_number = t.transaction_number
            WHERE t.time >= NOW() - INTERVAL '30 days'
            GROUP BY ca.name
            ORDER BY "Net30d" DESC NULLS LAST
            LIMIT 5
        """),
    }


# --------------------------------------------------------------------------- #
# Run readonly SQL escape hatch
# --------------------------------------------------------------------------- #

_BANNED = (" insert ", " update ", " delete ", " drop ", " alter ",
           " truncate ", " merge ", " grant ", " revoke ", " create ",
           " copy ", " do ")

async def run_readonly_sql(sql: str, row_limit: int = 500) -> list[dict]:
    norm = " ".join(sql.strip().split()).lower()
    if ";" in norm.rstrip(";"):
        raise ValueError("only a single statement is allowed")
    if not (norm.startswith("select") or norm.startswith("with")):
        raise ValueError("only SELECT / WITH queries are allowed")
    padded = f" {norm} "
    for b in _BANNED:
        if b in padded:
            raise ValueError(f"statement rejected: contains '{b.strip()}'")
    # Wrap in a LIMIT for safety.
    wrapped = f"SELECT * FROM ({sql.rstrip(';')}) _q LIMIT {int(row_limit)}"
    return await fetch(wrapped)
