# Installation & Deploy Manual — CELR Procurement

Step-by-step guide to running this app locally and shipping it to Render
as a public URL. **Zero prior knowledge of React or Render assumed.**
Follow the Parts in order; each step tells you what success looks like
before you move on.

**Repo:** https://github.com/hellou2xai/celr_1st

**What you'll end up with:**
- A web app at `https://<your-service>.onrender.com/`
- Magic-link sign-in (allowlisted email addresses only)
- 23 procurement pages (Dashboard, Open POs, Sales Analytics, Risk Calc, etc.)
- Right-click drill-down modal on any UPC
- An MCP server at `/mcp/` for Claude clients

---

## Where you'll be working

Every Part below is tagged with the location it happens in:

| Tag | Where | What you use |
|---|---|---|
| `[LOCAL]` | Your laptop | Terminal / PowerShell, code editor, browser |
| `[RENDER]` | <https://dashboard.render.com> | Web browser, Render UI |
| `[BROWSER]` | Your deployed URL | Just a web browser |

```
                        LOCAL                          RENDER
                   (your laptop)                  (cloud, via browser)
                   ─────────────                  ───────────────────
Install tools           ✓
Clone repo              ✓
Extract catalog CSVs    ✓   (needs WINEZONE LAN)
Run locally             ✓   (Postgres in Docker + Node + Python)
git push                ✓
Click "Apply Blueprint"                                  ✓
Wait for build + seed                                    ✓
Get public URL                                           ✓
Sign in, use the app    (browser)                       (browser)
```

You will **never SSH** into the Render server. Anything Render-side
happens in their dashboard. The "Shell" tab on Render is a browser-based
terminal, not real SSH.

---

## Table of contents

- [Part 0 — Tools you need installed](#part-0--tools-you-need-installed--local)
- [Part 1 — Clone the repo](#part-1--clone-the-repo--local)
- [Part 2 — Extract the catalog from WINEZONE](#part-2--extract-the-catalog-from-winezone--local)
- [Part 3 — Run locally (optional but recommended)](#part-3--run-locally-optional-but-recommended--local)
- [Part 4 — Push your changes](#part-4--push-your-changes--local)
- [Part 5 — Deploy on Render](#part-5--deploy-on-render--render)
- [Part 6 — Sign in and verify](#part-6--sign-in-and-verify--browser)
- [Part 7 — Connect Claude (MCP)](#part-7--connect-claude-mcp--local)
- [Part 8 — Turning on real email (magic-link via Resend)](#part-8--turning-on-real-email-magic-link-via-resend--render)
- [Part 9 — Things that commonly go wrong](#part-9--things-that-commonly-go-wrong)
- [Quick-reference card](#quick-reference-card)

---

## Part 0 — Tools you need installed  `[LOCAL]`

> **You are on your laptop.** Install everything in this Part once.

### 0.1 Python 3.12

```powershell
python --version
```

You want `Python 3.12.x` or newer. If not, download from
<https://www.python.org/downloads/>. **On Windows install, check
"Add python.exe to PATH."** On Mac: `brew install python@3.12`.

### 0.2 Node.js 20+

```powershell
node --version
npm --version
```

You want Node ≥ 20. If not: download from <https://nodejs.org/>
(install the LTS version). On Mac: `brew install node@20`.

### 0.3 Git

```powershell
git --version
```

If not installed:
- **Windows:** <https://git-scm.com/download/win>
- **Mac:** `brew install git`

### 0.4 ODBC Driver for SQL Server (Windows, only for Part 2)

Only needed if you're going to run the catalog extractor against the
real WINEZONE SQL Server. Check:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

If the list is empty: install ODBC Driver 18 from
<https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server>.

### 0.5 (Optional) Docker Desktop

For local Postgres in Part 3. <https://www.docker.com/products/docker-desktop/>

### 0.6 Accounts

- **GitHub** — <https://github.com/signup>
- **Render** — <https://render.com/register>

---

## Part 1 — Clone the repo  `[LOCAL]`

```powershell
cd "C:\where\you\keep\projects"
git clone https://github.com/hellou2xai/celr_1st.git
cd celr_1st
```

Confirm the structure:

```powershell
ls
```

You should see:

```
backend/   frontend/   data/   db/   extract/   seed/   scripts/
README.md  DEPLOY.md   CURRENT_APP_AUDIT.md
render.yaml  requirements.txt  .env.example  .gitignore
LICENSE  Dockerfile
```

Install Python and Node dependencies:

```powershell
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Each takes 1–3 minutes. You can run both in parallel terminals.

---

## Part 2 — Extract the catalog from WINEZONE  `[LOCAL]`

> **You must be on the WINEZONE LAN** (or VPN'd in) — the extractor
> talks to the SQL Server at 192.168.1.99.

The Render demo needs eight CSVs of catalog data. They are not in the
repo by default. Generate them:

```powershell
cd extract

$env:SQL_SERVER   = "192.168.1.99"
$env:SQL_DATABASE = "WINEZONE"
$env:SQL_AUTH     = "sql"
$env:SQL_USER     = "CELR"
$env:SQL_PASSWORD = "Pow1966"
$env:SQL_DRIVER   = "SQL Server"

python extract_real_catalog.py
```

Expected output:

```
Connecting to 192.168.1.99/WINEZONE as CELR
  departments.csv: 24
  categories.csv: 412
  suppliers.csv: 168
  items.csv: 29841
  item_velocity.csv: 8273
  month_seasonality.csv: 12
  dow_seasonality.csv: 7
  hour_distribution.csv: 24
  baseline.csv: avg_txns_per_day=412
```

(Numbers are illustrative.) The script runs in 30–60 seconds. It only
pulls **catalog and aggregate velocity** — no transaction or customer
PII leaves the WINEZONE database.

Quick check that the items CSV looks real:

```powershell
cd ..\data
ls
```

You should see eight CSVs plus `README.md`. Open `items.csv` and confirm
familiar SKUs (MALIBU, CORONA, etc.) and sensible costs/prices.

---

## Part 3 — Run locally (optional but recommended)  `[LOCAL]`

> Skip to Part 4 if you're confident. Doing this catches bugs in 3
> minutes instead of after a 25-minute Render deploy.

### 3.1 Start a local Postgres in Docker

```powershell
docker run -d --name celr-pg -p 5432:5432 `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=celr_procurement `
  postgres:16
```

Confirm:

```powershell
docker ps
```

### 3.2 Configure env

```powershell
copy .env.example .env
```

Open `.env` and confirm:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/celr_procurement
SYNTH_DAY_TXN_CAP=50
AUTH_EMAIL_PROVIDER=none
AUTH_ALLOWED_EMAILS=hello@u2xai.com
```

(`SYNTH_DAY_TXN_CAP=50` keeps the local seed under 90 seconds. Production
runs with no cap.)

Load env into your shell:

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/celr_procurement"
$env:SYNTH_DAY_TXN_CAP = "50"
$env:AUTH_EMAIL_PROVIDER = "none"
$env:AUTH_ALLOWED_EMAILS = "hello@u2xai.com"
```

### 3.3 Seed the database

```powershell
python -m seed.seed
```

Expected tail:

```
[14:23:01] render_demo seed v1.0.0 (seed=20260518, years=4)
[14:23:02]   department: 24 rows
[14:23:02]   item: 29,841 rows
...
[14:24:30] Seed complete in 88s
```

### 3.4 Start the backend (FastAPI)

```powershell
uvicorn backend.main:app --reload --port 8000
```

Expected:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal running.

### 3.5 Start the frontend (Vite) in a second terminal

```powershell
cd celr_1st\frontend
npm run dev
```

Expected:

```
  VITE v5.x.x  ready in 412 ms
  ➜  Local:   http://localhost:5173/
```

Open http://localhost:5173/.

### 3.6 Sign in

You'll be redirected to `/login`. Enter `hello@u2xai.com`. Because
`AUTH_EMAIL_PROVIDER=none` in dev, the magic-link token comes back in
the response — it'll auto-fill the second step. Click **Sign in**.

You should land on the Dashboard with five KPI tiles populated.

**Try the drill-down**: navigate to **Items**, right-click any UPC →
modal opens with the item summary, open POs, and transaction history.

### 3.7 Stop everything

Ctrl-C in both terminals. Stop the local Postgres:

```powershell
docker stop celr-pg && docker rm celr-pg
```

---

## Part 4 — Push your changes  `[LOCAL]`

Render auto-deploys from `main`. If you extracted new catalog CSVs or
made code changes, push them:

```powershell
git add .
git status              # eyeball what's staged
git commit -m "refresh catalog snapshot"
git push origin main
```

If `git push` asks for credentials, use your GitHub username and a
**personal access token** — not your account password. Generate one at
<https://github.com/settings/tokens?type=beta> with `repo` write access
to `celr_1st`.

---

## Part 5 — Deploy on Render  `[RENDER]`

> **Switch to your browser**, at <https://dashboard.render.com>. No
> terminal needed for this whole Part.

### 5.1 Connect Render to your GitHub (once)

1. Avatar (top right) → **Account settings** → **GitHub** → **Connect**.
2. Authorize Render and grant access to `celr_1st` (or all repos).

### 5.2 Create the Blueprint

1. **New + → Blueprint**.
2. Pick `hellou2xai/celr_1st`.
3. Render reads `render.yaml` and shows the plan:
   - Web service: `celr-procurement` (Python Starter, Oregon)
   - Database: `celr-procurement-db` (Postgres 16 Starter, Oregon)
4. Click **Apply**.

### 5.3 Watch the first build

Click into the `celr-procurement` web service → **Logs** tab. The first
deploy runs four phases:

1. **Provision Postgres** (1–2 min). Status reaches "Available."
2. **Build** — Node 20 download → `npm ci` → Vite build → `pip install`. (~5 min)
3. **preDeployCommand** — `python -m seed.seed`. **This is the slow part — 10 to 20 minutes** for 4 years of synthetic transactions. You'll see lines like:

   ```
   [14:35:12] Phase 2: transactions
   [14:35:12]   span: 2022-05-18 → 2026-05-18 (1461 days)
   [14:48:55]   through 2026-05-18: 612,450 txns, 1,857,201 entries
   [14:48:55] Seed complete in 822s
   ```

4. **Start** — `uvicorn backend.main:app …`. Health check `/api/health`
   should return `ok` within 30s.

When the deploy status goes green, your URL is live.

### 5.4 Find your public URL

Top of the web service page, e.g. `https://celr-procurement-abc1.onrender.com`.
You can rename the service in **Settings → Name** to get a cleaner URL.

---

## Part 6 — Sign in and verify  `[BROWSER]`

1. Open `https://<your-service>.onrender.com/`.
2. You'll bounce to `/login`.
3. Enter `hello@u2xai.com` and click **Send magic link**.
4. Since `AUTH_EMAIL_PROVIDER=none` is the default, the **dev token**
   comes back in the response and auto-fills the form. Click **Sign in**.

You're on the Dashboard. Verification checklist:

| Check | Expected |
|---|---|
| Dashboard loads | 5 KPI tiles with real numbers, not zero |
| Sidebar collapses | Click the chevron at bottom-left |
| **Right-click any UPC** | Drill-down modal opens with item details |
| **Open POs** page | Filters work, supplier rollup populated, CSV export downloads |
| **Stockouts** page | KPI tiles + by-risk + by-supplier rollups, xlsx export downloads |
| **Sales Analytics** | 4 tabs render: Top sellers, Weekly YoY, Movers, Transactions |
| **PO Spend** | 4 tabs render with charts |
| **Item Analytics** | Click any top item → 4 charts appear |
| **AI Advisor** | Daily briefing card + Q&A returns rule-based answers |
| `/api/health` | Returns `ok` in browser |
| `/mcp/` | Returns the MCP server greeting (or "trailing slash" error if no `/`) |

If anything's blank or errors, go to [Part 9](#part-9--things-that-commonly-go-wrong).

---

## Part 7 — Connect Claude (MCP)  `[LOCAL]`

MCP URL: `https://<your-service>.onrender.com/mcp/` (trailing slash matters).

### Claude Code (CLI)

```bash
claude mcp add celr-procurement --transport http https://<your-service>.onrender.com/mcp/
```

Restart Claude Code. In a new session, `/mcp` shows `celr-procurement`
with ~45 tools.

### Claude Desktop

`Settings → Developer → Edit Config` and add:

```json
{
  "mcpServers": {
    "celr-procurement": {
      "url": "https://<your-service>.onrender.com/mcp/"
    }
  }
}
```

Restart Claude Desktop. The wrench icon in a new chat lists the tools.

### Try it

> "Using celr-procurement, show me top 5 items to reorder this week."

Claude calls `reorder_recommendations` and renders the result.

---

## Part 8 — Turning on real email (magic-link via Resend)  `[RENDER]`

Default install uses `AUTH_EMAIL_PROVIDER=none` — magic-link tokens come
back in the API response (dev mode). To send actual emails:

1. Create a Resend account at <https://resend.com>.
2. Verify a sending domain (or use their `onboarding@resend.dev` for testing).
3. Generate an API key: <https://resend.com/api-keys>.
4. In Render → `celr-procurement` → **Environment** → add / update:

   ```
   AUTH_EMAIL_PROVIDER=resend
   RESEND_API_KEY=re_********
   RESEND_FROM=CELR <noreply@yourdomain.com>
   PUBLIC_URL=https://<your-service>.onrender.com
   ```

5. Click **Save changes**. Render re-deploys automatically (~2 min, no
   re-seed because `seed_marker` is already set).

After redeploy, `/login` actually sends an email containing the token
and a one-click sign-in link.

Locking down the allowlist to your team:

```
AUTH_ALLOWED_EMAILS=hello@u2xai.com,bob@u2xai.com
# OR
AUTH_ALLOWED_DOMAINS=u2xai.com
```

---

## Part 9 — Things that commonly go wrong

Each fix is tagged with where to apply it.

### "The extractor hangs forever"  `[LOCAL]`

You're not on the same network as the WINEZONE SQL Server. VPN in or run
the extractor on a machine inside the network.

### "pyodbc.OperationalError: ('08001', ...)"  `[LOCAL]`

ODBC driver name doesn't match.

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

Set `$env:SQL_DRIVER` to whatever exact string the list shows. If you
see only `ODBC Driver 18 for SQL Server`, also add:

```powershell
$env:SQL_DRIVER = "ODBC Driver 18 for SQL Server"
```

### "npm install fails with permission errors"  `[LOCAL]`

On Windows, run PowerShell as administrator once for the install. On
Mac/Linux make sure `~/.npm` is owned by you, not root.

### "Render build fails: 'node: command not found'"  `[RENDER]`

The build command downloads Node from nodejs.org. If that fails, edit
`render.yaml` to use a different URL or pin Node via Render's
buildpacks. For a fix-in-place: in Render → **Settings → Build &
Deploy → Build Command**, hardcode a working Node CDN URL.

### "preDeployCommand timed out"  `[RENDER]`

Default Render timeout is generous (90 min) but if you hit it:

1. **Environment** → set `SYNTH_DAY_TXN_CAP=300`.
2. Trigger manual deploy. Lower cap finishes in 3–5 min.
3. To unlock full data later, remove `SYNTH_DAY_TXN_CAP`, then
   open Render Shell:

   ```bash
   FORCE_RESEED=true python -m seed.seed
   ```

### "Login screen loops back to itself"  `[BROWSER]` / `[RENDER]`

Cookies aren't being set. Causes:

- **Local dev**: Vite is on `localhost:5173` and FastAPI is on
  `localhost:8000`. The proxy in `vite.config.ts` handles this. If you
  bypassed it and hit `:8000` directly from `:5173`, cookies won't
  cross. Use the Vite URL.
- **Production**: confirm `RENDER=true` is set in env vars
  (it's in `render.yaml` by default). This switches the session cookie
  to `Secure`.

### "Dashboard tiles are all zero"  `[RENDER]`

Seed didn't run. Open Render Shell tab:

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transaction_entry;"
```

If zero:

```bash
FORCE_RESEED=true python -m seed.seed
```

### "Sales Analytics tab is blank"  `[BROWSER]`

The seed needs >3 years of history for the YoY comparison to populate.
Confirm `SYNTH_YEARS` is at least `4` in Render env vars.

### "MCP client can't connect"  `[LOCAL]`

1. URL has trailing slash: `/mcp/` not `/mcp`.
2. Hit `https://<url>/api/health` in browser first — wakes the worker.
3. Your client needs Streamable HTTP transport (Claude Code ≥ 1.0,
   recent Claude Desktop).

### "I want to start completely over"  `[RENDER]`

Delete the Blueprint in Render dashboard. Both the web service and
the Postgres go with it. Then **New + → Blueprint** with the same repo.

### "I want to redeploy after fixing something"  `[LOCAL → RENDER]`

`git push` from your laptop. Render auto-deploys. `seed_marker` makes
the seed phase skip (~2 min total redeploy).

---

## Quick-reference card

```
[LOCAL]   CLONE       git clone https://github.com/hellou2xai/celr_1st.git
[LOCAL]   PYDEPS      pip install -r requirements.txt
[LOCAL]   FEDEPS      cd frontend && npm install
[LOCAL]   EXTRACT     cd extract && python extract_real_catalog.py
[LOCAL]   LOCAL PG    docker run -d --name celr-pg -p 5432:5432 \
                        -e POSTGRES_PASSWORD=postgres \
                        -e POSTGRES_DB=celr_procurement postgres:16
[LOCAL]   SEED        python -m seed.seed
[LOCAL]   BACKEND     uvicorn backend.main:app --reload
[LOCAL]   FRONTEND    cd frontend && npm run dev   (in another terminal)
[LOCAL]   COMMIT      git add . && git commit -m "..." && git push
[RENDER]  DEPLOY      New + → Blueprint → celr_1st → Apply
[RENDER]  RESEED      Shell tab → FORCE_RESEED=true python -m seed.seed
[RENDER]  LOGS        Web service → Logs tab
[RENDER]  SQL         Shell tab → psql $DATABASE_URL
[BROWSER] WAKE        https://<url>/api/health
[LOCAL]   CLAUDE      claude mcp add celr-procurement --transport http <url>/mcp/
```

**Live URLs once deployed:**

```
LOGIN        https://<service>.onrender.com/login
DASHBOARD    https://<service>.onrender.com/
MCP          https://<service>.onrender.com/mcp/
HEALTH       https://<service>.onrender.com/api/health
```

**Env vars that matter:**

| Name | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres DSN. Wired by render.yaml. | (auto) |
| `SYNTH_YEARS` | Years of synthetic history. | 4 |
| `SYNTH_SEED` | RNG seed for reproducibility. | 20260518 |
| `SYNTH_DAY_TXN_CAP` | Cap per-day txn count (0=real volume). | 0 |
| `FORCE_RESEED` | Set `true` to wipe + re-seed. | unset |
| `AUTH_ALLOWED_EMAILS` | Comma-separated allowlist. | hello@u2xai.com |
| `AUTH_ALLOWED_DOMAINS` | Comma-separated domain allowlist. | (empty) |
| `AUTH_EMAIL_PROVIDER` | `none` (dev) or `resend`. | none |
| `AUTH_SECRET` | HMAC secret. Auto-generated per env. | random |
| `RESEND_API_KEY` | When `AUTH_EMAIL_PROVIDER=resend`. | unset |
| `PUBLIC_URL` | Used in magic-link emails. | unset |

That's the entire installation manual. If you hit something not covered
here, grab the Render log lines or the browser console error and ask the
maintainer. Welcome to CELR.
