"""
One-shot extractor that copies the SQLite store from procurement_app/rip.db
into CSV files inside render_demo/data/.

Tables extracted:
    rip_month, rip_program, rip_combo, rip_match, rip_upc_map
    invoice_header, invoice_line
    risk_calc_alias

Run on a machine that has the procurement_app folder:

    cd render_demo/extract
    python extract_rip.py

Output CSVs land in ../data/. Commit them and push — Render's seed step
will load them on the next deploy.
"""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = (HERE / ".." / "data").resolve()
OUT.mkdir(parents=True, exist_ok=True)

# Locate rip.db — sits next to procurement_app/app.py.
RIP_DB = Path(os.environ.get(
    "RIP_DB_PATH",
    HERE / ".." / ".." / "procurement_app" / "rip.db"
)).resolve()

TABLES = [
    "rip_month",
    "rip_program",
    "rip_combo",
    "rip_match",
    "rip_upc_map",
    "invoice_header",
    "invoice_line",
    "risk_calc_alias",
]


def main() -> None:
    if not RIP_DB.exists():
        print(f"ERROR: rip.db not found at {RIP_DB}", file=sys.stderr)
        print("Set RIP_DB_PATH env var to the right path, or run from "
              "render_demo/extract with procurement_app/ next to render_demo/.")
        sys.exit(1)
    print(f"Reading {RIP_DB}")
    con = sqlite3.connect(RIP_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    for table in TABLES:
        try:
            cur.execute(f"SELECT * FROM {table}")
        except sqlite3.OperationalError as e:
            print(f"  {table}: skipped ({e})")
            continue
        rows = cur.fetchall()
        if not rows:
            print(f"  {table}: 0 rows")
            continue
        cols = list(rows[0].keys())
        path = OUT / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([r[c] for c in cols])
        print(f"  {table}: {len(rows)} rows -> {path.name}")

    con.close()
    print(f"\nDone. Output in {OUT}")
    print("Commit data/*.csv and push — Render will load them on next deploy.")
    print("To force the loader to re-run on an existing deploy:")
    print("  Render Shell tab -> FORCE_RIP_RELOAD=true python -m seed.seed")


if __name__ == "__main__":
    main()
