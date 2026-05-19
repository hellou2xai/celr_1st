"""
FastAPI entrypoint for the WINEZONE demo.

Routes:
    GET  /             — marketing/landing page
    GET  /dashboard    — analytics dashboard (HTML)
    GET  /api/*        — JSON endpoints feeding the dashboard
    /mcp/*             — Streamable HTTP MCP server (~45 tools)
    GET  /healthz      — Render health check

The MCP server is mounted as a sub-ASGI app at /mcp. Visitors point their
Claude Code / Desktop / SDK client at https://<service>.onrender.com/mcp/
and get the same tool surface as the original WINEZONE procurement MCP.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import analytics
from .db import get_pool, close_pool
from .mcp_server import mcp_app

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="WINEZONE Procurement Demo",
    description="Live Postgres-backed retail intelligence MCP + dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
app.mount("/mcp", mcp_app)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    base_url = os.environ.get("PUBLIC_URL") or str(request.base_url).rstrip("/")
    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "mcp_url": f"{base_url}/mcp/"},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    try:
        await analytics.ping()
        return "ok"
    except Exception as e:  # pragma: no cover
        raise HTTPException(503, f"db unreachable: {e}")


# --------------------------------------------------------------------------- #
# REST API powering the dashboard
# --------------------------------------------------------------------------- #

@app.get("/api/executive")
async def api_executive():
    return await analytics.executive_dashboard()


@app.get("/api/sales-trend")
async def api_sales_trend(days: int = Query(180, ge=7, le=1460),
                          granularity: str = Query("week")):
    return await analytics.sales_trend(days, granularity)


@app.get("/api/fast-movers")
async def api_fast_movers(days: int = 30, top: int = 10):
    return await analytics.fast_movers(days, top)


@app.get("/api/category-performance")
async def api_category(days: int = 365, top: int = 20):
    return await analytics.category_performance(days, top)


@app.get("/api/supplier-spend")
async def api_supplier_spend(days: int = 365, top: int = 12):
    return await analytics.supplier_spend(days, top)


@app.get("/api/dead-stock")
async def api_dead_stock(top: int = 15):
    return await analytics.dead_stock(limit=top)


@app.get("/api/reorder")
async def api_reorder(limit: int = 15):
    return await analytics.reorder_recommendations(limit=limit)


@app.get("/api/aging-buckets")
async def api_aging():
    return await analytics.aging_inventory_buckets()


@app.get("/api/tender-mix")
async def api_tender(start_date: str, end_date: str):
    return await analytics.tender_mix(start_date, end_date)


@app.get("/api/hourly-heatmap")
async def api_heatmap(days: int = 90):
    return await analytics.hourly_heatmap(days)


@app.get("/api/item-lookup")
async def api_item_lookup(q: str, limit: int = 25):
    return await analytics.item_lookup(q, limit)


@app.get("/api/customer-rfm")
async def api_rfm():
    rows = await analytics.customer_rfm()
    # Aggregate counts per segment for the dashboard chart
    segments: dict[str, int] = {}
    for r in rows:
        segments[r["Segment"]] = segments.get(r["Segment"], 0) + 1
    return {"segments": segments, "rows": rows[:50]}


@app.get("/api/expected-stockout")
async def api_expected_stockout(item_code: str, days: int = 90):
    return await analytics.expected_stockout_date(item_code, days)


# Friendly default for /mcp without trailing slash (some clients miss the
# slash). Redirect to the canonical endpoint.
@app.get("/mcp")
async def mcp_root_redirect():
    return JSONResponse(
        {"error": "MCP endpoint is at /mcp/. Add the trailing slash."}
    )
