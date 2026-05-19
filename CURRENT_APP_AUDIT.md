# Current App Audit — what `procurement_app/` actually contains

I built `render_demo/` against the WINEZONE MCP server output, not the
actual production Flask app in `procurement_app/`. The two are different
systems with different scope. **The Flask app is roughly 20× the scope of
what `render_demo/` covers today.**

This document is a page-by-page audit of every feature in the real app
that I would need to port for "exact same functionality" on Render.

---

## Headline numbers

|  | `procurement_app/` (live) | `render_demo/` (built so far) |
|---|---|---|
| Backend lines of Python | ~14,000 across 20 files | ~2,500 across 6 files |
| Templates | 33 | 2 (landing + dashboard) |
| Routes / pages | ~70 | 1 page + 11 REST + 1 MCP |
| Charts | 30+ (Chart.js) | 6 (Chart.js) |
| Data tables on screen | ~120 | 3 |
| Excel exports | 8 endpoints | 0 |
| Drill-down modals | Yes (right-click any UPC, stack of N levels) | No |
| Filter forms | ~25 multi-parameter forms | 1 |
| Local SQLite store | Yes (`rip.db`, RIP programs + match history) | No |
| Invoice PDF parsing | Yes (multi-supplier) | No |
| AI advisor with ask/explain | Yes | No |

What `render_demo/` does *better*: an MCP server. The Flask app has no
MCP. So neither system is a strict superset of the other; merging them
needs explicit decisions.

---

## Sidebar / navigation structure

`base.html` defines a six-section sidebar — none of which exists in
`render_demo/`:

```
📊 Dashboard

▼ Buying
  🧮 Pre-PO Risk Calc
  📦 Purchase Order Suggestions
  🎯 RIP Order Suggestions
  💰 Buy Optimizer
  🎁 RIP Programs

▼ Review
  📋 Open POs · Cancel/Reduce
  ↩️ Return to Vendor
  📦 Excess Stock
  ⚠️ Stockouts

▼ Analytics
  📊 Item Analytics
  📈 Sales Analytics       (tabbed, 8 sub-views)
  💵 PO Spend Analysis      (tabbed, 5 sub-views)
  💰 Cost Analysis
  🏷️ Pricing Analytics

▼ Browse
  🛒 Items
  🧾 Purchase Orders → PO detail
  📄 Invoices → Invoice detail

▼ AI
  🧠 AI Advisor (ask/explain)

▼ Admin
  💾 Data files
  ⚙️ Config
```

Collapsible sidebar with persistence in localStorage. Active state per
endpoint.

---

## Page-by-page inventory

For each page: **tiles**, **filters/inputs**, **tables/charts**, **drill-downs**, **exports**.

### 1. Dashboard `/`  (131-line template, ~50 lines of backend)
- **Tiles (5):** Open POs · Open PO Value · Suggested Cancels/Reduces · RTV Candidates (Net) · Recent Stockouts. Each linkable to its review page.
- **Tables (2):** Open PO risk breakdown (clickable rows → Open POs filtered by risk) · Top suppliers with cancel/reduce opportunity.
- **Filters:** none — it's a snapshot.

### 2. Risk Calc `/risk-calc`  (601-line template, ~270 lines backend)
- **Inputs:** big textarea where a buyer pastes "UPC + qty" lines (one per row); toggles for show-transactions, prefer-parent, fuzzy match, with-volume, qty-in-cases, prefer-purchased; history months slider.
- **Summary cards:** total lines, qty, value, count of unresolved.
- **Tables:** risk summary by tier · line-level breakdown with per-line transaction expansion · alias search + save (POST /api/risk-calc/alias).
- **Drill-down:** inline txn list per line; alt-match suggestions.
- **Export:** POST `/risk-calc/export.xlsx` (formatted xlsx with risk colour-coding).
- **Companion page:** `/risk-calc/aliases` to manage saved UPC↔ItemCode aliases.

### 3. Purchase Order Suggestions `/order-suggestions`  (637-line template, ~450 lines backend)
- **Filters (20+):** weeks of supply target, velocity months window, supplier (multi-select with autocomplete), department, category, min velocity, min PO count, PO recency, max projected weeks, free-text search, include zero-velocity toggle, valid-supplier-only, sort key, limit, **use_rip** toggle, **show_rip_only** toggle, RIP-now/next month selectors, min net, action filter (BUY/WAIT/SKIP), wait days.
- **KPI cards:** lines, suggested buy value, est rebate from RIP, est savings, etc.
- **Main table:** UPC · Description · Supplier · OnHand · OpenPO · AvgMo · Cover · Suggested Qty · Unit Cost · Line Total · Action · RIP indicator. Sortable, sticky header, drill-down icon per row.
- **Export:** `/order-suggestions/export.xlsx`.

### 4. RIP Order Suggestions `/rip-order-suggestions`  (320-line template, ~170 lines backend)
- A focused variant of the above: only items with an active RIP program for the chosen month, with tier-qualified flags and rebate-per-unit math.
- **Filters:** month, supplier, dept, cat, min units, tier filter.
- **Cards** + **table** with RIP rebate column. Each row links to `/rip-item/<id>` detail.

### 5. Buy Optimizer `/optimizer`  (149-line template, ~60 lines backend)
- "Basket" workflow: drop items into a basket, optimizer finds the cheapest mix of vendors / combos to hit your target qty using current pricing + RIP combos.
- **Cards:** basket total, savings, RIP rebate.
- **Basket table** with vendor / combo path per item.

### 6. RIP Programs `/rip/programs`  (242-line template, ~270 lines backend)
- **Filters:** month, supplier, brand, tier filter, free-text.
- **Cards:** programs in window, total potential rebate, combos count, etc.
- **Table:** every active RIP program for the chosen month with tier1/2 qty + rebate columns.
- **Companion pages:** `/rip` (home), `/rip/optimize` (combo optimizer), `/rip-item/<int:item_id>` (per-item RIP detail, 334-line partial with claim status management), `/rip/rescan` POST, `/rip/claim/<id>` POST.

### 7. Open POs / Cancel-Reduce `/open-pos`  (131-line template, ~65 lines backend)
- **Filters:** days, supplier, product search w/ datalist, risk tier, action (CANCEL/REDUCE/KEEP/NEEDS_ACTION), valid supplier toggle, limit.
- **Cards (5):** open line count, total value, recoverable value, etc.
- **By-supplier rollup table** + **line detail table**. Each row has CANCEL/REDUCE action suggestions inline.
- **Export:** `/open-pos/export.csv`.

### 8. Return to Vendor `/rtv`  (~150 lines)
- Filters: in-window only toggle, supplier.
- Table of RTV-eligible items with vendor return windows.
- Export: `/rtv/export.csv`.

### 9. Excess Stock `/excess-stock`  (477-line template, ~95 lines backend)
- **Filters (9):** velocity months, min MoS, min OH value, risk tier, aging bucket, supplier, dept, cat, sort, include-dead, limit.
- **Cards:** total excess capital, items, suppliers affected, etc.
- **Tables (6):** by risk-tier, definitions reference, top suppliers, by department, by category, **aging × risk grid** (drill matrix).
- **Export:** `/excess-stock/export.xlsx`.

### 10. Stockouts `/stockouts`  (422-line template, ~70 lines backend)
- **Filters:** similar set to excess stock + open-PO coverage flag.
- **Cards:** stockout items, lost-sales estimate, etc.
- **Tables (7):** main list, risk distribution, action breakdown, open-PO coverage, by supplier, by dept, aging duration buckets, **aging × risk grid**.
- **Export:** `/stockouts/export.xlsx`.

### 11. Item Analytics `/analytics/item`  (820-line template, ~100 lines backend)
- Two modes: **single-item drill** and **compare-multiple-items**.
- **Filters:** item search w/ autocomplete, hidden item_id, dept, cat, multi-add compare items, months, granularity (week/month/qtr), top_n, show-cumulative checkbox, scope (item|dept|cat|all).
- **Single-item view:** 6 KPI cards · 4 charts (revenue per bucket, cumulative units sales-vs-purchases, historical purchase price, historical sale price vs regular retail).
- **Compare view:** comparison KPI cards · comparison table · units-over-time multi-line chart · total-units + total-revenue bar charts.
- **"Top items"** table at bottom when no specific item picked.

### 12. Sales Analytics `/sales-analysis`  (1392-line template, ~600 lines backend) — **TABBED**
This is the biggest single page. Eight independent tabs, each with its
own filter form and tables:
1. **Top sellers + by-department** — current-period table + biggest gainers/decliners + dept rollup.
2. **Multi-year totals** — year-by-year totals + top sellers across years.
3. **Weekly YoY** — 4 KPI cards, weekly line chart, totals bar chart, YoY change table, N-week × M-year grid, "apples-to-apples" same-weeks comparison. Excel export.
4. **Movement classification** — 6 risk cards (healthy / slowing / growing / dying etc.) + movement table.
5. **Seasonality** — year × month grid + month-of-year seasonal index.
6. **Hierarchy** — dept/cat/supplier hierarchy rollup.
7. **Transactions browser** — paginated raw transactions with filters (scope, dates, dept/cat/supplier/item). Excel export.
8. **ABC / Pareto** — Pareto-ranked items with A/B/C banding.

### 13. PO Spend Analysis `/analytics/po-spend`  (578-line template, ~250 lines backend) — **TABBED**
Five tabs (chart-heavy):
1. **Overview** — spend over time, status mix donut, top-10 suppliers bar.
2. **Suppliers** — Pareto chart + supplier table.
3. **Categories** — spend-by-dept chart, top categories chart, category table.
4. **Time** — spend trend, YoY chart.
5. **Items** — top-20 bar, top-50 table with click-to-load price drift in Variance subtab.
6. **Variance** — price-drift line chart + table for the selected item.

### 14. Cost Analysis `/analytics/cost`  (603-line template, ~100 lines backend)
- Filters: item picker (search), dept, cat, supplier, months, scope.
- 4 charts: unit cost over time line, % change first→last receipt bar, cost-vs-retail-vs-margin bar, cost range (min/avg/max) chart.
- Per-item summary table.
- "Cost movers" recent-shift table.

### 15. Pricing Analytics `/analytics/pricing`  (631-line template, ~120 lines backend)
- Filters similar to Cost. Plus promo flags.
- 4 charts: price over time (retail vs promo vs cost), current retail/sale/cost, promo activity %, max discount % observed.
- Per-item summary + "pricing concerns" table.

### 16. Items browse `/items`
- Filter: q (search), dept, cat, supplier, limit.
- Item table with on-hand, cost, price, last sold.

### 17. Purchase Orders browse `/pos`
- Filter: supplier, status, date range, search, limit.
- PO table.
- Export: `/pos/export.xlsx`.

### 18. PO Detail `/po/<po_number>`  (237-line template, ~30 lines backend)
- Header tiles (5+) — PO total, lines, ordered/received qty, status.
- Header details table.
- Line items table (sortable) — each item drillable via UPC.

### 19. Invoices `/invoices`  (~80 lines)
- Upload form (POST multipart `/invoices/upload`).
- Recent invoices list.

### 20. Invoice Detail `/invoices/<id>`
- Per-line match status, supplier-code → ItemLookupCode mapping.
- Delete POST endpoint.
- Excel export per invoice.

### 21. AI Advisor `/advisor`  (190-line template)
- Daily briefing card.
- Q&A form (POST `/api/ask`).
- "Explain this row" endpoint (POST `/api/explain`).
- Refresh endpoint `/advisor/refresh`.
- Requires `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` in env; gracefully degrades to "not configured" message.

### 22. Data files `/data`
- Lists CSVs/xlsx in the local `data/` folder for download.
- `/data/file/<name>` serves them.

### 23. Config `/config`
- Read-only display of supplier policies, thresholds, env settings.

---

## Cross-cutting infrastructure

### Item drill-down (`static/drilldown.js`, 453 lines)
Every page with `data-upc` cells gets right-click → modal drill-down:

- **Stack-based navigation:** up to N levels deep, Backspace pops, Escape closes.
- **Item view:** 8 KPI cards (OnHand, OpenPO, Avg/Mo, MoS, Days→stockout, Cost, Retail, Risk badge); summary line; recent transactions table with running quantity; open POs table for that item; alt-match suggestions (when description maps to multiple UPCs).
- **Transaction view:** opened by clicking a TXN# or ITL# reference. For sales, shows all line items in the basket; for ITL batches, shows items that moved together within ±2s.
- **Each line in the transaction view is itself drillable** — pushes another item view onto the stack.
- Months slider, Reload button, Back/Close buttons. Endpoints: `/api/item?id=...&months=...` and `/api/transaction?ref=...`.

### Table sort (`static/table_sort.js`)
Click any `<th>` to sort. Inferred types (numeric, currency, date). Disabled by `<table class="no-sort">`.

### RIP modal (`templates/_rip_modal.html`, ~80 lines)
Separate modal pattern used on RIP order suggestions: click a row's
"details" link, server returns an HTML partial, modal loads it. Distinct
from the JS drill-down — server-rendered.

### Excel exports
Eight export endpoints. All use `openpyxl` server-side with styled
headers, currency formats, conditional row colouring.

### Risk classification (in `analysis.py` etc.)
Custom rules engine that bins items into Critical / High / Moderate /
Healthy / Excess / Dead based on velocity, on-hand, MoS, last-sale age,
open-PO coverage. Used everywhere — same risk badge appears in 15+ places.

### Local SQLite (`rip.db`)
Separate database for RIP programs, combos, UPC mapping, match history.
Schema in `rip_db.py`. Joins to SQL Server tables at query time by UPC.

---

## What's in `render_demo/` today

| Feature | Status |
|---|---|
| Marketing landing page | ✅ Built |
| Single dashboard with 6 charts + 3 tables | ✅ Built |
| 45 analytics tools as MCP | ✅ Built |
| 11 REST API endpoints | ✅ Built |
| 4 years of synthetic transaction data | ✅ Built |
| Real catalog (items, suppliers, etc.) | ✅ Built (via extractor) |
| Postgres schema with 16 tables | ✅ Built |
| Render blueprint with auto-seed | ✅ Built |
| MCP Streamable HTTP transport | ✅ Built |

| Real-app feature | Status in render_demo |
|---|---|
| Sidebar navigation + 23 distinct pages | ❌ Not started |
| Item drill-down modal (right-click anywhere) | ❌ Not started |
| Transaction drill-down with stack | ❌ Not started |
| Tabbed pages (Sales Analytics × 8, PO Spend × 5) | ❌ Not started |
| 25 filter forms with multi-select / autocomplete | ❌ Not started |
| Risk calculator (Pre-PO) | ❌ Not started |
| Order Suggestions with RIP integration | ❌ Not started |
| RIP Programs / Optimizer | ❌ Not started — needs separate SQLite + RIP ingestion |
| Open POs / RTV / Excess / Stockouts review pages | ❌ Not started |
| Invoice upload + PDF parsing | ❌ Not started |
| Excel exports (8 endpoints) | ❌ Not started |
| AI Advisor with ask/explain | ❌ Not started |
| Aging × risk grids | ❌ Not started |
| Table sort JS | ❌ Not started |
| Custom risk classification engine | ❌ Not started |

---

## Effort estimate (rough)

Grouping the work into deliverable slices. These are calendar estimates
assuming one engineer focused full-time, working from the existing Flask
code as the reference implementation.

| Slice | Pages / features | Estimate |
|---|---|---|
| **1. Foundation** | Switch render_demo from FastAPI to Flask (or keep FastAPI + port templates); port `base.html` sidebar + collapse JS; port table_sort.js; port the global stylesheet. | 1–2 days |
| **2. Drill-down infra** | Port `drilldown.js` + `/api/item` + `/api/transaction` endpoints. This unlocks ~half of the navigation feel of the real app. | 2 days |
| **3. Dashboard + Open POs + RTV + Stockouts + Excess** | Five review pages with filters, tiles, tables, exports. | 3–5 days |
| **4. Sales Analytics (8 tabs)** | Biggest single page. | 3–4 days |
| **5. PO Spend Analysis (5 tabs) + Cost Analysis + Pricing Analytics + Item Analytics** | Four analytics pages, all chart-heavy. | 3–5 days |
| **6. Order Suggestions + Buy Optimizer + Risk Calc** | Three buying pages with complex math. | 3–4 days |
| **7. RIP module** | Separate SQLite, RIP ingestion, programs page, optimizer page, item RIP detail, RIP order suggestions, claim management. | 4–6 days |
| **8. Browse pages (Items, POs, PO Detail, Invoices)** | Mostly straightforward filtered tables. | 1–2 days |
| **9. Excel export pipeline** | 8 endpoints, styled output via openpyxl. | 1–2 days |
| **10. AI Advisor + Data Files + Config + small pages** | Including OpenAI/Anthropic key handling. | 1–2 days |
| **11. Seed pipeline updates** | Synthetic POs, RIP programs, invoices, audit log to feed all the new pages. | 2–3 days |
| **12. End-to-end QA on Render** | Verify every page renders, every export downloads, every drill-down works against synthetic data. | 2 days |

**Total: ~25–40 working days for the full port.** Realistically 5–8 weeks
with normal review cycles.

---

## Recommended decisions before continuing

The user (you) should pick one of these paths before I write more code.
The right choice depends on what the demo is for:

### Path A — Stay narrow (what render_demo is today)
Keep `render_demo/` as the *MCP demo* — a flat dashboard + 45 AI tools.
Don't try to mirror the Flask app. Document clearly that the full app is
the local Flask installation.

→ **0 additional days.** Deploy what's there.

### Path B — Port the most-used 5 pages
Dashboard, Open POs, Order Suggestions, Sales Analytics (the weekly-YoY
tab only), Risk Calc. Skip RIP, invoices, advisor. Skip drill-down — use
direct hyperlinks instead.

→ **~7–10 days.** Covers the "wow, this is a real procurement app" demo
without months of work.

### Path C — Port the whole thing
What you asked for. Full feature parity, all 23 pages, full drill-down,
exports, advisor.

→ **~5–8 weeks** as estimated above. Substantial commitment.

### Path D — Wrap, don't rewrite
Don't port at all. Host the existing Flask app directly on Render
(Postgres-as-SQLite swap or keep SQL Server connection alive over a
secure tunnel). Keep `render_demo/` as the public MCP-only demo, and
expose the Flask app only behind auth.

→ **~3–5 days** of infrastructure work (Postgres swap, auth, data
seeding). Fastest path to "every page works on Render."

---

## Open questions for the user

1. **Path A / B / C / D — which?** This is the gating decision.
2. **Anonymization scope.** The real app shows customer-level data on
   sales transactions (line 1132 of `sales_analysis.html`: per-txn rows
   with customer link). The demo synthesizes customers but the original
   Flask app expects real ones. If we port Sales Analytics' Transactions
   tab as-is on synthetic data, it works — but anything that links a
   customer name back to "their last 10 purchases" will need to handle
   the synthetic-customer mapping cleanly.
3. **RIP data.** RIP programs are loaded from monthly ABG distributor
   files (proprietary). For the demo we'd need to either ship a stub set
   or omit RIP entirely.
4. **AI Advisor.** Requires an LLM key. For a public demo do we want it
   on a shared key (cost), behind a "bring your own key" form, or
   omitted?
5. **Authentication.** The Flask app currently has no auth — it's
   intranet-only. A public Render URL with all this data exposed is a
   different threat model. At minimum we'd want basic auth or a
   shared-link gate.

Pick a path and I'll plan the next round of work against it.
