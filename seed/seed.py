"""
Bootstrap the WINEZONE demo Postgres database.

Two-phase boot:
    1. Catalog phase
        - Apply db/schema.sql
        - COPY data/{departments,categories,suppliers,items}.csv into Postgres
        - Insert static reference rows (tender types, reason codes)
        - Synthesize cashiers and customers (no real PII)
    2. Transaction phase
        - Generate SYNTH_YEARS years of synthetic transactions, tender entries,
          purchase orders, supporting events. Stream into Postgres via COPY.

Run from the project root:
    python -m seed.seed

The script is idempotent on the seed_marker table — re-running on an already
seeded DB exits in <1 s.

Env knobs (see .env.example):
    DATABASE_URL       — Postgres DSN. On Render, set via the Postgres add-on.
    SYNTH_SEED         — RNG seed for reproducibility (default 20260518).
    SYNTH_YEARS        — Years of history to generate (default 4).
    SYNTH_DAY_TXN_CAP  — If >0, cap daily txn count for fast local testing.
    FORCE_RESEED       — If "true", drop tables and re-seed.
"""
from __future__ import annotations

import csv
import io
import os
import sys
import time
import math
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import psycopg
from faker import Faker

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA_SQL = ROOT / "db" / "schema.sql"

SEED_VERSION = "1.0.0"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set", file=sys.stderr)
    sys.exit(2)

# Render injects DATABASE_URL with the postgres:// scheme; psycopg accepts
# postgresql:// preferentially. Normalize.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

SYNTH_SEED = int(os.environ.get("SYNTH_SEED", "20260518"))
SYNTH_YEARS = int(os.environ.get("SYNTH_YEARS", "4"))
SYNTH_DAY_TXN_CAP = int(os.environ.get("SYNTH_DAY_TXN_CAP", "0"))
FORCE_RESEED = os.environ.get("FORCE_RESEED", "").lower() == "true"

rng = np.random.default_rng(SYNTH_SEED)
random.seed(SYNTH_SEED)
faker = Faker("en_US")
Faker.seed(SYNTH_SEED)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def already_seeded(cn: psycopg.Connection) -> bool:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'seed_marker'
            )
        """)
        if not cur.fetchone()[0]:
            return False
        cur.execute("SELECT seeded_at, seed_version, txn_count FROM seed_marker")
        row = cur.fetchone()
        if row is None:
            return False
        log(f"  prior seed found: {row[1]} on {row[0]} with {row[2]:,} txns")
        return True


def apply_schema(cn: psycopg.Connection) -> None:
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with cn.cursor() as cur:
        cur.execute(sql)
    cn.commit()


def copy_csv(cn: psycopg.Connection, table: str, csv_path: Path,
             columns: list[str]) -> int:
    """Stream a CSV file into a table via COPY. Returns row count."""
    with csv_path.open("r", encoding="utf-8") as f:
        header = f.readline()  # discard header
        cols = ", ".join(columns)
        with cn.cursor() as cur, cur.copy(
            f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv)"
        ) as copy:
            n = 0
            chunk = f.read(1 << 20)
            while chunk:
                copy.write(chunk)
                n += chunk.count("\n")
                chunk = f.read(1 << 20)
    cn.commit()
    return n


# --------------------------------------------------------------------------- #
# Phase 1: catalog + reference data
# --------------------------------------------------------------------------- #

ITEM_COLS = [
    "id", "item_lookup_code", "description", "department_id", "category_id",
    "supplier_id", "bin_location", "quantity", "quantity_committed",
    "reorder_point", "restock_level", "cost", "price",
    "last_received", "last_sold", "last_counted", "last_updated",
    "inactive", "taxable", "date_created",
]

TENDERS = [
    (1,  "CASH",          "CASH"),
    (2,  "DELIVERY",      "DELV"),
    (3,  "MASTERCARD",    "MC"),
    (4,  "AMEX",          "AMEX"),
    (5,  "DEBIT",         "DEB"),
    (6,  "DISCOVER",      "DISC"),
    (7,  "STORE ACCOUNT", "ACCT"),
    (8,  "GIFT CARD",     "GIFT"),
    (9,  "TELEPHONE",     "TEL"),
    (10, "EMV",           "EMV"),
    (11, "CHECK",         "CHK"),
    (12, "VISA",          "VISA"),
]

REASON_CODES = [
    (1, "BANK DEPOSIT"),
    (2, "PETTY CASH"),
    (3, "TILL CORRECTION"),
    (4, "PAYOUT TO VENDOR"),
    (5, "EMPLOYEE DRAW"),
    (6, "OTHER"),
]


def load_catalog(cn: psycopg.Connection) -> None:
    log("Phase 1: catalog & reference data")

    # If a real catalog hasn't been extracted yet, generate a plausible
    # synthetic one so the deploy still works. Real CSVs (when present)
    # always win — this is just a fallback.
    from . import synthetic_catalog
    if synthetic_catalog.ensure_present(DATA, seed=SYNTH_SEED):
        log("  (synthetic catalog generated — run extract/extract_real_catalog.py "
            "and push for real WINEZONE data)")

    n = copy_csv(cn, "department", DATA / "departments.csv", ["id", "name"])
    log(f"  department: {n} rows")

    n = copy_csv(cn, "category", DATA / "categories.csv", ["id", "name"])
    log(f"  category: {n} rows")

    n = copy_csv(cn, "supplier", DATA / "suppliers.csv",
                 ["id", "supplier_name"])
    log(f"  supplier: {n} rows")

    n = copy_csv(cn, "item", DATA / "items.csv", ITEM_COLS)
    log(f"  item: {n} rows")

    with cn.cursor() as cur:
        cur.executemany(
            "INSERT INTO tender (id, description, code) VALUES (%s,%s,%s)",
            TENDERS,
        )
        cur.executemany(
            "INSERT INTO reason_code (id, description) VALUES (%s,%s)",
            REASON_CODES,
        )
    cn.commit()
    log(f"  tender: {len(TENDERS)} rows")
    log(f"  reason_code: {len(REASON_CODES)} rows")


# --------------------------------------------------------------------------- #
# Cashier and customer synthesis
# --------------------------------------------------------------------------- #

CASHIER_COUNT = 18

def gen_cashiers(cn: psycopg.Connection) -> list[int]:
    names = []
    seen = set()
    while len(names) < CASHIER_COUNT:
        first = faker.first_name()
        last = faker.last_name()
        key = (first, last)
        if key in seen:
            continue
        seen.add(key)
        names.append((first, last))

    rows = []
    for i, (first, last) in enumerate(names, start=1):
        inactive = 1 if i > CASHIER_COUNT - 2 else 0  # last two retired
        rows.append((
            i, f"{first} {last}", f"{1000+i}", inactive,
            float(rng.choice([100, 250, 500])),     # return_limit
            float(rng.choice([1000, 2500, 5000])),  # floor_limit
            int(rng.integers(1, 4)),                # security_level
        ))
    with cn.cursor() as cur:
        cur.executemany(
            "INSERT INTO cashier (id, name, number, inactive, "
            "return_limit, floor_limit, security_level) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)", rows)
    cn.commit()
    log(f"  cashier: {len(rows)} rows")
    return [r[0] for r in rows]


CUSTOMER_COUNT = 12_000
B2B_FRACTION = 0.06

def gen_customers(cn: psycopg.Connection, span_start: date,
                  span_end: date) -> list[int]:
    log(f"Phase 1b: customers (n={CUSTOMER_COUNT:,})")
    buf = io.StringIO()
    w = csv.writer(buf)
    ids: list[int] = []
    span_days = (span_end - span_start).days

    for i in range(1, CUSTOMER_COUNT + 1):
        is_b2b = rng.random() < B2B_FRACTION
        first = faker.first_name()
        last = faker.last_name()
        company = faker.company() if is_b2b else ""
        # Force fake email/phone domains so they cannot ever collide with
        # real customer data.
        email = f"{first.lower()}.{last.lower()}.{i}@example.com"
        phone = f"555-{rng.integers(100,1000):03d}-{rng.integers(1000,10000):04d}"
        addr = faker.street_address()
        city = faker.city()
        state = faker.state_abbr()
        zipc = faker.postcode()
        opened = span_start + timedelta(days=int(rng.integers(0, span_days)))
        # Initial counters zeroed; will be backfilled after txn generation.
        w.writerow([
            i,
            f"AC{100000 + i}",
            "",
            first, last, company,
            email, phone, addr, city, state, zipc,
            opened.isoformat(),
            "",  # last_visit
            0, 0, 0, 0,
            0 if not is_b2b else float(rng.choice([1000, 2500, 5000])),
            0, 0,
            1 if is_b2b and rng.random() < 0.3 else 0,
            0,
            "B2B" if is_b2b else "",
        ])
        ids.append(i)

    buf.seek(0)
    cols = ("id, account_number, title, first_name, last_name, company, "
            "email_address, phone_number, address, city, state, zip, "
            "account_opened, last_visit, total_visits, total_sales, "
            "total_savings, account_balance, credit_limit, "
            "current_discount, price_level, tax_exempt, employee, notes")
    with cn.cursor() as cur, cur.copy(
        f"COPY customer ({cols}) FROM STDIN WITH (FORMAT csv)"
    ) as copy:
        copy.write(buf.getvalue())
    cn.commit()
    log(f"  customer: {len(ids):,} rows")
    return ids


# --------------------------------------------------------------------------- #
# Velocity profile + sampler
# --------------------------------------------------------------------------- #

def load_velocity_profile() -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                     np.ndarray, np.ndarray, dict[int,float],
                                     dict[int,float], float]:
    """
    Returns:
        item_ids       array of item IDs eligible for sale
        item_weights   probability weight per item (sums to ~1)
        item_prices    avg sold price per item
        item_costs     unit cost per item
        item_returns_w probability weight per item for return lines
        month_mult     {1..12: multiplier}
        dow_mult       {1..7: multiplier} (Sun=1, Sat=7)
        avg_txns_per_day
    """
    # baseline.csv has avg_txns_per_day
    base = 750.0
    p = DATA / "baseline.csv"
    if p.exists():
        with p.open() as f:
            next(f)
            row = next(csv.reader(f))
            try:
                base = float(row[1])
            except (IndexError, ValueError):
                pass

    # items.csv → id, cost, price
    items_by_id: dict[int, tuple[float, float]] = {}
    with (DATA / "items.csv").open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if int(row["inactive"]) != 0:
                continue
            try:
                cost = float(row["cost"] or 0)
                price = float(row["price"] or 0)
            except ValueError:
                continue
            if price <= 0:
                continue
            items_by_id[int(row["id"])] = (cost, price)

    # item_velocity.csv → avg_daily_units, avg_daily_returns, avg_sold_price
    velocity: dict[int, tuple[float, float, float]] = {}
    vpath = DATA / "item_velocity.csv"
    if vpath.exists():
        with vpath.open(encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    iid = int(row["item_id"])
                except ValueError:
                    continue
                if iid not in items_by_id:
                    continue
                velocity[iid] = (
                    float(row.get("avg_daily_units") or 0),
                    float(row.get("avg_daily_returns") or 0),
                    float(row.get("avg_sold_price") or 0),
                )

    # Fall back: any item without a velocity row gets a tiny weight so it
    # still appears occasionally.
    item_ids = []
    weights = []
    prices = []
    costs = []
    ret_weights = []
    for iid, (cost, price) in items_by_id.items():
        v = velocity.get(iid, (0.0, 0.0, price))
        avg_daily = v[0] if v[0] > 0 else 0.001
        item_ids.append(iid)
        weights.append(avg_daily)
        ret_weights.append(v[1] if v[1] > 0 else 0.0001)
        prices.append(v[2] if v[2] > 0 else price)
        costs.append(cost)

    item_ids = np.array(item_ids, dtype=np.int32)
    weights = np.array(weights, dtype=np.float64)
    weights = weights / weights.sum()
    ret_weights = np.array(ret_weights, dtype=np.float64)
    ret_weights = ret_weights / ret_weights.sum()
    prices = np.array(prices, dtype=np.float64)
    costs = np.array(costs, dtype=np.float64)

    # Seasonality
    month_mult = _load_mult(DATA / "month_seasonality.csv", "month_of_year")
    dow_mult = _load_mult(DATA / "dow_seasonality.csv", "day_of_week")

    return item_ids, weights, prices, costs, ret_weights, month_mult, dow_mult, base


def _load_mult(p: Path, key: str) -> dict[int, float]:
    out: dict[int, float] = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                k = int(row[key])
                v = float(row["multiplier"])
            except (ValueError, KeyError):
                continue
            if v > 0:
                out[k] = v
    return out


def hour_distribution() -> np.ndarray:
    """24-element array summing to 1."""
    p = DATA / "hour_distribution.csv"
    out = np.zeros(24)
    if p.exists():
        with p.open(encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    h = int(row["hour_of_day"])
                    s = float(row["share"])
                except (ValueError, KeyError):
                    continue
                if 0 <= h < 24:
                    out[h] = s
    if out.sum() == 0:
        # Plausible liquor store curve, peak 17:00-20:00, closed overnight.
        weights = np.array([0,0,0,0,0,0,0,0,
                            0.5,1,1.5,2,2.5,3,3.5,4,
                            5,7,8,7,5,3,1.5,0.5])
        out = weights / weights.sum()
    else:
        out = out / out.sum()
    return out


# --------------------------------------------------------------------------- #
# Phase 2: synthesize 4 years of transactions
# --------------------------------------------------------------------------- #

# Tender mix probabilities (approximate liquor store split):
TENDER_MIX = [
    (1,  0.28),  # CASH
    (3,  0.18),  # MASTERCARD
    (12, 0.20),  # VISA
    (5,  0.18),  # DEBIT
    (4,  0.08),  # AMEX
    (6,  0.05),  # DISCOVER
    (10, 0.02),  # EMV
    (7,  0.005), # STORE ACCOUNT
    (11, 0.003), # CHECK
    (8,  0.002), # GIFT
]
TENDER_IDS = np.array([t[0] for t in TENDER_MIX])
TENDER_P   = np.array([t[1] for t in TENDER_MIX])
TENDER_P   = TENDER_P / TENDER_P.sum()


def generate_transactions(cn: psycopg.Connection, customer_ids: list[int],
                          cashier_ids: list[int]) -> tuple[int, int]:
    log("Phase 2: transactions")
    end = date.today()
    start = end - timedelta(days=SYNTH_YEARS * 365)
    log(f"  span: {start} → {end} ({(end-start).days} days)")

    (item_ids, item_w, item_prices, item_costs,
     ret_w, month_mult, dow_mult, base_daily) = load_velocity_profile()
    hour_dist = hour_distribution()
    log(f"  catalog: {len(item_ids):,} sellable SKUs; base {base_daily:.0f} txns/day")

    cust_arr = np.array(customer_ids, dtype=np.int32)
    cash_arr = np.array([c for c in cashier_ids[:-2]], dtype=np.int32)  # active only

    # Item-level RNG samples are the hot path. Pre-build a CDF for fast sampling.
    item_cdf = np.cumsum(item_w)

    txn_no = 100_000  # starting transaction number
    batch_no = 1
    cur_day = start
    total_txns = 0
    total_entries = 0
    t_start = time.time()

    # Pre-open COPY streams. We keep them open in batches by week to avoid
    # one giant statement.
    while cur_day <= end:
        week_end = min(cur_day + timedelta(days=7), end + timedelta(days=1))
        txn_no, batch_no, b, e = _generate_week(
            cn, cur_day, week_end, batch_no, txn_no,
            item_ids, item_cdf, item_prices, item_costs, ret_w,
            month_mult, dow_mult, hour_dist, base_daily,
            cust_arr, cash_arr)
        total_txns += b
        total_entries += e
        elapsed = time.time() - t_start
        log(f"  through {week_end.isoformat()}: "
            f"{total_txns:,} txns, {total_entries:,} entries "
            f"({elapsed:.0f}s, {total_txns/max(1,elapsed):.0f} txns/s)")
        cur_day = week_end

    log(f"  done. {total_txns:,} txns and {total_entries:,} entries "
        f"in {time.time()-t_start:.0f}s")
    return total_txns, total_entries


def _generate_week(cn: psycopg.Connection, start: date, end: date,
                   batch_no: int, txn_no: int,
                   item_ids: np.ndarray, item_cdf: np.ndarray,
                   item_prices: np.ndarray, item_costs: np.ndarray,
                   ret_w: np.ndarray, month_mult: dict[int,float],
                   dow_mult: dict[int,float], hour_dist: np.ndarray,
                   base_daily: float, cust_arr: np.ndarray,
                   cash_arr: np.ndarray) -> tuple[int, int, int, int]:
    """Generate transactions for [start, end). Streams into Postgres COPY.
    Returns (next_txn_no, next_batch_no, txns_this_window, entries_this_window).
    """

    txn_rows: list[tuple] = []
    entry_rows: list[tuple] = []
    tender_rows: list[tuple] = []
    batch_rows: list[tuple] = []
    txns_this_week = 0
    entries_this_week = 0

    d = start
    while d < end:
        mm = month_mult.get(d.month, 1.0)
        # In WINEZONE, DATEPART WEEKDAY default returns 1=Sun..7=Sat
        dow_sql = (d.weekday() + 2) % 7 or 7  # Mon=2 ... Sun=1 → match SQL Server default
        dw = dow_mult.get(dow_sql, 1.0)
        target = int(round(base_daily * mm * dw))
        target = max(20, target)
        if SYNTH_DAY_TXN_CAP > 0:
            target = min(target, SYNTH_DAY_TXN_CAP)

        # Open a batch for the day
        batch_open = datetime.combine(d, datetime.min.time()).replace(hour=8)
        batch_close = datetime.combine(d, datetime.min.time()).replace(hour=23)
        batch_rows.append((batch_no, batch_open, batch_close))
        this_batch = batch_no
        batch_no += 1

        # Sample hours for each txn (vectorized)
        hours = rng.choice(24, size=target, p=hour_dist)
        minutes = rng.integers(0, 60, size=target)
        seconds = rng.integers(0, 60, size=target)

        # Sample basket sizes
        basket_sizes = np.clip(
            rng.negative_binomial(2, 0.45, size=target) + 1, 1, 28
        )

        # Customer attached ~1.6%
        has_customer = rng.random(target) < 0.016
        customer_pick = cust_arr[rng.integers(0, len(cust_arr), size=target)]

        # Cashier pick — weighted toward mid-staff
        cashier_pick = cash_arr[rng.integers(0, len(cash_arr), size=target)]

        # Return flags
        is_return = rng.random(target) < 0.018

        # Pre-sample all line items in one big draw
        total_lines = int(basket_sizes.sum())
        # Vectorized weighted sample via searchsorted on the CDF
        u = rng.random(total_lines)
        flat_items = np.searchsorted(item_cdf, u)
        flat_items = np.clip(flat_items, 0, len(item_ids) - 1)

        line_cursor = 0
        for i in range(target):
            txn_no += 1
            h, m, s = int(hours[i]), int(minutes[i]), int(seconds[i])
            t = datetime.combine(d, datetime.min.time()).replace(
                hour=h, minute=m, second=s)
            sz = int(basket_sizes[i])
            items_this_basket = flat_items[line_cursor:line_cursor + sz]
            line_cursor += sz

            ret = bool(is_return[i])
            sign = -1 if ret else 1

            tx_total = 0.0
            tx_tax = 0.0
            for idx in items_this_basket:
                item_id = int(item_ids[idx])
                price = float(item_prices[idx])
                cost = float(item_costs[idx])
                qty = sign * 1  # most baskets are qty 1; occasional bulk handled below
                # Bulk: ~6% chance qty 2-6, ~1% qty 6-12
                r = rng.random()
                if r < 0.06:
                    qty = sign * int(rng.integers(2, 7))
                elif r < 0.07:
                    qty = sign * int(rng.integers(6, 13))
                # Occasional discount
                full_price = price
                if rng.random() < 0.04:
                    price = round(price * float(rng.uniform(0.85, 0.95)), 2)
                # Sales tax on liquor varies; demo: 8.625% on taxable items
                line_net = qty * price
                line_tax = round(abs(line_net) * 0.08625, 4) if line_net != 0 else 0
                entry_rows.append((
                    txn_no, item_id, qty, price, full_price, cost,
                    line_tax, t, 1
                ))
                tx_total += line_net
                tx_tax += line_tax if not ret else -line_tax
                entries_this_week += 1

            cust_val = int(customer_pick[i]) if bool(has_customer[i]) else None
            tx_total_tax = round(tx_total + tx_tax, 2)
            txn_rows.append((
                txn_no, this_batch, 1, t, cust_val,
                int(cashier_pick[i]),
                tx_total_tax, round(tx_tax, 2), 0, "", ""
            ))

            # Tender entry — one tender per txn
            tid = int(rng.choice(TENDER_IDS, p=TENDER_P))
            tender_rows.append((txn_no, tid, tx_total_tax, t))

            txns_this_week += 1

        # Flush this day's batches periodically so memory stays bounded
        if len(entry_rows) > 250_000:
            _flush(cn, txn_rows, entry_rows, tender_rows, batch_rows)
            txn_rows.clear()
            entry_rows.clear()
            tender_rows.clear()
            batch_rows.clear()

        d += timedelta(days=1)

    # Final flush
    if txn_rows or entry_rows or batch_rows:
        _flush(cn, txn_rows, entry_rows, tender_rows, batch_rows)

    return txn_no, batch_no, txns_this_week, entries_this_week


def _flush(cn: psycopg.Connection, txn_rows, entry_rows, tender_rows,
           batch_rows) -> None:
    with cn.cursor() as cur:
        if batch_rows:
            with cur.copy("COPY batch (batch_number, opened, closed) "
                          "FROM STDIN WITH (FORMAT csv)") as copy:
                buf = io.StringIO()
                w = csv.writer(buf)
                for r in batch_rows:
                    w.writerow(r)
                copy.write(buf.getvalue())
        if txn_rows:
            with cur.copy(
                'COPY "transaction" (transaction_number, batch_number, '
                'store_id, time, customer_id, cashier_id, total, '
                'sales_tax, status, comment, reference_number) '
                'FROM STDIN WITH (FORMAT csv, NULL \'\\N\')'
            ) as copy:
                buf = io.StringIO()
                w = csv.writer(buf)
                for r in txn_rows:
                    out = list(r)
                    out[4] = "\\N" if out[4] is None else out[4]
                    w.writerow(out)
                copy.write(buf.getvalue())
        if entry_rows:
            with cur.copy(
                "COPY transaction_entry (transaction_number, item_id, "
                "quantity, price, full_price, cost, sales_tax, "
                "transaction_time, store_id) "
                "FROM STDIN WITH (FORMAT csv)"
            ) as copy:
                buf = io.StringIO()
                w = csv.writer(buf)
                for r in entry_rows:
                    w.writerow(r)
                copy.write(buf.getvalue())
        if tender_rows:
            with cur.copy(
                "COPY tender_entry (transaction_number, tender_id, "
                "amount, time) FROM STDIN WITH (FORMAT csv)"
            ) as copy:
                buf = io.StringIO()
                w = csv.writer(buf)
                for r in tender_rows:
                    w.writerow(r)
                copy.write(buf.getvalue())
    cn.commit()


# --------------------------------------------------------------------------- #
# Phase 3: supporting events + customer denorms + item.last_sold backfill
# --------------------------------------------------------------------------- #

def backfill_aggregates(cn: psycopg.Connection) -> None:
    log("Phase 3: backfill aggregates")
    with cn.cursor() as cur:
        cur.execute("""
            UPDATE customer c SET
                total_visits  = COALESCE(agg.visits, 0),
                total_sales   = COALESCE(agg.spend, 0),
                last_visit    = agg.last_visit
            FROM (
                SELECT t.customer_id,
                       COUNT(DISTINCT t.transaction_number) AS visits,
                       SUM(t.total)                          AS spend,
                       MAX(t.time)                           AS last_visit
                FROM "transaction" t
                WHERE t.customer_id IS NOT NULL
                GROUP BY t.customer_id
            ) agg
            WHERE c.id = agg.customer_id
        """)
        log(f"    customer aggregates updated: {cur.rowcount:,}")

        cur.execute("""
            UPDATE item i SET
                last_sold = a.last_sold
            FROM (
                SELECT item_id, MAX(transaction_time) AS last_sold
                FROM transaction_entry
                WHERE quantity > 0
                GROUP BY item_id
            ) a
            WHERE i.id = a.item_id
        """)
        log(f"    item.last_sold updated: {cur.rowcount:,}")
    cn.commit()


def generate_purchase_orders(cn: psycopg.Connection) -> None:
    log("Phase 3b: purchase orders")
    end = date.today()
    start = end - timedelta(days=SYNTH_YEARS * 365)
    span_days = (end - start).days

    with cn.cursor() as cur:
        cur.execute("SELECT id, supplier_id FROM item WHERE inactive=0 "
                    "AND supplier_id IS NOT NULL")
        items_by_supplier: dict[int, list[int]] = {}
        for iid, sid in cur.fetchall():
            items_by_supplier.setdefault(sid, []).append(iid)

    suppliers = list(items_by_supplier.keys())
    log(f"  generating POs for {len(suppliers)} suppliers")

    po_id = 1
    po_rows = []
    poe_rows = []
    for sid in suppliers:
        # Roughly one PO per month per supplier with items
        pos_count = max(2, SYNTH_YEARS * 12 // 3)
        for n in range(pos_count):
            created = start + timedelta(days=int(rng.integers(0, span_days)))
            lead = int(rng.integers(3, 21))
            received = created + timedelta(days=lead)
            placed = created + timedelta(days=int(rng.integers(0, 2)))
            required = created + timedelta(days=int(rng.integers(7, 21)))
            # Status: 5=closed if received <= today, else 2=placed
            status = 5 if received < end else 2
            po_rows.append((
                po_id, f"PO{po_id:06d}", sid, status,
                datetime.combine(created, datetime.min.time()),
                datetime.combine(placed, datetime.min.time()),
                datetime.combine(required, datetime.min.time()),
            ))
            lines = items_by_supplier[sid]
            n_lines = min(len(lines), int(rng.integers(3, 25)))
            picked = rng.choice(lines, size=n_lines, replace=False)
            for iid in picked:
                ordered = int(rng.integers(6, 60))
                ratio = rng.uniform(0.85, 1.05) if status == 5 else rng.uniform(0, 1.05)
                got = max(0, int(round(ordered * ratio)))
                price = float(rng.uniform(2.5, 35.0))
                poe_rows.append((
                    po_id, int(iid), ordered, got, round(price, 4),
                    datetime.combine(received, datetime.min.time())
                    if got > 0 else None,
                ))
            po_id += 1

    with cn.cursor() as cur:
        cur.executemany(
            "INSERT INTO purchase_order (id, po_number, supplier_id, status, "
            "date_created, date_placed, required_date) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)", po_rows)
        cur.executemany(
            "INSERT INTO purchase_order_entry (purchase_order_id, item_id, "
            "quantity_ordered, quantity_received, price, last_received_date) "
            "VALUES (%s,%s,%s,%s,%s,%s)", poe_rows)
    cn.commit()
    log(f"  purchase_order: {len(po_rows):,} rows")
    log(f"  purchase_order_entry: {len(poe_rows):,} rows")


def generate_supporting_events(cn: psycopg.Connection,
                                cashier_ids: list[int]) -> None:
    log("Phase 3c: supporting events")
    end = datetime.now()
    start = end - timedelta(days=SYNTH_YEARS * 365)
    span_days = (end - start).days
    active = [c for c in cashier_ids[:-2]]

    # Non-tender (no-sale drawer opens) — ~12 per day across all cashiers
    nt_rows = []
    for d in range(span_days):
        for _ in range(int(rng.integers(0, 24))):
            t = start + timedelta(days=d,
                                  seconds=int(rng.integers(8*3600, 22*3600)))
            cid = int(rng.choice(active))
            nt_rows.append((cid, 13, t))

    # Cash drops — one per cashier shift, ~end of day
    dp_rows = []
    for d in range(span_days):
        for cid in active[:int(rng.integers(2, 7))]:
            t = start + timedelta(days=d, hours=22,
                                  minutes=int(rng.integers(0, 60)))
            amt = round(float(rng.uniform(50, 600)), 2)
            dp_rows.append((cid, t, amt, "BANK DEPOSIT", "", 1))

    # Time card — 1-2 shifts per active cashier per day
    tc_rows = []
    for d in range(span_days):
        day_dt = start + timedelta(days=d)
        for cid in active:
            if rng.random() < 0.55:
                tin = day_dt.replace(
                    hour=int(rng.integers(8, 14)),
                    minute=int(rng.integers(0, 60)))
                hours = float(rng.uniform(4, 9))
                tout = tin + timedelta(hours=hours)
                tc_rows.append((cid, tin, tout, round(hours, 2)))

    # Item value log — sporadic cost changes
    with cn.cursor() as cur:
        cur.execute("SELECT id, cost FROM item WHERE inactive=0 ORDER BY id LIMIT 1500")
        items_for_log = cur.fetchall()
    ivl_rows = []
    for iid, cost in items_for_log:
        if rng.random() < 0.4:
            for _ in range(int(rng.integers(1, 4))):
                t = start + timedelta(days=int(rng.integers(0, span_days)))
                old = float(cost) * float(rng.uniform(0.85, 1.0))
                new = old * float(rng.uniform(0.95, 1.18))
                ivl_rows.append((iid, t, 'C', round(old, 4), round(new, 4)))

    with cn.cursor() as cur:
        if nt_rows:
            cur.executemany(
                "INSERT INTO non_tender_transaction "
                "(cashier_id, transaction_type, time) VALUES (%s,%s,%s)",
                nt_rows)
        if dp_rows:
            cur.executemany(
                "INSERT INTO drop_payout (cashier_id, time, amount, "
                "recipient, comment, reason_code_id) "
                "VALUES (%s,%s,%s,%s,%s,%s)", dp_rows)
        if tc_rows:
            cur.executemany(
                "INSERT INTO time_card (cashier_id, time_in, time_out, hours) "
                "VALUES (%s,%s,%s,%s)", tc_rows)
        if ivl_rows:
            cur.executemany(
                "INSERT INTO item_value_log (item_id, last_updated, "
                "amount_type, old_amount, new_amount) "
                "VALUES (%s,%s,%s,%s,%s)", ivl_rows)
    cn.commit()
    log(f"  non_tender_transaction: {len(nt_rows):,}")
    log(f"  drop_payout: {len(dp_rows):,}")
    log(f"  time_card: {len(tc_rows):,}")
    log(f"  item_value_log: {len(ivl_rows):,}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    log(f"render_demo seed v{SEED_VERSION} (seed={SYNTH_SEED}, years={SYNTH_YEARS})")
    t0 = time.time()
    with psycopg.connect(DATABASE_URL, autocommit=False) as cn:
        if not FORCE_RESEED and already_seeded(cn):
            log("Main seed marker present — skipping phases 1-3.")
            # Auxiliary loaders still run unconditionally (each is idempotent)
            # so a redeploy after pushing new RIP / invoice CSVs picks them up
            # without a full reseed.
            log("Auxiliary phase: RIP / invoices / aliases")
            from . import seed_rip
            result = seed_rip.ensure(cn, seed=SYNTH_SEED, log=lambda m: log(m))
            log(f"  source: {result}")
            log(f"Done in {time.time()-t0:.0f}s")
            return

        log("Applying schema")
        apply_schema(cn)

        load_catalog(cn)
        cashier_ids = gen_cashiers(cn)
        end = date.today()
        start = end - timedelta(days=SYNTH_YEARS * 365)
        customer_ids = gen_customers(cn, start, end)

        total_txns, total_entries = generate_transactions(
            cn, customer_ids, cashier_ids
        )

        backfill_aggregates(cn)
        generate_purchase_orders(cn)
        generate_supporting_events(cn, cashier_ids)

        # RIP + invoice + risk-calc-alias data. If data/rip_*.csv files
        # exist (produced by extract/extract_rip.py), load them. Otherwise
        # synthesize. Idempotent — skips if already populated unless
        # FORCE_RIP_RELOAD=true.
        log("Phase 3d: RIP / invoices / aliases")
        from . import seed_rip
        result = seed_rip.ensure(cn, seed=SYNTH_SEED, log=lambda m: log(m))
        log(f"  source: {result}")

        log("Phase 4: analyze tables")
        with cn.cursor() as cur:
            cur.execute("ANALYZE")
            cur.execute("INSERT INTO seed_marker "
                        "(id, seeded_at, seed_version, txn_count) "
                        "VALUES (1, NOW(), %s, %s) "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "seeded_at = EXCLUDED.seeded_at, "
                        "seed_version = EXCLUDED.seed_version, "
                        "txn_count = EXCLUDED.txn_count",
                        (SEED_VERSION, total_txns))
        cn.commit()
    log(f"Seed complete in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
