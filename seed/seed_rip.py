"""
Loads RIP / invoice / risk-calc-alias data into Postgres.

Two paths:
    1. CSV path — if data/rip_*.csv etc. exist (produced by
       extract/extract_rip.py against the real SQLite store), COPY them in.
    2. Synthetic fallback — generate ~3 months of plausible programs
       inline so the demo isn't empty even before anyone extracts.

Idempotent: skips loading if rip_program already has rows, unless the
FORCE_RIP_RELOAD env var is "true".

Creates the supporting Postgres tables on every call (CREATE IF NOT EXISTS).
"""
from __future__ import annotations

import csv
import io
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FORCE = os.environ.get("FORCE_RIP_RELOAD", "").lower() == "true"


SCHEMA = """
CREATE TABLE IF NOT EXISTS rip_month (
    month        TEXT PRIMARY KEY,
    label        TEXT,
    source_file  TEXT,
    loaded_at    TIMESTAMP,
    rip_rows     INTEGER NOT NULL DEFAULT 0,
    combo_rows   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rip_program (
    id            INTEGER PRIMARY KEY,
    month         TEXT NOT NULL,
    abg_sku       TEXT,
    rip_code      TEXT,
    upc           TEXT NOT NULL,
    brand         TEXT,
    valid_from    DATE,
    valid_to      DATE,
    description   TEXT,
    tier1_unit    TEXT,
    tier1_qty     NUMERIC(18,3),
    tier1_rebate  NUMERIC(18,4),
    tier2_unit    TEXT,
    tier2_qty     NUMERIC(18,3),
    tier2_rebate  NUMERIC(18,4),
    comments      TEXT
);
CREATE INDEX IF NOT EXISTS idx_rip_program_upc_month ON rip_program(upc, month);
CREATE INDEX IF NOT EXISTS idx_rip_program_month ON rip_program(month);

CREATE TABLE IF NOT EXISTS rip_combo (
    id               INTEGER PRIMARY KEY,
    month            TEXT NOT NULL,
    abg_sku          TEXT,
    combo_code       TEXT,
    upc              TEXT NOT NULL,
    brand            TEXT,
    valid_from       DATE,
    valid_to         DATE,
    description      TEXT,
    combo_pack_price NUMERIC(18,4),
    qty_items        TEXT,
    qty_value        NUMERIC(18,3),
    qty_unit         TEXT,
    fline_price      NUMERIC(18,4),
    combo_price      NUMERIC(18,4),
    total_savings    NUMERIC(18,4),
    comments         TEXT
);
CREATE INDEX IF NOT EXISTS idx_rip_combo_upc_month ON rip_combo(upc, month);

CREATE TABLE IF NOT EXISTS rip_match (
    id                   INTEGER PRIMARY KEY,
    po_number            TEXT,
    po_entry_id          INTEGER,
    item_id              INTEGER,
    upc                  TEXT NOT NULL,
    description          TEXT,
    supplier             TEXT,
    po_date              DATE,
    month                TEXT NOT NULL,
    rip_program_id       INTEGER,
    rip_code             TEXT,
    tier_qualified       INTEGER,
    qty_ordered          NUMERIC(18,3),
    qty_unit             TEXT,
    case_pack            INTEGER,
    rebate_amount        NUMERIC(18,4),
    expected_paid_after  DATE,
    expected_paid_before DATE,
    status               TEXT,
    received_amount      NUMERIC(18,4),
    received_on          DATE,
    notes                TEXT,
    created_at           TEXT,
    updated_at           TEXT
);
CREATE INDEX IF NOT EXISTS idx_rip_match_status ON rip_match(status);
CREATE INDEX IF NOT EXISTS idx_rip_match_month ON rip_match(month);

CREATE TABLE IF NOT EXISTS rip_upc_map (
    rip_upc          TEXT NOT NULL,
    item_id          INTEGER NOT NULL,
    item_code        TEXT NOT NULL,
    match_method     TEXT NOT NULL,
    match_score      NUMERIC(18,4),
    rip_description  TEXT,
    item_description TEXT,
    has_po_history   INTEGER DEFAULT 0,
    PRIMARY KEY (rip_upc, item_id)
);
CREATE INDEX IF NOT EXISTS idx_upc_map_rip_upc ON rip_upc_map(rip_upc);

CREATE TABLE IF NOT EXISTS invoice_header (
    id            INTEGER PRIMARY KEY,
    supplier      TEXT,
    invoice_number TEXT,
    invoice_date  TEXT,
    totals_gross  NUMERIC(18,4),
    totals_net    NUMERIC(18,4),
    source_file   TEXT,
    line_count    INTEGER,
    mapped        INTEGER,
    unmapped      INTEGER,
    warnings      TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS invoice_line (
    id             INTEGER PRIMARY KEY,
    invoice_id     INTEGER NOT NULL,
    line_number    INTEGER,
    supplier_code  TEXT,
    rms_lookup     TEXT,
    description    TEXT,
    quantity       NUMERIC(18,3),
    unit_price     NUMERIC(18,4),
    line_total     NUMERIC(18,4),
    match_status   TEXT,
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_invoice_line_invoice ON invoice_line(invoice_id);

CREATE TABLE IF NOT EXISTS risk_calc_alias (
    id              INTEGER PRIMARY KEY,
    alias_text      TEXT NOT NULL,
    rms_lookup_code TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_risk_alias_text ON risk_calc_alias(alias_text);
"""


# --------------------------------------------------------------------------- #
# CSV loader (preferred when extract_rip.py output is in data/)
# --------------------------------------------------------------------------- #

LOAD_SPEC = [
    # (table, csv_filename, columns to import in CSV order)
    ("rip_month",       "rip_month.csv",       ["month","label","source_file","loaded_at","rip_rows","combo_rows"]),
    ("rip_program",     "rip_program.csv",     ["id","month","abg_sku","rip_code","upc","brand","valid_from","valid_to","description","tier1_unit","tier1_qty","tier1_rebate","tier2_unit","tier2_qty","tier2_rebate","comments"]),
    ("rip_combo",       "rip_combo.csv",       ["id","month","abg_sku","combo_code","upc","brand","valid_from","valid_to","description","combo_pack_price","qty_items","qty_value","qty_unit","fline_price","combo_price","total_savings","comments"]),
    ("rip_match",       "rip_match.csv",       ["id","po_number","po_entry_id","item_id","upc","description","supplier","po_date","month","rip_program_id","rip_code","tier_qualified","qty_ordered","qty_unit","case_pack","rebate_amount","expected_paid_after","expected_paid_before","status","received_amount","received_on","notes","created_at","updated_at"]),
    ("rip_upc_map",     "rip_upc_map.csv",     ["rip_upc","item_id","item_code","match_method","match_score","rip_description","item_description","has_po_history"]),
    ("invoice_header",  "invoice_header.csv",  ["id","supplier","invoice_number","invoice_date","totals_gross","totals_net","source_file","line_count","mapped","unmapped","warnings","created_at"]),
    ("invoice_line",    "invoice_line.csv",    ["id","invoice_id","line_number","supplier_code","rms_lookup","description","quantity","unit_price","line_total","match_status","notes"]),
    ("risk_calc_alias", "risk_calc_alias.csv", ["id","alias_text","rms_lookup_code","description","created_at"]),
]


def _copy_csv(cn: psycopg.Connection, table: str, csv_path: Path,
              columns: list[str]) -> int:
    """Stream a CSV into a table. We match by column name from the CSV
    header, so column order can differ between CSV and our SELECT."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return 0
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return 0
        # Filter to columns we know about in the right order.
        col_idx = {name: i for i, name in enumerate(header)}
        wanted = [c for c in columns if c in col_idx]
        if not wanted:
            return 0
        buf = io.StringIO()
        w = csv.writer(buf)
        n = 0
        for row in reader:
            out = []
            for c in wanted:
                v = row[col_idx[c]] if col_idx[c] < len(row) else ""
                out.append(v)
            w.writerow(out)
            n += 1
        buf.seek(0)
        cols_sql = ", ".join(wanted)
        with cn.cursor() as cur, cur.copy(
            f"COPY {table} ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '')"
        ) as copy:
            copy.write(buf.getvalue())
    cn.commit()
    return n


def _table_row_count(cn: psycopg.Connection, table: str) -> int:
    with cn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def _truncate_all(cn: psycopg.Connection) -> None:
    with cn.cursor() as cur:
        for table, *_ in LOAD_SPEC:
            cur.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE")
    cn.commit()


def _ensure_schema(cn: psycopg.Connection) -> None:
    with cn.cursor() as cur:
        cur.execute(SCHEMA)
    cn.commit()


def _csv_path(name: str) -> Path:
    return DATA / name


def _has_real_data() -> bool:
    return _csv_path("rip_program.csv").exists()


def ensure(cn: psycopg.Connection, seed: int = 20260518, log=print) -> str:
    """Apply schema and load RIP / invoice / alias data.

    Returns one of: 'real', 'synthetic', 'skipped'.
    """
    _ensure_schema(cn)

    have_rows = _table_row_count(cn, "rip_program") > 0
    if have_rows and not FORCE:
        return "skipped"
    if have_rows and FORCE:
        log("  FORCE_RIP_RELOAD=true — truncating existing rows")
        _truncate_all(cn)

    if _has_real_data():
        total = 0
        for table, fname, cols in LOAD_SPEC:
            n = _copy_csv(cn, table, _csv_path(fname), cols)
            if n:
                log(f"  {table}: {n:,} rows (real)")
                total += n
        # Reset SERIAL sequences so future inserts don't collide with
        # imported ids.
        with cn.cursor() as cur:
            for table, *_ in LOAD_SPEC:
                cur.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                                  COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                                  false)
                """)
        cn.commit()
        return "real"

    # ----------------------- Synthetic fallback -----------------------
    log("  no rip_program.csv found — generating synthetic data")
    _synthesize(cn, seed=seed, log=log)
    return "synthetic"


# --------------------------------------------------------------------------- #
# Synthetic fallback (~3 months, ~300 programs, ~50 combos, ~60 matches)
# --------------------------------------------------------------------------- #

def _month_label(d: date) -> str:
    return d.strftime("%B %Y")


def _start_of(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _prev_month(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _synthesize(cn: psycopg.Connection, seed: int, log) -> None:
    rng = random.Random(seed + 7)
    cur = cn.cursor()

    today = date.today()
    months = [_prev_month(today), _start_of(today), _next_month(today)]

    cur.execute("""
        SELECT i.id, i.item_lookup_code, i.description, i.cost,
               COALESCE(s.supplier_name, '')
        FROM item i
        LEFT JOIN supplier s ON i.supplier_id = s.id
        WHERE i.inactive = 0 AND i.cost > 0
        ORDER BY i.quantity DESC NULLS LAST
        LIMIT 800
    """)
    pool = cur.fetchall()
    if not pool:
        return

    prog_id = 1
    combo_id = 1
    match_id = 1
    for m_date in months:
        month_str = m_date.strftime("%Y-%m")
        cur.execute("""
            INSERT INTO rip_month (month, label, source_file, loaded_at, rip_rows, combo_rows)
            VALUES (%s, %s, %s, NOW(), 0, 0)
            ON CONFLICT (month) DO NOTHING
        """, (month_str, _month_label(m_date), f"synthetic_{month_str}.xlsx"))

        chosen = rng.sample(pool, min(100, len(pool)))
        prog_rows = []
        for item_id, upc, desc, cost, supplier in chosen:
            t1_qty = float(rng.choice([3, 5, 6, 10, 12]))
            t1_reb = round(float(cost) * rng.uniform(0.03, 0.10), 4)
            if rng.random() < 0.4:
                t2_qty = t1_qty * rng.choice([2, 3, 5])
                t2_reb = round(t1_reb * rng.uniform(1.2, 1.8), 4)
                t2_u = "Case"
            else:
                t2_qty = None; t2_reb = None; t2_u = None
            prog_rows.append((
                prog_id, month_str, f"ABG-{rng.randint(100000,999999)}",
                f"R{rng.randint(10000,99999)}", upc,
                desc.split()[0] if desc else "",
                m_date, _next_month(m_date) - timedelta(days=1),
                desc, "Case", t1_qty, t1_reb, t2_u, t2_qty, t2_reb,
                rng.choice(["Tier rebate", "Quarterly program", ""])
            ))
            prog_id += 1
        cur.executemany("""
            INSERT INTO rip_program
              (id, month, abg_sku, rip_code, upc, brand, valid_from, valid_to,
               description, tier1_unit, tier1_qty, tier1_rebate,
               tier2_unit, tier2_qty, tier2_rebate, comments)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, prog_rows)

        combo_rows = []
        for i, (item_id, upc, desc, cost, supplier) in enumerate(rng.sample(chosen, min(15, len(chosen)))):
            qty = float(rng.choice([3, 5, 10, 12]))
            fline = float(cost) * qty
            cprice = round(fline * rng.uniform(0.85, 0.95), 4)
            combo_rows.append((
                combo_id, month_str, f"ABG-{rng.randint(100000,999999)}",
                f"COMBO-{m_date.strftime('%Y%m')}-{i+1:03d}", upc,
                desc.split()[0] if desc else "",
                m_date, _next_month(m_date) - timedelta(days=1),
                desc, round(fline/qty, 4),
                str(int(qty)) + " C", qty, "Case",
                round(fline, 4), cprice, round(fline - cprice, 4), ""
            ))
            combo_id += 1
        cur.executemany("""
            INSERT INTO rip_combo
              (id, month, abg_sku, combo_code, upc, brand, valid_from, valid_to,
               description, combo_pack_price, qty_items, qty_value, qty_unit,
               fline_price, combo_price, total_savings, comments)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, combo_rows)

        cur.execute("""
            UPDATE rip_month
            SET rip_rows = %s, combo_rows = %s
            WHERE month = %s
        """, (len(prog_rows), len(combo_rows), month_str))

    # Match history against the oldest month
    prior_month_str = months[0].strftime("%Y-%m")
    cur.execute("""
        SELECT id, upc, description, rip_code, tier1_qty, tier1_rebate,
               tier2_qty, tier2_rebate
        FROM rip_program WHERE month = %s ORDER BY random() LIMIT 60
    """, (prior_month_str,))
    prior_progs = cur.fetchall()
    cur.execute("""
        SELECT po.po_number, po.date_created, COALESCE(s.supplier_name,'')
        FROM purchase_order po
        LEFT JOIN supplier s ON po.supplier_id = s.id
        WHERE po.date_created >= NOW() - INTERVAL '90 days'
        ORDER BY po.date_created DESC LIMIT 200
    """)
    pos = cur.fetchall() or [(None, datetime.now(), "ALLIED")]

    match_rows = []
    for prog in prior_progs:
        po_number, po_dt, supplier = rng.choice(pos)
        po_d = po_dt.date() if isinstance(po_dt, datetime) else po_dt
        t1q, t1r, t2q, t2r = prog[4], prog[5], prog[6], prog[7]
        if t2q and rng.random() < 0.3:
            tier, qty, reb = 2, float(t2q), float(t2r or 0)
        else:
            tier, qty, reb = 1, float(t1q or 0), float(t1r or 0)
        total = round(reb * qty, 4)
        r = rng.random()
        if r < 0.30:
            status = "RECEIVED"
            received_on = po_d + timedelta(days=rng.randint(30, 80))
            received_amount = total * rng.uniform(0.95, 1.0)
        elif r < 0.65:
            status, received_on, received_amount = "EXPECTED", None, None
        elif r < 0.85:
            status, received_on, received_amount = "OVERDUE", None, None
        elif r < 0.95:
            status, received_on, received_amount = "DISPUTED", None, None
        else:
            status, received_on, received_amount = "DECLINED", None, 0

        cur.execute("SELECT id FROM item WHERE item_lookup_code = %s LIMIT 1", (prog[1],))
        row = cur.fetchone()
        item_id = row[0] if row else None

        match_rows.append((
            match_id, po_number, None, item_id, prog[1], prog[2],
            supplier, po_d, prior_month_str, prog[0], prog[3],
            tier, qty, "Case", 12, total,
            po_d + timedelta(days=30), po_d + timedelta(days=90),
            status, received_amount, received_on,
            "Auto-matched at receipt" if status == "RECEIVED" else "",
            str(datetime.now()), str(datetime.now()),
        ))
        match_id += 1

    cur.executemany("""
        INSERT INTO rip_match (
            id, po_number, po_entry_id, item_id, upc, description, supplier,
            po_date, month, rip_program_id, rip_code, tier_qualified,
            qty_ordered, qty_unit, case_pack, rebate_amount,
            expected_paid_after, expected_paid_before, status,
            received_amount, received_on, notes, created_at, updated_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, match_rows)
    cn.commit()
