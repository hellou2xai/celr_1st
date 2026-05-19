"""
MCP server (Streamable HTTP transport) for the WINEZONE demo.

Registers the same tool surface as the original
`mcp-procurement/server.py` + `intel.py` — only the implementation has
been retargeted to async Postgres. Each tool simply delegates to the
matching async function in `analytics`.

The MCP app object exposed at the bottom is an ASGI application; the
FastAPI app in `main.py` mounts it under /mcp.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import analytics

mcp = FastMCP("winezone-procurement-demo")


# --------------------------------------------------------------------------- #
# Core procurement tools
# --------------------------------------------------------------------------- #

@mcp.tool()
async def ping() -> dict:
    """Verify Postgres connectivity and return server identity."""
    return await analytics.ping()


@mcp.tool()
async def reorder_recommendations(lookback_days: int = 365,
                                  horizon_days: int = 7,
                                  only_active: bool = True,
                                  limit: int = 200) -> list[dict]:
    """
    Items that need to be reordered now. Computes avg daily sales over
    `lookback_days`, projects a `horizon_days` supply need, and flags
    items whose available qty is below that need. Most urgent first.
    """
    return await analytics.reorder_recommendations(
        lookback_days, horizon_days, only_active, limit
    )


@mcp.tool()
async def dead_stock(no_sales_days: int = 180,
                     min_inventory_value: float = 0.0,
                     limit: int = 200) -> list[dict]:
    """Items still on hand with no sales in `no_sales_days` days."""
    return await analytics.dead_stock(no_sales_days, min_inventory_value, limit)


@mcp.tool()
async def supplier_spend(lookback_days: int = 365, top: int = 25) -> list[dict]:
    """Top suppliers by realised COGS over the lookback window."""
    return await analytics.supplier_spend(lookback_days, top)


@mcp.tool()
async def category_performance(lookback_days: int = 365,
                               top: int = 50) -> list[dict]:
    """Revenue, units, margin and SKU count by Department + Category."""
    return await analytics.category_performance(lookback_days, top)


@mcp.tool()
async def fast_movers(lookback_days: int = 30, top: int = 25) -> list[dict]:
    """Top sellers by units sold in the recent window."""
    return await analytics.fast_movers(lookback_days, top)


@mcp.tool()
async def overstock(min_days_of_stock: int = 120,
                    top: int = 100) -> list[dict]:
    """SKUs with too many days of cover at current velocity."""
    return await analytics.overstock(min_days_of_stock, top)


@mcp.tool()
async def stockouts() -> list[dict]:
    """Active items currently out of stock."""
    return await analytics.stockouts()


@mcp.tool()
async def inventory_valuation(group_by: str = "department") -> list[dict]:
    """Inventory valuation grouped by total/department/category/supplier."""
    return await analytics.inventory_valuation(group_by)


@mcp.tool()
async def item_lookup(query: str, limit: int = 25) -> list[dict]:
    """Fuzzy lookup on item code or description (substring match)."""
    return await analytics.item_lookup(query, limit)


@mcp.tool()
async def sales_trend(lookback_days: int = 90,
                      granularity: str = "day") -> list[dict]:
    """Time-series of sales. granularity = day | week | month."""
    return await analytics.sales_trend(lookback_days, granularity)


@mcp.tool()
async def sales_between(start_date: str, end_date: str,
                        group_by: str = "day") -> dict:
    """
    Net sales between two ISO dates (inclusive). Includes returns netted
    against sales and an RMS header reconciliation.
    """
    return await analytics.sales_between(start_date, end_date, group_by)


@mcp.tool()
async def procurement_briefing() -> dict:
    """KPI snapshot + top reorder + top dead stock + supplier spend."""
    return await analytics.procurement_briefing()


@mcp.tool()
async def run_readonly_sql(sql: str, row_limit: int = 500) -> list[dict]:
    """Escape hatch: SELECT/WITH only; mutations blocked."""
    return await analytics.run_readonly_sql(sql, row_limit)


# --------------------------------------------------------------------------- #
# Customer intelligence
# --------------------------------------------------------------------------- #

@mcp.tool()
async def customer_360(query: str) -> dict:
    """Full 360 view of a named customer (profile, RFM, history, items)."""
    return await analytics.customer_360(query)


@mcp.tool()
async def customer_rfm() -> list[dict]:
    """RFM segmentation of every named customer with at least one txn."""
    return await analytics.customer_rfm()


@mcp.tool()
async def top_customers(by: str = "spend", top: int = 25,
                        lookback_days: int = 365) -> list[dict]:
    """Top named customers by spend / visits / margin / avg_basket."""
    return await analytics.top_customers(by, top, lookback_days)


@mcp.tool()
async def customer_churn_risk(min_lifetime_spend: float = 5000.0,
                              no_purchase_days: int = 90) -> list[dict]:
    """Named customers with high lifetime spend and long absence."""
    return await analytics.customer_churn_risk(min_lifetime_spend, no_purchase_days)


@mcp.tool()
async def customer_purchase_history(customer_id: int,
                                    lookback_days: int = 365) -> list[dict]:
    """All transactions for a customer in the lookback window."""
    return await analytics.customer_purchase_history(customer_id, lookback_days)


# --------------------------------------------------------------------------- #
# Cashier intelligence
# --------------------------------------------------------------------------- #

@mcp.tool()
async def cashier_scorecard(lookback_days: int = 30) -> list[dict]:
    """Performance scorecard per cashier."""
    return await analytics.cashier_scorecard(lookback_days)


@mcp.tool()
async def cashier_loss_prevention_signals(lookback_days: int = 90) -> list[dict]:
    """Loss-prevention scorecard combining returns, no-sales, drops."""
    return await analytics.cashier_loss_prevention_signals(lookback_days)


@mcp.tool()
async def cashier_no_sale_drawer_opens(lookback_days: int = 30) -> list[dict]:
    """No-sale (drawer-opened-without-sale) events per cashier."""
    return await analytics.cashier_no_sale_drawer_opens(lookback_days)


@mcp.tool()
async def cashier_hourly_productivity(lookback_days: int = 30) -> list[dict]:
    """Sales per hour worked, joining TimeCard hours."""
    return await analytics.cashier_hourly_productivity(lookback_days)


# --------------------------------------------------------------------------- #
# Tender / payment
# --------------------------------------------------------------------------- #

@mcp.tool()
async def tender_mix(start_date: str, end_date: str) -> list[dict]:
    """Payment-method breakdown for a date range."""
    return await analytics.tender_mix(start_date, end_date)


@mcp.tool()
async def cash_drops(days: int = 30) -> list[dict]:
    """Cash drops / pay-outs from the till."""
    return await analytics.cash_drops(days)


# --------------------------------------------------------------------------- #
# Procurement / supplier
# --------------------------------------------------------------------------- #

@mcp.tool()
async def supplier_scorecard(lookback_days: int = 365) -> list[dict]:
    """Comprehensive supplier scorecard (sales + PO performance)."""
    return await analytics.supplier_scorecard(lookback_days)


@mcp.tool()
async def purchase_orders_open(top: int = 100) -> list[dict]:
    """Open / partial POs with ageing."""
    return await analytics.purchase_orders_open(top)


@mcp.tool()
async def lead_time_analysis(supplier_query: Optional[str] = None,
                             lookback_days: int = 365) -> list[dict]:
    """Distribution of PO lead times by supplier."""
    return await analytics.lead_time_analysis(supplier_query, lookback_days)


@mcp.tool()
async def purchase_history_for_item(item_code: str,
                                    lookback_days: int = 730) -> list[dict]:
    """All PO lines that bought this item."""
    return await analytics.purchase_history_for_item(item_code, lookback_days)


@mcp.tool()
async def receiving_anomalies(lookback_days: int = 90,
                              min_variance_pct: float = 20.0) -> list[dict]:
    """PO lines where receipts deviate from orders."""
    return await analytics.receiving_anomalies(lookback_days, min_variance_pct)


# --------------------------------------------------------------------------- #
# Inventory intelligence
# --------------------------------------------------------------------------- #

@mcp.tool()
async def inventory_turns(group_by: str = "department",
                          lookback_days: int = 365) -> list[dict]:
    """Inventory turnover and GMROI."""
    return await analytics.inventory_turns(group_by, lookback_days)


@mcp.tool()
async def price_change_history(item_code: str, days: int = 365) -> list[dict]:
    """Cost/price change log for one item."""
    return await analytics.price_change_history(item_code, days)


@mcp.tool()
async def cost_change_alerts(min_pct: float = 10.0, days: int = 30,
                             top: int = 100) -> list[dict]:
    """Items with significant cost changes in window."""
    return await analytics.cost_change_alerts(min_pct, days, top)


@mcp.tool()
async def negative_inventory(top: int = 100) -> list[dict]:
    """Items showing negative on-hand quantity."""
    return await analytics.negative_inventory(top)


@mcp.tool()
async def aging_inventory_buckets() -> list[dict]:
    """Active SKUs bucketed by days-since-last-sale."""
    return await analytics.aging_inventory_buckets()


# --------------------------------------------------------------------------- #
# Margin / P&L
# --------------------------------------------------------------------------- #

@mcp.tool()
async def pnl_summary(start_date: str, end_date: str,
                      group_by: str = "department") -> list[dict]:
    """Full P&L for a window."""
    return await analytics.pnl_summary(start_date, end_date, group_by)


@mcp.tool()
async def discount_impact(start_date: str, end_date: str) -> dict:
    """How much money was given away in discounts in window."""
    return await analytics.discount_impact(start_date, end_date)


@mcp.tool()
async def items_below_cost(top: int = 50) -> list[dict]:
    """Active items priced at or below cost."""
    return await analytics.items_below_cost(top)


# --------------------------------------------------------------------------- #
# Time / pattern
# --------------------------------------------------------------------------- #

@mcp.tool()
async def hourly_heatmap(lookback_days: int = 90) -> list[dict]:
    """Day-of-week x hour-of-day matrix of net sales."""
    return await analytics.hourly_heatmap(lookback_days)


@mcp.tool()
async def peak_hours(lookback_days: int = 30, top: int = 10) -> list[dict]:
    """Top hours of the week by net sales."""
    return await analytics.peak_hours(lookback_days, top)


@mcp.tool()
async def weekday_seasonality(lookback_days: int = 365) -> list[dict]:
    """Share of weekly sales by weekday."""
    return await analytics.weekday_seasonality(lookback_days)


# --------------------------------------------------------------------------- #
# Basket / cross-sell
# --------------------------------------------------------------------------- #

@mcp.tool()
async def basket_size_distribution(lookback_days: int = 30) -> list[dict]:
    """Histogram of items per basket."""
    return await analytics.basket_size_distribution(lookback_days)


@mcp.tool()
async def item_affinity(item_code: str, lookback_days: int = 90,
                        top: int = 20) -> list[dict]:
    """Items most frequently bought together with the given item."""
    return await analytics.item_affinity(item_code, lookback_days, top)


# --------------------------------------------------------------------------- #
# Anomaly / forecasting
# --------------------------------------------------------------------------- #

@mcp.tool()
async def outlier_transactions(lookback_days: int = 30,
                               top: int = 25) -> list[dict]:
    """Largest transactions by net amount."""
    return await analytics.outlier_transactions(lookback_days, top)


@mcp.tool()
async def expected_stockout_date(item_code: str,
                                 lookback_days: int = 90) -> dict:
    """Naive run-out forecast: avg daily sales x current available."""
    return await analytics.expected_stockout_date(item_code, lookback_days)


@mcp.tool()
async def forecast_revenue(days_ahead: int = 30) -> dict:
    """50/50 blend of 30d run rate and prior-year same window."""
    return await analytics.forecast_revenue(days_ahead)


# --------------------------------------------------------------------------- #
# Cross-entity + dashboard
# --------------------------------------------------------------------------- #

@mcp.tool()
async def entity_lookup(query: str, top: int = 10) -> dict:
    """Cross-entity search across items/customers/cashiers/suppliers/etc."""
    return await analytics.entity_lookup(query, top)


@mcp.tool()
async def executive_dashboard() -> dict:
    """One-shot multi-domain executive view."""
    return await analytics.executive_dashboard()


# --------------------------------------------------------------------------- #
# ASGI app for mounting in FastAPI
# --------------------------------------------------------------------------- #

# Streamable HTTP transport exposes /mcp endpoints over a single ASGI app.
mcp_app = mcp.streamable_http_app()
