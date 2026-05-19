# Deploy Manual — WINEZONE Procurement Demo

A complete, step-by-step guide to taking this folder from your laptop to a
live public URL on Render. **Zero prior knowledge of Render or Postgres
assumed.** Follow the parts in order; each step tells you what success
looks like before you move on.

**Total time:** ~45 minutes (10 minutes of clicking + a 20-minute
unattended seed running on Render + 10 minutes of testing).

**What you will end up with:**
- A public URL like `https://winezone-demo.onrender.com/` with a landing
  page documenting the demo.
- A dashboard at `/dashboard` with live charts.
- An MCP endpoint at `/mcp/` you can plug into Claude Code or Claude
  Desktop.

---

## Where you will be working

This deploy moves between three places. Every Part below is tagged with
the location where you'll spend that step:

| Tag | Where | What you use |
|---|---|---|
| `[LOCAL]` | Your laptop | Terminal / PowerShell, code editor, web browser |
| `[RENDER]` | <https://dashboard.render.com> | Web browser, Render UI |
| `[BROWSER]` | Your deployed URL | Just a web browser |

**Quick mental model:**

```
                                LOCAL                       RENDER
                          (your laptop)               (cloud, via browser)
                          ─────────────               ───────────────────
Install tools                  ✓
Extract catalog CSVs           ✓   (needs WINEZONE LAN)
Optional local test            ✓   (Docker Postgres)
Push to GitHub                 ✓
Click "Apply Blueprint"                                     ✓
Wait for seed (15-20 min)                                   ✓
Get public URL                                              ✓
Wire up Claude Code/Desktop    ✓
Open dashboard in browser      ✓
Troubleshoot via Logs/Shell                                 ✓
```

You will **never SSH** into the Render server. Anything you need to do
on Render's side happens through buttons in their web dashboard. The
"Shell" mentioned in Part 8 is a browser-based terminal inside the Render
UI, not a real SSH session.

---

## Table of contents

- [Part 0 — Tools you need installed](#part-0--tools-you-need-installed--local)
- [Part 1 — Get the code on your laptop](#part-1--get-the-code-on-your-laptop--local)
- [Part 2 — Extract the catalog from WINEZONE](#part-2--extract-the-catalog-from-winezone--local)
- [Part 3 — Sanity-check the demo locally (optional but recommended)](#part-3--sanity-check-the-demo-locally-optional-but-recommended--local)
- [Part 4 — Push to GitHub](#part-4--push-to-github--local)
- [Part 5 — Deploy on Render](#part-5--deploy-on-render--render)
- [Part 6 — Connect Claude](#part-6--connect-claude--local)
- [Part 7 — Verify everything works](#part-7--verify-everything-works--browser--local)
- [Part 8 — Things that commonly go wrong](#part-8--things-that-commonly-go-wrong)
- [Quick-reference card](#quick-reference-card)

---

## Part 0 — Tools you need installed  `[LOCAL]`

> **You are on your laptop.** Everything in this Part is a one-time
> install on your machine. No Render involvement yet.

Before you start, install these on your laptop. Skip anything you already
have.

### 0.1 Python 3.12

Check first:

```powershell
python --version
```

You want `Python 3.12.x` or newer. If not:

- **Windows:** download from <https://www.python.org/downloads/>. During
  install, **check the box that says "Add python.exe to PATH"**.
- **Mac:** `brew install python@3.12`

### 0.2 Git

```powershell
git --version
```

You want any recent version. If not:

- **Windows:** <https://git-scm.com/download/win>
- **Mac:** `brew install git`

### 0.3 ODBC Driver for SQL Server (Windows only)

The catalog extractor in Part 2 needs this. Check whether you already have
it:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

If you see `'SQL Server'` or `'ODBC Driver 17 for SQL Server'` in the
output, you're good. If the command errors with "no module pyodbc," that's
fine — we'll install pyodbc later. If the list is empty:

1. Download the ODBC Driver 18 installer from Microsoft:
   <https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server>
2. Install with default options.
3. Re-run the check above to confirm.

### 0.4 A GitHub account

If you don't have one: <https://github.com/signup>. Make a note of your
username.

### 0.5 A Render account

Sign up at <https://render.com/register>. Use the same email as GitHub if
you can — it makes Part 5 simpler.

### 0.6 (Optional) Docker Desktop

Only needed if you want to test locally in Part 3. Skip if you're going
straight to Render.

- <https://www.docker.com/products/docker-desktop/>

---

## Part 1 — Get the code on your laptop  `[LOCAL]`

> **Still on your laptop.** This Part just gets the code and Python
> dependencies in place. Nothing here touches WINEZONE or Render.

You should already have the `render_demo/` folder at
`C:\CELR AI Analysis\render_demo\`. If you don't, ask the person who set up
this project for access.

### 1.1 Open a terminal in the folder

**Windows PowerShell:**

```powershell
cd "C:\CELR AI Analysis\render_demo"
```

**Mac/Linux:**

```bash
cd "/path/to/CELR AI Analysis/render_demo"
```

### 1.2 Confirm the structure

```powershell
ls
```

You should see at least these entries:

```
app  data  db  extract  scripts  seed
.env.example  .gitignore  Dockerfile  README.md  render.yaml  requirements.txt
```

If anything's missing, stop and re-check the folder path. The deploy will
not work without the full tree.

### 1.3 Install Python dependencies

```powershell
pip install -r requirements.txt
```

Expected output: a lot of "Successfully installed ..." lines, ending with
something like `Successfully installed fastapi-... asyncpg-... ...`. The
process takes 1–3 minutes.

If you see `pip: command not found`, use `python -m pip` instead:

```powershell
python -m pip install -r requirements.txt
```

### 1.4 Install pyodbc separately (Windows only, for Part 2)

```powershell
pip install pyodbc
```

---

## Part 2 — Extract the catalog from WINEZONE  `[LOCAL]`

> **On your laptop, on the WINEZONE network.** This is the only step
> that talks to the real SQL Server. The extractor runs locally; nothing
> gets sent to Render. If you're remote, VPN in first — see warning
> below.

The deploy package needs three things from the real database before it can
be seeded:

1. The item catalog (codes, descriptions, costs, prices).
2. Department / category / supplier reference lists.
3. Aggregated velocity numbers (averages per item — no row-level data).

The extractor script produces CSV files. **It does not export any customer
or transaction data.**

> **Important:** Your laptop must be on the same network as the WINEZONE
> SQL Server (192.168.1.99) for this step. If you're remote, VPN in first.
> If `ping 192.168.1.99` doesn't get a response, the extractor will fail
> with a connection timeout.

### 2.1 Run the extractor

```powershell
cd "C:\CELR AI Analysis\render_demo\extract"
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

Done. Output in C:\CELR AI Analysis\render_demo\data
Commit data/*.csv to the repo, then 'git push' to deploy on Render.
```

(Numbers will vary — those are illustrative.)

**The script takes 30–60 seconds.** If it sits for more than two minutes
without output, hit Ctrl-C and see the [troubleshooting section](#part-8--things-that-commonly-go-wrong).

### 2.2 Sanity-check the CSVs

```powershell
cd "C:\CELR AI Analysis\render_demo\data"
ls
```

You should see all eight CSVs plus a `README.md`. Open `items.csv` in
Excel or Notepad and confirm:

- Header row exists: `id, item_lookup_code, description, ...`
- You see real WINEZONE items (e.g., MALIBU RUM, CORONA, etc.)
- Cost and price columns have sensible numbers.

If any CSV is empty (0 bytes) or has only a header, the SQL extraction
silently returned no rows — stop and check that the database is reachable
and that you used a SQL login with SELECT permissions.

---

## Part 3 — Sanity-check the demo locally (optional but recommended)  `[LOCAL]`

> **All local.** Spin up Postgres in Docker on your laptop, seed it with
> a small slice, and confirm the app boots. Nothing here touches Render.
> The whole Part takes ~3 minutes and saves you a 20-minute Render round
> trip if there's a bug.

Skip to [Part 4](#part-4--push-to-github--local) if you're confident and
short on time. Doing this part catches problems before they cost you a
slow Render deploy.

### 3.1 Start a local Postgres in Docker

```powershell
docker run -d --name wz-pg -p 5432:5432 `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=winezone_demo `
  postgres:16
```

(On Mac/Linux replace the trailing backticks with backslashes for line
continuation.)

Confirm it's running:

```powershell
docker ps
```

You should see `postgres:16` with status `Up x seconds`.

### 3.2 Configure local env

```powershell
cd "C:\CELR AI Analysis\render_demo"
copy .env.example .env
```

Open `.env` in a text editor and make sure these two lines are set:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/winezone_demo
SYNTH_DAY_TXN_CAP=50
```

Setting the cap to 50 keeps the local seed fast (≈1 minute instead of 15).

### 3.3 Load env vars into your shell

**PowerShell:**

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/winezone_demo"
$env:SYNTH_DAY_TXN_CAP = "50"
```

**Mac/Linux:**

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/winezone_demo"
export SYNTH_DAY_TXN_CAP=50
```

### 3.4 Run the seed

```powershell
python -m seed.seed
```

Expected output (truncated):

```
[14:23:01] render_demo seed v1.0.0 (seed=20260518, years=4)
[14:23:01] Applying schema
[14:23:02] Phase 1: catalog & reference data
[14:23:02]   department: 24 rows
[14:23:02]   category: 412 rows
...
[14:23:45]   through 2024-04-21: 18,250 txns, 54,127 entries (44s, 414 txns/s)
...
[14:24:30] Seed complete in 88s
```

If the seed finishes without an error, you're good.

### 3.5 Start the app

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expected output:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

Open <http://localhost:8000/> in your browser. You should see the landing
page. Then click "Open the dashboard →" — charts should populate within a
few seconds.

Press Ctrl-C in the terminal to stop the server.

### 3.6 Stop the local Postgres (optional)

```powershell
docker stop wz-pg && docker rm wz-pg
```

---

## Part 4 — Push to GitHub  `[LOCAL]`

> **Last local step before Render.** You will use your browser briefly
> to create a GitHub repo, then git from your terminal to push. After
> this Part you can close the terminal and move entirely to the browser.

Render deploys by pulling from a GitHub (or GitLab/Bitbucket) repository.

### 4.1 Create a new private repository on GitHub

1. Go to <https://github.com/new>.
2. **Repository name:** `winezone-demo` (or whatever you like).
3. **Visibility:** Private. (Catalog CSVs are public-safe but the
   repository's not interesting to anyone else.)
4. Leave "Add a README" / "Add .gitignore" UNCHECKED. We have those
   already.
5. Click **Create repository**.

GitHub now shows a "Quick setup" page with a URL like
`https://github.com/your-username/winezone-demo.git`. Copy it.

### 4.2 Initialize git locally and commit

```powershell
cd "C:\CELR AI Analysis\render_demo"
git init
git add .
git commit -m "winezone-demo initial commit"
```

Expected output:

```
[main (root-commit) abc1234] winezone-demo initial commit
 22 files changed, 4218 insertions(+)
```

The exact file count may differ. What matters is that the commit succeeds.

### 4.3 Push to GitHub

```powershell
git branch -M main
git remote add origin https://github.com/your-username/winezone-demo.git
git push -u origin main
```

(Replace the URL with the one GitHub gave you.)

If git asks for credentials, use your GitHub username and a **personal
access token** (not your password). Generate one at
<https://github.com/settings/tokens> with `repo` scope.

After the push, refresh your GitHub repo page — you should see all the
files.

---

## Part 5 — Deploy on Render  `[RENDER]`

> **Switch to your browser, at <https://dashboard.render.com>.** No
> terminal needed for this whole Part. You'll click through Render's UI
> and watch logs in the browser while the seed runs.

This is the magic step. Render's Blueprint feature reads `render.yaml`
from your repo and creates everything for you.

### 5.1 Connect Render to your GitHub

1. Go to <https://dashboard.render.com>.
2. Top right, click your avatar → **Account settings** → **GitHub** →
   **Connect**.
3. Authorize Render and grant access to the `winezone-demo` repo (or all
   repos, your choice).

### 5.2 Create the Blueprint

1. From the dashboard, click **New +** (top right) → **Blueprint**.
2. Select the `winezone-demo` repository.
3. Render scans the repo and finds `render_demo/render.yaml`. It will
   show a preview:
   - **Web Service:** `winezone-demo` (Starter, Python, Oregon)
   - **PostgreSQL:** `winezone-demo-db` (Starter, version 16, Oregon)
4. Give the blueprint a name like `winezone-demo`.
5. Click **Apply**.

### 5.3 Watch the deploy

Render now does, in order:

1. **Provisions Postgres** (1–2 minutes). Status: "Available".
2. **Builds the web service** — clones your repo, runs
   `pip install -r requirements.txt`. ~3–5 minutes.
3. **Runs `preDeployCommand`** which is `python -m seed.seed`. **This is
   the slow part — 10 to 20 minutes.** Click the **Logs** tab on the web
   service to watch real-time output.

You should see log lines like:

```
[14:23:01] render_demo seed v1.0.0 (seed=20260518, years=4)
[14:23:01] Applying schema
[14:23:02] Phase 1: catalog & reference data
[14:23:02]   department: 24 rows
...
[14:35:12]   through 2026-05-18: 612,450 txns, 1,857,201 entries (722s, 848 txns/s)
[14:35:12]   done. 612,450 txns and 1,857,201 entries in 722s
[14:35:18] Phase 3: backfill aggregates
[14:35:22] Phase 3b: purchase orders
[14:35:39] Phase 3c: supporting events
[14:35:50] Phase 4: analyze tables
[14:35:55] Seed complete in 774s
```

4. **Starts the web service** with `uvicorn ...`. Should be live within
   30 seconds of seed completion.
5. **Health check** — Render hits `/healthz`, which queries the DB. When
   it returns `ok`, the deploy goes green.

### 5.4 Find your public URL

In the web service page, look at the top: **`https://winezone-demo-XXXX.onrender.com`**
(the suffix is random; you can customize it under **Settings → Name**).

Click the URL. You should see the landing page.

> **First load may take 30 seconds** while uvicorn warms up. After that
> it's fast.

---

## Part 6 — Connect Claude  `[LOCAL]`

> **Back on your laptop.** You'll configure your local Claude Code CLI
> or Claude Desktop app to talk to the Render-hosted MCP endpoint. The
> Render service itself is fully deployed and idle, just waiting for
> traffic.

The MCP endpoint is at `https://<your-service>.onrender.com/mcp/` — note
the trailing slash, it's required.

### 6.1 Claude Code (CLI)

From your terminal:

```bash
claude mcp add winezone-demo --transport http https://your-service.onrender.com/mcp/
```

Then restart Claude Code. In a new session, type `/mcp` — you should see
`winezone-demo` listed with ~45 tools.

### 6.2 Claude Desktop

1. Open Claude Desktop → **Settings → Developer → Edit Config**.
2. Add (or merge) into the `mcpServers` object:

   ```json
   {
     "mcpServers": {
       "winezone-demo": {
         "url": "https://your-service.onrender.com/mcp/"
       }
     }
   }
   ```

3. Save and **restart Claude Desktop**.
4. New chat → click the 🔧 icon in the message box — you should see the
   `winezone-demo` tools listed.

### 6.3 Try it

In Claude, ask something like:

> "Using winezone-demo, show me the top 5 fast movers in the last 30 days."

Claude should call the `fast_movers` tool and return a table.

---

## Part 7 — Verify everything works  `[BROWSER + LOCAL]`

> **Mostly a web browser exercise.** The first six checks are URLs you
> open in a browser. The last one (Claude) uses your local Claude Code
> or Claude Desktop that you wired up in Part 6.

Run through this checklist before declaring victory:

| Check | Expected |
|---|---|
| `https://<url>/` loads | Landing page with title "WINEZONE demo" |
| `https://<url>/dashboard` loads | Dashboard with populated KPI tiles (not all zero) |
| Sales trend chart appears | A wavy line spanning ~365 days |
| Hourly heatmap appears | A 7×24 grid with red intensity in evening hours |
| Fast movers table populated | 10 rows of real-looking SKUs |
| `https://<url>/healthz` | Returns `ok` |
| `https://<url>/api/executive` | Returns JSON with non-zero KPIs |
| Claude tool call works | Asking Claude returns data, not an error |

If any item fails, jump to the next section.

---

## Part 8 — Things that commonly go wrong

Each fix is tagged with where you have to be to apply it.

### "The extractor hangs forever"  `[LOCAL]`

You're not on the same network as the SQL Server. VPN in or run the
extractor from a machine inside the network.

### "pyodbc.OperationalError: ('08001', ...)"  `[LOCAL]`

ODBC driver mismatch. Try:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

If you see `ODBC Driver 18 for SQL Server` instead of plain `SQL Server`,
set the right driver before running:

```powershell
$env:SQL_DRIVER = "ODBC Driver 18 for SQL Server"
$env:SQL_EXTRA = "TrustServerCertificate=yes;"   # ODBC 18 default-rejects self-signed
python extract_real_catalog.py
```

If that still fails, install ODBC 17 (older, friendlier defaults) from
the Microsoft download page.

### "git push fails with 403 or asks for password"  `[LOCAL]`

Use a personal access token, not your account password. Make one at
<https://github.com/settings/tokens?type=beta> with `repo` write
permission and use it in place of the password.

### "Render build fails with `Could not find a version that satisfies ...`"  `[RENDER]`

The Python version on Render doesn't match what one of the packages
expects. Open `render.yaml` and confirm `PYTHON_VERSION` is `3.12.7`. If
Render still picks the wrong version, set the env var manually under
**Environment** in the Render dashboard.

### "preDeployCommand timed out"  `[RENDER]`

The default Render timeout is generous (90 minutes) but if you hit it:

1. In Render → web service → **Environment**, set
   `SYNTH_DAY_TXN_CAP = 300`. Save.
2. Trigger a manual deploy (button top right). The lower cap finishes in
   under 5 minutes.

You can crank it back up by removing the env var and forcing a re-seed
later via Render's **Shell** tab:

```bash
FORCE_RESEED=true python -m seed.seed
```

### "The dashboard loads but every chart is empty"  `[RENDER]`

The seed didn't actually populate the DB. Open Render's Shell tab and
check:

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM transaction_entry;"
```

If it's zero, force a re-seed:

```bash
FORCE_RESEED=true python -m seed.seed
```

### "Health check fails / service won't go live"  `[RENDER]`

Click **Logs**. Look for the last red line. Common causes:

- "DATABASE_URL is not set" — the env var wasn't wired up. Open the web
  service → **Environment** → confirm `DATABASE_URL` is set
  `fromDatabase`. If not, set it manually pointing at your Postgres
  service's internal connection string.
- "Connection refused" — the Postgres service hasn't started yet. Wait
  60 seconds and Render will auto-retry the health check.

### "Claude says: 'Error: cannot connect to MCP server'"  `[LOCAL]`

Three things to check, in order:

1. URL has the trailing slash: `/mcp/` not `/mcp`.
2. The service is awake. Hit `https://<url>/healthz` in a browser first
   to wake the worker.
3. Your Claude client supports Streamable HTTP transport. This requires
   Claude Code ≥ 1.0 or Claude Desktop on a recent version.

### "I want to start completely over"  `[RENDER]`

In Render dashboard:

1. Delete the web service.
2. Delete the Postgres database.
3. Re-run **New + → Blueprint** with the same repo.

Or just delete the Blueprint (which deletes both at once).

### "I want to redeploy after fixing something"  `[LOCAL → RENDER]`

Just `git push` from your laptop — Render auto-deploys from main on its
own. The seed step will detect existing data via `seed_marker` and skip
itself, so redeploys are fast (under 2 minutes). Watch the new deploy
finish in the Render Logs tab.

---

## Quick-reference card

```
[LOCAL]   EXTRACT     cd render_demo/extract && python extract_real_catalog.py
[LOCAL]   COMMIT      git add . && git commit -m "..." && git push
[RENDER]  DEPLOY      Render dashboard → New + → Blueprint → repo → Apply
[BROWSER] WAKE UP     curl https://<url>/healthz   (or just open the URL)
[RENDER]  RESEED      Render Shell tab → FORCE_RESEED=true python -m seed.seed
[RENDER]  LOGS        Render web service → Logs tab
[RENDER]  SQL         Render Shell tab → psql $DATABASE_URL
[LOCAL]   LOCAL DEV   docker run postgres + python -m seed.seed + uvicorn app.main:app
[LOCAL]   CLAUDE      claude mcp add winezone-demo --transport http <url>/mcp/
```

**The URLs once deployed:**

```
LANDING     https://<service>.onrender.com/
DASHBOARD   https://<service>.onrender.com/dashboard
MCP         https://<service>.onrender.com/mcp/
HEALTH      https://<service>.onrender.com/healthz
JSON API    https://<service>.onrender.com/api/executive  (and others)
```

**The environment variables that matter:**

| Name | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres DSN. Wired automatically by render.yaml. | (Render auto) |
| `SYNTH_YEARS` | Years of history to generate. | 4 |
| `SYNTH_SEED` | RNG seed for reproducibility. | 20260518 |
| `SYNTH_DAY_TXN_CAP` | Cap per-day txn count (0 = real volume). | 0 |
| `FORCE_RESEED` | Set to `true` to wipe and re-seed. | unset |
| `PUBLIC_URL` | Override what the landing page shows for the MCP URL. | (auto-detected) |

That's it. If you got stuck somewhere not covered above, capture the
error message and the Render log, and ask whoever set this up. Welcome
to the team.
