"""
FastAPI entrypoint for CELR Procurement.

Layout:
    /api/*       JSON endpoints feeding the React SPA pages
    /api/health  Liveness probe used by Render
    /mcp/*       Streamable HTTP MCP server (45 analytics tools)
    /auth/*      Magic-link sign-in
    /*           Serves frontend/dist (SPA fallback)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import analytics
from .api.pages import router as pages_router
from .api.pages2 import router as pages2_router
from .auth import router as auth_router
from .db import close_pool, get_pool
from .mcp_server import mcp_app

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = (ROOT / ".." / "frontend" / "dist").resolve()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="CELR Procurement",
    description="React SPA + JSON API + Streamable HTTP MCP server",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(pages2_router)
app.mount("/mcp", mcp_app)


@app.get("/api/health", response_class=PlainTextResponse)
async def healthz() -> str:
    try:
        await analytics.ping()
        return "ok"
    except Exception as e:  # pragma: no cover
        raise HTTPException(503, f"db unreachable: {e}")


@app.get("/mcp")
async def mcp_root_redirect():
    return JSONResponse({"error": "MCP endpoint is at /mcp/. Add the trailing slash."})


# Static React build + SPA fallback.
if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        if path.startswith(("api/", "mcp/", "auth/")):
            raise HTTPException(404, "Not found")
        candidate = FRONTEND_DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def dev_landing():
        return JSONResponse({
            "message": "Frontend build not found.",
            "hint": "Run `cd frontend && npm install && npm run build` first, "
                     "or use `npm run dev` in dev (Vite proxies /api back here).",
        })
