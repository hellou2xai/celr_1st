# CELR Procurement — React + FastAPI + Postgres + MCP

A deployable React port of the WINEZONE/CELR procurement intelligence
app. Hosts on Render with a single web service that serves:

- **React SPA** (`frontend/`) — port of the original Flask `procurement_app/`
  with a sidebar, drill-down modal, sortable tables, filter forms.
- **JSON API** (`backend/api/`) — feeds the SPA. FastAPI.
- **MCP server** (`backend/mcp_server.py`) — 45 analytics tools at
  `/mcp/` for Claude / Cursor / any MCP client.

Data is 4 years of synthetic transactions over the real WINEZONE item
catalog. Customers / cashiers / POs / RIP programs are synthesized.

---

## Status of the React port

This is an **in-progress** port. The foundation (layout, sidebar,
drill-down, auth, shared components) is complete and four pages are
built end-to-end:

- ✅ Dashboard
- ✅ Open POs (Cancel/Reduce)
- ✅ Return to Vendor
- ✅ Stockouts

The remaining 19 pages are stubbed with a "Page under construction"
notice and their planned scope. See `CURRENT_APP_AUDIT.md` for the full
inventory of features still to port.

---

## Layout

```
render_demo/
├── render.yaml             Render blueprint (web + Postgres Starter)
├── requirements.txt        Python deps
├── DEPLOY.md               Step-by-step deploy manual
├── CURRENT_APP_AUDIT.md    Page-by-page audit of procurement_app/
├── backend/                FastAPI + analytics + MCP
│   ├── main.py             App entry, lifespan, serves React build
│   ├── auth.py             Magic-link sign-in
│   ├── api/pages.py        JSON endpoints powering the SPA
│   ├── analytics.py        Postgres dialect port of 45 MCP tools
│   ├── mcp_server.py       MCP server (Streamable HTTP)
│   └── db.py               asyncpg pool
├── frontend/               React SPA (Vite + TS + Tailwind + shadcn/ui)
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx                 23-route router
│   │   ├── components/             Layout, Sidebar, DataTable, DrillDown, …
│   │   ├── pages/                  Dashboard, OpenPOs, RTV, Stockouts, Placeholder
│   │   ├── api/                    Typed fetch client
│   │   └── lib/                    Money/num/pct/risk formatting helpers
├── db/schema.sql           Postgres schema
├── seed/seed.py            Synthetic data generator
├── extract/                One-time SQL Server CSV extractor
└── data/                   Catalog CSVs (committed; transactions synthesized)
```

---

## Local development

```bash
# 1. Postgres in Docker
docker run -d --name celr-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=celr_procurement postgres:16

# 2. Backend env + seed
cd render_demo
cp .env.example .env  # then edit DATABASE_URL if needed
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/celr_procurement
export SYNTH_DAY_TXN_CAP=50   # ~1 minute seed for fast local iteration
pip install -r requirements.txt
python -m seed.seed

# 3. Backend (FastAPI)
uvicorn backend.main:app --reload --port 8000

# 4. Frontend (Vite, in another terminal)
cd frontend
npm install
npm run dev    # opens http://localhost:5173 with proxy to :8000
```

Open http://localhost:5173. Sign in with `hello@u2xai.com` — in dev mode
(no Resend key) the token comes back in the JSON response of `/auth/request`
so you can paste it on the next step without a real email.

---

## Deploy on Render

See [`DEPLOY.md`](DEPLOY.md) for the step-by-step manual.

TL;DR:

1. Push this folder as the root of your GitHub repo.
2. Render dashboard → **New + → Blueprint** → pick the repo.
3. First deploy takes ~25–30 minutes (Node + Python build + 4-year seed).
4. Visit `https://<service>.onrender.com/`, sign in.

---

## Connecting Claude / MCP clients

MCP URL: `https://<service>.onrender.com/mcp/`

```bash
claude mcp add celr-procurement --transport http https://<service>.onrender.com/mcp/
```

---

## Privacy

Item catalog (descriptions, costs, prices, suppliers) is real and
public-safe per the data owner. Everything else — transactions,
customers, cashiers, POs, RIP programs, drops, time cards — is
synthesized at deploy time with `@example.com` email domains forced so
synthetic accounts cannot collide with real ones.

See `CURRENT_APP_AUDIT.md` for the full coverage matrix.
