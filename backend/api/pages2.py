"""
JSON endpoints for the remaining 19 page ports.

Most endpoints are thin wrappers around analytics.py functions or single
Postgres queries. Pages whose source schema isn't part of the demo seed
(RIP programs, invoice line matches) return well-formed empty payloads
so the frontend renders a clean "no data" state.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from .. import analytics
from ..auth import current_user
from ..db import fetch, fetchrow

router = APIRouter(prefix="/api", tags=["pages2"])


def _u(user=Depends(current_user)):  # short auth dep
    return user


# ============================================================== #
# EXCESS STOCK
# ============================================================== #

@router.get("/excess-stock")
async def excess_stock(velocity_months: int = 6, min_mos: float = 6,
                       min_oh_value: float = 100, supplier: Optional[str] = None,
                       dept: Optional[str] = None, limit: int = 500, _=Depends(_u)):
    sql = """
    WITH velocity AS (
        SELECT te.item_id,
               SUM(te.quantity) / NULLIF($1*30.0, 0) AS daily_units,
               SUM(te.quantity) / NULLIF($1, 0)      AS monthly_units
        FROM transaction_entry te
        WHERE te.transaction_time >= NOW() - make_interval(months => $1)
          AND te.quantity > 0
        GROUP BY te.item_id
    )
    SELECT
      i.item_lookup_code AS "UPC",
      i.description      AS "Description",
      COALESCE(d.name,'')  AS "Department",
      COALESCE(c.name,'')  AS "Category",
      COALESCE(s.supplier_name,'')  AS "SupplierName",
      i.quantity         AS "OnHand",
      i.cost             AS "Cost",
      (i.quantity * i.cost) AS "InventoryValue",
      COALESCE(v.monthly_units, 0) AS "AvgMonthlySales",
      CASE WHEN COALESCE(v.daily_units,0) > 0
           THEN (i.quantity / (v.daily_units * 30))
           ELSE NULL END AS "MoS",
      (CURRENT_DATE - i.last_sold::date)::int AS "DaysSinceLastSale",
      CASE
        WHEN COALESCE(v.daily_units,0) = 0 THEN 'Dead'
        WHEN (i.quantity / (v.daily_units * 30)) > 24 THEN 'Excess'
        ELSE 'Healthy'
      END AS "Risk"
    FROM item i
    LEFT JOIN department d ON i.department_id = d.id
    LEFT JOIN category   c ON i.category_id   = c.id
    LEFT JOIN supplier   s ON i.supplier_id   = s.id
    LEFT JOIN velocity   v ON v.item_id       = i.id
    WHERE i.inactive = 0
      AND i.quantity > 0
      AND (i.quantity * i.cost) >= $2
      AND (
        COALESCE(v.daily_units,0) = 0
        OR (i.quantity / (v.daily_units * 30)) >= $3
      )
      AND ($4::text IS NULL OR s.supplier_name ILIKE $4)
      AND ($5::text IS NULL OR d.name ILIKE $5)
    ORDER BY (i.quantity * i.cost) DESC NULLS LAST
    LIMIT $6
    """
    rows = await fetch(sql, velocity_months, min_oh_value, min_mos,
                       f"%{supplier}%" if supplier else None,
                       f"%{dept}%" if dept else None,
                       int(limit))
    total_capital = sum(float(r["InventoryValue"] or 0) for r in rows)
    dead_capital = sum(float(r["InventoryValue"] or 0) for r in rows if r["Risk"] == "Dead")
    by_supp: dict[str, dict] = {}
    by_dept: dict[str, dict] = {}
    for r in rows:
        s = r["SupplierName"] or "(none)"
        b = by_supp.setdefault(s, {"SupplierName": s, "Skus": 0, "Value": 0})
        b["Skus"] += 1
        b["Value"] += float(r["InventoryValue"] or 0)
        d = r["Department"] or "(none)"
        bd = by_dept.setdefault(d, {"Department": d, "Skus": 0, "Value": 0})
        bd["Skus"] += 1
        bd["Value"] += float(r["InventoryValue"] or 0)
    return {
        "summary": {
            "sku_count": len(rows), "total_capital": total_capital,
            "dead_capital": dead_capital,
            "suppliers_affected": len(by_supp),
        },
        "by_supplier": sorted(by_supp.values(), key=lambda x: -x["Value"])[:15],
        "by_department": sorted(by_dept.values(), key=lambda x: -x["Value"])[:15],
        "rows": rows,
    }


# ============================================================== #
# ITEMS BROWSE
# ============================================================== #

@router.get("/items")
async def items(q: Optional[str] = None, dept: Optional[str] = None,
                supplier: Optional[str] = None, limit: int = 200, _=Depends(_u)):
    args: list = []
    conds = ["i.inactive = 0"]
    if q:
        args.append(f"%{q}%")
        conds.append(f"(i.item_lookup_code ILIKE ${len(args)} OR i.description ILIKE ${len(args)})")
    if dept:
        args.append(f"%{dept}%")
        conds.append(f"d.name ILIKE ${len(args)}")
    if supplier:
        args.append(f"%{supplier}%")
        conds.append(f"s.supplier_name ILIKE ${len(args)}")
    sql = f"""
    SELECT i.id AS "ID", i.item_lookup_code AS "UPC",
           i.description AS "Description",
           COALESCE(d.name,'') AS "Department",
           COALESCE(c.name,'') AS "Category",
           COALESCE(s.supplier_name,'') AS "SupplierName",
           i.quantity AS "OnHand", i.cost AS "Cost", i.price AS "Price",
           i.last_sold AS "LastSold"
    FROM item i
    LEFT JOIN department d ON i.department_id = d.id
    LEFT JOIN category   c ON i.category_id   = c.id
    LEFT JOIN supplier   s ON i.supplier_id   = s.id
    WHERE {" AND ".join(conds)}
    ORDER BY i.description
    LIMIT {int(limit)}
    """
    rows = await fetch(sql, *args)
    return {"count": len(rows), "rows": rows}


# ============================================================== #
# PURCHASE ORDERS BROWSE + DETAIL
# ============================================================== #

@router.get("/pos")
async def pos_browse(supplier: Optional[str] = None,
                     status: Optional[str] = None,
                     days: int = 365, limit: int = 500, _=Depends(_u)):
    args: list = [days]
    conds = ["po.date_created >= NOW() - make_interval(days => $1)"]
    if supplier:
        args.append(f"%{supplier}%")
        conds.append(f"s.supplier_name ILIKE ${len(args)}")
    if status:
        try:
            args.append(int(status))
            conds.append(f"po.status = ${len(args)}")
        except ValueError:
            pass
    sql = f"""
    SELECT po.po_number AS "PONumber",
           s.supplier_name AS "SupplierName",
           po.status      AS "Status",
           po.date_created AS "DateCreated",
           po.date_placed  AS "DatePlaced",
           po.required_date AS "RequiredDate",
           COALESCE(SUM(poe.quantity_ordered), 0)::int AS "UnitsOrdered",
           COALESCE(SUM(poe.quantity_received), 0)::int AS "UnitsReceived",
           COALESCE(SUM(poe.quantity_ordered * poe.price), 0) AS "Value",
           COUNT(poe.id)::int AS "Lines"
    FROM purchase_order po
    JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
    LEFT JOIN supplier s ON po.supplier_id = s.id
    WHERE {" AND ".join(conds)}
    GROUP BY po.po_number, s.supplier_name, po.status, po.date_created,
             po.date_placed, po.required_date
    ORDER BY po.date_created DESC
    LIMIT {int(limit)}
    """
    rows = await fetch(sql, *args)
    return {"count": len(rows), "rows": rows}


@router.get("/po/{po_number}")
async def po_detail(po_number: str, _=Depends(_u)):
    header = await fetchrow("""
        SELECT po.id, po.po_number AS "PONumber", po.status AS "Status",
               po.date_created AS "DateCreated", po.date_placed AS "DatePlaced",
               po.required_date AS "RequiredDate",
               s.supplier_name AS "SupplierName"
        FROM purchase_order po
        LEFT JOIN supplier s ON po.supplier_id = s.id
        WHERE po.po_number = $1
    """, po_number)
    if not header:
        raise HTTPException(404, f"PO {po_number} not found")
    lines = await fetch("""
        SELECT poe.id, i.item_lookup_code AS "UPC", i.description AS "Description",
               d.name AS "Department",
               poe.quantity_ordered AS "QtyOrdered",
               poe.quantity_received AS "QtyReceived",
               (poe.quantity_ordered - poe.quantity_received) AS "QtyOpen",
               poe.price AS "UnitCost",
               (poe.quantity_ordered * poe.price) AS "LineTotal",
               poe.last_received_date AS "LastReceivedDate"
        FROM purchase_order_entry poe
        JOIN item i ON poe.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        WHERE poe.purchase_order_id = $1
        ORDER BY i.description
    """, header["id"])
    totals = {
        "line_count": len(lines),
        "units_ordered": sum(float(l["QtyOrdered"] or 0) for l in lines),
        "units_received": sum(float(l["QtyReceived"] or 0) for l in lines),
        "value": sum(float(l["LineTotal"] or 0) for l in lines),
    }
    return {"header": header, "lines": lines, "totals": totals}


# ============================================================== #
# INVOICES — loaded from invoice_header / invoice_line CSVs.
# ============================================================== #

@router.get("/invoices")
async def invoices(supplier: Optional[str] = None,
                   q: Optional[str] = None,
                   limit: int = 200, _=Depends(_u)):
    args: list = []
    conds = ["1=1"]
    if supplier:
        args.append(f"%{supplier}%")
        conds.append(f"supplier ILIKE ${len(args)}")
    if q:
        args.append(f"%{q}%")
        conds.append(f"(invoice_no ILIKE ${len(args)} OR filename ILIKE ${len(args)})")
    rows = await fetch(f"""
        SELECT id AS "ID",
               supplier AS "Supplier",
               invoice_no AS "InvoiceNumber",
               invoice_date AS "InvoiceDate",
               total_cost AS "Total",
               line_count AS "Lines",
               matched_count AS "Matched",
               (COALESCE(line_count, 0) - COALESCE(matched_count, 0)) AS "Unmapped",
               filename AS "SourceFile",
               uploaded_at AS "UploadedAt",
               notes AS "Notes"
        FROM invoice_header
        WHERE {" AND ".join(conds)}
        ORDER BY invoice_date DESC NULLS LAST, id DESC
        LIMIT {int(limit)}
    """, *args)
    return {"rows": rows, "count": len(rows)}


@router.get("/invoices/{invoice_id}")
async def invoice_detail(invoice_id: int, _=Depends(_u)):
    header = await fetchrow("""
        SELECT id AS "ID",
               supplier AS "Supplier",
               invoice_no AS "InvoiceNumber",
               invoice_date AS "InvoiceDate",
               total_cost AS "Total",
               line_count AS "Lines",
               matched_count AS "Matched",
               (COALESCE(line_count, 0) - COALESCE(matched_count, 0)) AS "Unmapped",
               filename AS "SourceFile",
               uploaded_at AS "UploadedAt",
               notes AS "Notes"
        FROM invoice_header WHERE id = $1
    """, invoice_id)
    if not header:
        raise HTTPException(404, "Invoice not found")
    lines = await fetch("""
        SELECT id AS "ID",
               line_no AS "LineNumber",
               raw_upc AS "RawUPC",
               raw_description AS "RawDescription",
               qty AS "Quantity",
               unit_price AS "UnitPrice",
               line_total AS "LineTotal",
               item_upc AS "MatchedUPC",
               item_description AS "MatchedDescription",
               match_method AS "MatchMethod",
               match_score AS "MatchScore",
               cost_delta_pct AS "CostDeltaPct",
               notes AS "Notes"
        FROM invoice_line WHERE invoice_id = $1
        ORDER BY line_no, id
    """, invoice_id)
    return {"header": header, "lines": lines}


# ============================================================== #
# RISK-CALC ALIASES (loaded from risk_calc_alias CSV)
# ============================================================== #

@router.get("/risk-calc/aliases")
async def risk_calc_aliases(_=Depends(_u)):
    rows = await fetch("""
        SELECT id AS "ID",
               input_norm AS "Alias",
               input_raw AS "RawInput",
               item_upc AS "ItemUPC",
               item_description AS "ItemDescription",
               item_id AS "ItemID",
               use_count AS "UseCount",
               created_at AS "CreatedAt",
               last_used_at AS "LastUsedAt"
        FROM risk_calc_alias
        ORDER BY use_count DESC NULLS LAST, input_norm
    """)
    return {"rows": rows, "count": len(rows)}


# ============================================================== #
# RISK CALC (paste UPC + qty → resolved lines + risk)
# ============================================================== #

_UPC_RE = re.compile(r"^\s*(\d{6,14})\s*[,\t |x]\s*(\d+(?:\.\d+)?)?\s*$")


@router.post("/risk-calc")
async def risk_calc(payload: dict = Body(...), _=Depends(_u)):
    raw = str(payload.get("lines", ""))
    history_months = int(payload.get("history_months", 18))
    parsed: list[tuple[str, float]] = []
    for line in raw.splitlines():
        m = _UPC_RE.match(line)
        if not m:
            continue
        code = m.group(1)
        qty = float(m.group(2) or 1)
        parsed.append((code, qty))
    if not parsed:
        return {"lines": [], "summary": {}, "raw": raw}

    out_lines = []
    for upc, qty in parsed:
        item = await fetchrow("""
            SELECT i.id, i.item_lookup_code, i.description,
                   COALESCE(s.supplier_name,'') AS supplier,
                   COALESCE(d.name,'') AS department,
                   i.quantity, i.quantity_committed, i.cost, i.price
            FROM item i
            LEFT JOIN supplier s ON i.supplier_id = s.id
            LEFT JOIN department d ON i.department_id = d.id
            WHERE i.item_lookup_code = $1
            LIMIT 1
        """, upc)
        if not item:
            out_lines.append({"UPC": upc, "Description": "(not found)", "QtyToOrder": qty,
                              "Risk": "Unknown"})
            continue
        vel = await fetchrow("""
            SELECT SUM(te.quantity) AS units
            FROM transaction_entry te
            WHERE te.item_id = $1
              AND te.transaction_time >= NOW() - make_interval(months => $2)
              AND te.quantity > 0
        """, item["id"], history_months)
        monthly = float((vel or {}).get("units") or 0) / max(1, history_months)
        on_hand = float(item["quantity"] or 0)
        committed = float(item["quantity_committed"] or 0)
        avail = on_hand - committed
        mos_now = avail / monthly if monthly > 0 else None
        mos_post = (avail + qty) / monthly if monthly > 0 else None
        if monthly == 0:
            risk = "Dead"
        elif (mos_post or 0) > 12:
            risk = "Excess"
        elif (mos_now or 0) <= 0.25:
            risk = "Critical"
        elif (mos_now or 0) <= 0.7:
            risk = "High"
        elif (mos_now or 0) <= 2:
            risk = "Moderate"
        else:
            risk = "Healthy"
        out_lines.append({
            "UPC": item["item_lookup_code"],
            "Description": item["description"],
            "Supplier": item["supplier"],
            "Department": item["department"],
            "QtyToOrder": qty,
            "OnHand": on_hand,
            "AvgMonthlySales": monthly,
            "MoSNow": mos_now,
            "MoSAfterOrder": mos_post,
            "UnitCost": float(item["cost"] or 0),
            "LineCost": qty * float(item["cost"] or 0),
            "Risk": risk,
        })
    summary: dict[str, dict] = {}
    for l in out_lines:
        b = summary.setdefault(l["Risk"], {"Risk": l["Risk"], "Lines": 0, "Value": 0.0})
        b["Lines"] += 1
        b["Value"] += float(l.get("LineCost") or 0)
    return {"lines": out_lines, "summary": list(summary.values()),
            "history_months": history_months, "raw": raw}


# ============================================================== #
# ORDER SUGGESTIONS (rich wrap around reorder_recommendations)
# ============================================================== #

@router.get("/order-suggestions")
async def order_suggestions(weeks: int = 12, velocity_months: int = 18,
                             supplier: Optional[str] = None,
                             dept: Optional[str] = None,
                             min_velocity: Optional[float] = None,
                             limit: int = 500, _=Depends(_u)):
    horizon_days = weeks * 7
    base = await analytics.reorder_recommendations(
        lookback_days=velocity_months * 30,
        horizon_days=horizon_days,
        only_active=True,
        limit=limit * 3,
    )
    rows = base
    if supplier:
        rows = [r for r in rows if (r.get("Supplier") or "").lower().find(supplier.lower()) >= 0]
    if dept:
        rows = [r for r in rows if (r.get("Department") or "").lower().find(dept.lower()) >= 0]
    if min_velocity is not None:
        rows = [r for r in rows if (r.get("AvgDailySales") or 0) >= min_velocity]
    rows = rows[:limit]
    summary = {
        "lines": len(rows),
        "suggested_units": sum(float(r.get("SuggestedReorderQty") or 0) for r in rows),
        "suggested_value": sum(
            float(r.get("SuggestedReorderQty") or 0) * float(r.get("UnitCost") or 0)
            for r in rows
        ),
    }
    return {"summary": summary, "rows": rows}


# ============================================================== #
# RIP — backed by rip_program / rip_combo / rip_match (extracted from
# the original SQLite store via extract/extract_rip.py).
# ============================================================== #

async def _rip_months_available() -> list[dict]:
    return await fetch("""
        SELECT month AS "Month", label AS "Label",
               rip_rows AS "Programs", combo_rows AS "Combos"
        FROM rip_month
        ORDER BY month DESC
    """)


@router.get("/rip/programs")
async def rip_programs(month: Optional[str] = None,
                       supplier: Optional[str] = None,
                       brand: Optional[str] = None,
                       q: Optional[str] = None,
                       limit: int = 500,
                       _=Depends(_u)):
    months = await _rip_months_available()
    if not months:
        return {"rows": [], "summary": {"programs": 0, "potential_rebate": 0},
                "months": [], "month": "",
                "note": "No RIP data loaded yet. Run extract_rip.py and push CSVs."}

    if not month:
        month = months[0]["Month"]

    args: list = [month]
    conds = ["p.month = $1"]
    if brand:
        args.append(f"%{brand}%"); conds.append(f"p.brand ILIKE ${len(args)}")
    if q:
        args.append(f"%{q}%"); conds.append(f"(p.description ILIKE ${len(args)} OR p.upc ILIKE ${len(args)})")
    if supplier:
        args.append(f"%{supplier}%"); conds.append(f"COALESCE(s.supplier_name,'') ILIKE ${len(args)}")

    sql = f"""
      SELECT p.id, p.month AS "Month", p.upc AS "UPC", p.brand AS "Brand",
             p.description AS "Description", p.rip_code AS "RipCode",
             p.abg_sku AS "AbgSku",
             p.valid_from AS "ValidFrom", p.valid_to AS "ValidTo",
             p.tier1_unit AS "Tier1Unit", p.tier1_qty AS "Tier1Qty",
             p.tier1_rebate AS "Tier1Rebate",
             p.tier2_unit AS "Tier2Unit", p.tier2_qty AS "Tier2Qty",
             p.tier2_rebate AS "Tier2Rebate",
             p.comments AS "Comments",
             i.id AS "ItemID", i.quantity AS "OnHand",
             COALESCE(s.supplier_name,'') AS "Supplier"
      FROM rip_program p
      LEFT JOIN item i ON i.item_lookup_code = p.upc
      LEFT JOIN supplier s ON i.supplier_id = s.id
      WHERE {" AND ".join(conds)}
      ORDER BY p.brand, p.description
      LIMIT {int(limit)}
    """
    rows = await fetch(sql, *args)
    potential_rebate = sum(
        (float(r["Tier1Qty"] or 0) * float(r["Tier1Rebate"] or 0)) +
        (float(r["Tier2Qty"] or 0) * float(r["Tier2Rebate"] or 0))
        for r in rows
    )
    return {
        "rows": rows,
        "summary": {
            "programs": len(rows),
            "potential_rebate": potential_rebate,
        },
        "months": months,
        "month": month,
    }


@router.get("/rip-order-suggestions")
async def rip_order_suggestions(month: Optional[str] = None,
                                 supplier: Optional[str] = None,
                                 limit: int = 500, _=Depends(_u)):
    months = await _rip_months_available()
    if not months:
        return {"rows": [], "summary": {"lines": 0, "potential_rebate": 0},
                "months": [], "month": "",
                "note": "No RIP data loaded yet."}
    if not month:
        month = months[0]["Month"]
    args: list = [month, 180]
    conds = ["p.month = $1"]
    if supplier:
        args.append(f"%{supplier}%"); conds.append(f"COALESCE(s.supplier_name,'') ILIKE ${len(args)}")

    # For each RIP program in the chosen month, compute velocity-based
    # reorder advice — items below typical cover get flagged.
    sql = f"""
      WITH velocity AS (
        SELECT te.item_id, SUM(te.quantity)/180.0 AS daily_units
        FROM transaction_entry te
        WHERE te.transaction_time >= NOW() - make_interval(days => $2)
          AND te.quantity > 0
        GROUP BY te.item_id
      )
      SELECT p.id, p.upc AS "UPC", p.description AS "Description",
             p.brand AS "Brand", p.rip_code AS "RipCode",
             p.tier1_qty AS "Tier1Qty", p.tier1_rebate AS "Tier1Rebate",
             p.tier2_qty AS "Tier2Qty", p.tier2_rebate AS "Tier2Rebate",
             p.valid_from AS "ValidFrom", p.valid_to AS "ValidTo",
             i.id AS "ItemID", i.quantity AS "OnHand",
             COALESCE(s.supplier_name,'') AS "Supplier",
             COALESCE(v.daily_units, 0) AS "DailyUnits",
             CASE WHEN COALESCE(v.daily_units,0) > 0
                  THEN (i.quantity / (v.daily_units * 30))
                  ELSE NULL END AS "MoSNow",
             CASE WHEN COALESCE(v.daily_units,0) > 0
                  THEN GREATEST(p.tier1_qty,
                                CEIL(v.daily_units * 60 - i.quantity))
                  ELSE p.tier1_qty END AS "SuggestedQty",
             (p.tier1_qty * p.tier1_rebate) AS "ExpectedRebate"
      FROM rip_program p
      JOIN item i ON i.item_lookup_code = p.upc
      LEFT JOIN supplier s ON i.supplier_id = s.id
      LEFT JOIN velocity v ON v.item_id = i.id
      WHERE {" AND ".join(conds)}
        AND i.inactive = 0
      ORDER BY (p.tier1_qty * p.tier1_rebate) DESC NULLS LAST
      LIMIT {int(limit)}
    """
    rows = await fetch(sql, *args)
    return {
        "rows": rows,
        "summary": {
            "lines": len(rows),
            "potential_rebate": sum(float(r["ExpectedRebate"] or 0) for r in rows),
        },
        "months": months,
        "month": month,
    }


@router.get("/rip/optimize")
async def rip_optimize(month: Optional[str] = None, _=Depends(_u)):
    months = await _rip_months_available()
    if not months:
        return {"combos": [], "months": [], "month": "",
                "note": "No RIP data loaded yet."}
    if not month:
        month = months[0]["Month"]
    rows = await fetch("""
        SELECT c.id, c.combo_code AS "ComboCode", c.upc AS "UPC",
               c.brand AS "Brand", c.description AS "Description",
               c.qty_value AS "QtyItems", c.qty_unit AS "QtyUnit",
               c.fline_price AS "FlinePrice", c.combo_price AS "ComboPrice",
               c.total_savings AS "Savings",
               c.valid_from AS "ValidFrom", c.valid_to AS "ValidTo",
               i.id AS "ItemID", i.quantity AS "OnHand"
        FROM rip_combo c
        LEFT JOIN item i ON i.item_lookup_code = c.upc
        WHERE c.month = $1
        ORDER BY c.total_savings DESC NULLS LAST
        LIMIT 500
    """, month)
    return {
        "combos": rows,
        "summary": {
            "combos": len(rows),
            "total_savings": sum(float(r["Savings"] or 0) for r in rows),
        },
        "months": months,
        "month": month,
    }


@router.get("/rip-item/{item_id}")
async def rip_item_detail(item_id: int, _=Depends(_u)):
    item = await fetchrow("""
        SELECT i.id, i.item_lookup_code, i.description,
               i.quantity, i.cost, i.price,
               COALESCE(s.supplier_name,'') AS supplier
        FROM item i LEFT JOIN supplier s ON i.supplier_id = s.id
        WHERE i.id = $1
    """, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    upc = item["item_lookup_code"]
    programs = await fetch("""
        SELECT id, month AS "Month", brand AS "Brand", description AS "Description",
               rip_code AS "RipCode",
               tier1_unit AS "Tier1Unit", tier1_qty AS "Tier1Qty",
               tier1_rebate AS "Tier1Rebate",
               tier2_unit AS "Tier2Unit", tier2_qty AS "Tier2Qty",
               tier2_rebate AS "Tier2Rebate",
               valid_from AS "ValidFrom", valid_to AS "ValidTo"
        FROM rip_program WHERE upc = $1
        ORDER BY month DESC
    """, upc)
    combos = await fetch("""
        SELECT id, month AS "Month", combo_code AS "ComboCode",
               qty_value AS "QtyItems", qty_unit AS "QtyUnit",
               fline_price AS "FlinePrice", combo_price AS "ComboPrice",
               total_savings AS "Savings",
               valid_from AS "ValidFrom", valid_to AS "ValidTo"
        FROM rip_combo WHERE upc = $1
        ORDER BY month DESC
    """, upc)
    claims = await fetch("""
        SELECT id, po_number AS "PONumber", po_date AS "PODate",
               month AS "Month", rip_code AS "RipCode",
               tier_qualified AS "Tier",
               qty_ordered AS "Qty", rebate_amount AS "Rebate",
               status AS "Status", received_on AS "ReceivedOn",
               received_amount AS "ReceivedAmount", notes AS "Notes",
               expected_paid_before AS "DueBy"
        FROM rip_match WHERE upc = $1
        ORDER BY po_date DESC NULLS LAST
        LIMIT 100
    """, upc)
    return {"item": dict(item), "programs": programs,
            "combos": combos, "claims": claims}


@router.get("/rip/matches")
async def rip_matches(month: Optional[str] = None,
                       status: Optional[str] = None,
                       limit: int = 500, _=Depends(_u)):
    months = await _rip_months_available()
    if not months:
        return {"rows": [], "summary": {}, "months": [], "month": ""}
    if not month:
        month = months[0]["Month"]
    args: list = [month]
    conds = ["month = $1"]
    if status and status not in ("", "Any"):
        args.append(status); conds.append(f"status = ${len(args)}")
    rows = await fetch(f"""
        SELECT id, po_number AS "PONumber", po_date AS "PODate",
               upc AS "UPC", description AS "Description",
               supplier AS "Supplier", rip_code AS "RipCode",
               tier_qualified AS "Tier",
               qty_ordered AS "Qty", rebate_amount AS "Rebate",
               status AS "Status", received_on AS "ReceivedOn",
               received_amount AS "ReceivedAmount",
               expected_paid_before AS "DueBy"
        FROM rip_match
        WHERE {" AND ".join(conds)}
        ORDER BY po_date DESC NULLS LAST
        LIMIT {int(limit)}
    """, *args)
    by_status: dict[str, dict] = {}
    for r in rows:
        b = by_status.setdefault(r["Status"], {"Status": r["Status"], "Count": 0, "Rebate": 0})
        b["Count"] += 1
        b["Rebate"] += float(r["Rebate"] or 0)
    return {"rows": rows, "by_status": list(by_status.values()),
            "months": months, "month": month}


# ============================================================== #
# BUY OPTIMIZER (demo: shows current cost vs avg cost as savings hint)
# ============================================================== #

@router.post("/optimizer")
async def optimizer(payload: dict = Body(...), _=Depends(_u)):
    basket = payload.get("basket") or []
    out = []
    grand_total = 0.0
    grand_savings = 0.0
    for item in basket:
        upc = str(item.get("upc", ""))
        qty = float(item.get("qty", 0))
        if not upc or qty <= 0:
            continue
        info = await fetchrow("""
            SELECT i.id, i.item_lookup_code, i.description, i.cost, i.price,
                   COALESCE(s.supplier_name,'') AS supplier
            FROM item i LEFT JOIN supplier s ON i.supplier_id = s.id
            WHERE i.item_lookup_code = $1
        """, upc)
        if not info:
            continue
        avg = await fetchrow("""
            SELECT AVG(NULLIF(price,0)) AS p
            FROM purchase_order_entry
            WHERE item_id = $1
        """, info["id"])
        avg_cost = float((avg or {}).get("p") or 0) or float(info["cost"] or 0)
        cur_cost = float(info["cost"] or 0)
        line_total = qty * cur_cost
        savings = qty * max(0.0, avg_cost - cur_cost)
        grand_total += line_total
        grand_savings += savings
        out.append({"UPC": info["item_lookup_code"],
                    "Description": info["description"],
                    "Supplier": info["supplier"],
                    "Qty": qty,
                    "UnitCost": cur_cost,
                    "AvgPaid": avg_cost,
                    "LineTotal": line_total,
                    "EstSavings": savings})
    return {"basket": out,
            "totals": {"line_count": len(out),
                       "total": grand_total,
                       "savings": grand_savings}}


# ============================================================== #
# ITEM ANALYTICS — single item view
# ============================================================== #

@router.get("/analytics/item")
async def analytics_item(item_id: Optional[int] = None,
                          upc: Optional[str] = None,
                          months: int = 24,
                          granularity: str = "month",
                          _=Depends(_u)):
    target_id = item_id
    if target_id is None and upc:
        row = await fetchrow("SELECT id FROM item WHERE item_lookup_code = $1", upc)
        target_id = row["id"] if row else None
    if not target_id:
        top = await fetch("""
            SELECT i.id AS "ID", i.item_lookup_code AS "UPC", i.description AS "Description",
                   SUM(te.quantity * te.price) AS "Revenue",
                   SUM(te.quantity) AS "Units"
            FROM transaction_entry te
            JOIN item i ON te.item_id = i.id
            WHERE te.transaction_time >= NOW() - INTERVAL '180 days'
              AND te.quantity > 0
            GROUP BY i.id, i.item_lookup_code, i.description
            ORDER BY "Revenue" DESC NULLS LAST
            LIMIT 25
        """)
        return {"mode": "top", "top_items": top}

    item = await fetchrow("""
        SELECT i.id, i.item_lookup_code AS "UPC", i.description AS "Description",
               COALESCE(d.name,'') AS "Department",
               COALESCE(c.name,'') AS "Category",
               COALESCE(s.supplier_name,'') AS "Supplier",
               i.quantity AS "OnHand", i.cost AS "Cost", i.price AS "Price"
        FROM item i
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        LEFT JOIN supplier   s ON i.supplier_id   = s.id
        WHERE i.id = $1
    """, target_id)
    if not item:
        raise HTTPException(404, "Item not found")
    bucket = {
        "day":   "transaction_time::date",
        "week":  "date_trunc('week', transaction_time)::date",
        "month": "date_trunc('month', transaction_time)::date",
    }.get(granularity, "date_trunc('month', transaction_time)::date")
    series = await fetch(f"""
        SELECT {bucket} AS "Bucket",
               SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS "UnitsSold",
               SUM(CASE WHEN quantity < 0 THEN -quantity ELSE 0 END) AS "UnitsReceived",
               SUM(CASE WHEN quantity > 0 THEN quantity * price ELSE 0 END) AS "Revenue",
               AVG(CASE WHEN quantity > 0 THEN price END) AS "AvgSalePrice"
        FROM transaction_entry
        WHERE item_id = $1
          AND transaction_time >= NOW() - make_interval(months => $2)
        GROUP BY {bucket}
        ORDER BY {bucket}
    """, target_id, months)
    purchase_history = await fetch("""
        SELECT po.date_created::date AS "Bucket",
               poe.price AS "UnitCost"
        FROM purchase_order_entry poe
        JOIN purchase_order po ON poe.purchase_order_id = po.id
        WHERE poe.item_id = $1
          AND po.date_created >= NOW() - make_interval(months => $2)
        ORDER BY po.date_created
    """, target_id, months)
    return {"mode": "item", "item": item, "series": series,
            "purchase_history": purchase_history}


# ============================================================== #
# SALES ANALYTICS (4 sub-views: top sellers, weekly-yoy, movers, transactions)
# ============================================================== #

@router.get("/sales/top-sellers")
async def sales_top_sellers(months: int = 6, top: int = 25, _=Depends(_u)):
    rows = await fetch("""
        SELECT i.item_lookup_code AS "UPC", i.description AS "Description",
               COALESCE(d.name,'') AS "Department",
               SUM(te.quantity)             AS "Units",
               SUM(te.quantity * te.price)  AS "Revenue",
               SUM(te.quantity * (te.price - te.cost)) AS "GrossProfit"
        FROM transaction_entry te
        JOIN item i ON te.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        WHERE te.transaction_time >= NOW() - make_interval(months => $1)
          AND te.quantity > 0
        GROUP BY i.item_lookup_code, i.description, d.name
        ORDER BY "Revenue" DESC NULLS LAST
        LIMIT $2
    """, months, top)
    by_dept = await fetch("""
        SELECT COALESCE(d.name,'(none)') AS "Department",
               SUM(te.quantity * te.price) AS "Revenue",
               SUM(te.quantity) AS "Units"
        FROM transaction_entry te
        JOIN item i ON te.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        WHERE te.transaction_time >= NOW() - make_interval(months => $1)
          AND te.quantity > 0
        GROUP BY d.name
        ORDER BY "Revenue" DESC NULLS LAST
        LIMIT 15
    """, months)
    return {"rows": rows, "by_department": by_dept}


@router.get("/sales/weekly-yoy")
async def sales_weekly_yoy(weeks: int = 26, _=Depends(_u)):
    rows = await fetch("""
        SELECT date_trunc('week', transaction_time)::date AS "Week",
               EXTRACT(YEAR FROM transaction_time)::int AS "Year",
               SUM(quantity * price) AS "NetRevenue",
               COUNT(DISTINCT transaction_number) AS "Transactions"
        FROM transaction_entry
        WHERE transaction_time >= NOW() - make_interval(weeks => ($1 + 156))
        GROUP BY date_trunc('week', transaction_time), EXTRACT(YEAR FROM transaction_time)
        ORDER BY "Week"
    """, weeks)
    return {"rows": rows, "weeks": weeks}


@router.get("/sales/movers")
async def sales_movers(weeks: int = 12, top: int = 30, _=Depends(_u)):
    rows = await fetch("""
        WITH cur AS (
          SELECT te.item_id, SUM(te.quantity) AS units, SUM(te.quantity*te.price) AS rev
          FROM transaction_entry te
          WHERE te.transaction_time >= NOW() - make_interval(weeks => $1)
            AND te.quantity > 0
          GROUP BY te.item_id
        ),
        prev AS (
          SELECT te.item_id, SUM(te.quantity) AS units, SUM(te.quantity*te.price) AS rev
          FROM transaction_entry te
          WHERE te.transaction_time >= NOW() - make_interval(weeks => $1*2)
            AND te.transaction_time <  NOW() - make_interval(weeks => $1)
            AND te.quantity > 0
          GROUP BY te.item_id
        )
        SELECT i.item_lookup_code AS "UPC", i.description AS "Description",
               COALESCE(c.units, 0) AS "UnitsCur",
               COALESCE(p.units, 0) AS "UnitsPrev",
               (COALESCE(c.units,0) - COALESCE(p.units,0)) AS "Delta",
               CASE WHEN COALESCE(p.units,0) > 0
                    THEN (COALESCE(c.units,0) - p.units)*100.0 / p.units
                    ELSE NULL END AS "PctChange",
               COALESCE(c.rev, 0) AS "RevenueCur",
               CASE
                 WHEN COALESCE(p.units,0) = 0 AND COALESCE(c.units,0) > 0 THEN 'New'
                 WHEN COALESCE(c.units,0) = 0 AND COALESCE(p.units,0) > 0 THEN 'Dying'
                 WHEN COALESCE(c.units,0) > COALESCE(p.units,0) * 1.3       THEN 'Growing'
                 WHEN COALESCE(c.units,0) < COALESCE(p.units,0) * 0.7       THEN 'Slowing'
                 ELSE 'Stable'
               END AS "Category"
        FROM item i
        LEFT JOIN cur c ON i.id = c.item_id
        LEFT JOIN prev p ON i.id = p.item_id
        WHERE COALESCE(c.units,0) > 0 OR COALESCE(p.units,0) > 0
        ORDER BY ABS(COALESCE(c.rev,0) - COALESCE(p.rev,0)) DESC
        LIMIT $2
    """, weeks, top)
    return {"rows": rows, "weeks": weeks}


@router.get("/sales/transactions")
async def sales_transactions(days: int = 7, limit: int = 200, _=Depends(_u)):
    rows = await fetch("""
        SELECT t.transaction_number AS "TransactionNumber",
               t.time AS "Time",
               t.total AS "Total",
               COUNT(te.id)::int AS "Lines",
               SUM(te.quantity) AS "Units"
        FROM "transaction" t
        JOIN transaction_entry te ON te.transaction_number = t.transaction_number
        WHERE t.time >= NOW() - make_interval(days => $1)
        GROUP BY t.transaction_number, t.time, t.total
        ORDER BY t.time DESC
        LIMIT $2
    """, days, limit)
    return {"rows": rows}


# ============================================================== #
# PO SPEND ANALYSIS (5 sub-views inline)
# ============================================================== #

@router.get("/po-spend/overview")
async def po_spend_overview(months: int = 12, _=Depends(_u)):
    by_month = await fetch("""
        SELECT date_trunc('month', po.date_created)::date AS "Bucket",
               SUM(poe.quantity_ordered * poe.price) AS "Spend"
        FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        WHERE po.date_created >= NOW() - make_interval(months => $1)
        GROUP BY date_trunc('month', po.date_created)
        ORDER BY "Bucket"
    """, months)
    by_status = await fetch("""
        SELECT po.status::text AS "Status",
               COUNT(DISTINCT po.id)::int AS "POs",
               SUM(poe.quantity_ordered * poe.price) AS "Value"
        FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        WHERE po.date_created >= NOW() - make_interval(months => $1)
        GROUP BY po.status
        ORDER BY po.status
    """, months)
    top_suppliers = await fetch("""
        SELECT s.supplier_name AS "SupplierName",
               SUM(poe.quantity_ordered * poe.price) AS "Spend"
        FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
        WHERE po.date_created >= NOW() - make_interval(months => $1)
        GROUP BY s.supplier_name
        ORDER BY "Spend" DESC NULLS LAST
        LIMIT 10
    """, months)
    return {"by_month": by_month, "by_status": by_status, "top_suppliers": top_suppliers}


@router.get("/po-spend/categories")
async def po_spend_categories(months: int = 12, _=Depends(_u)):
    rows = await fetch("""
        SELECT COALESCE(d.name,'(none)') AS "Department",
               COALESCE(c.name,'(none)') AS "Category",
               SUM(poe.quantity_ordered * poe.price) AS "Spend",
               COUNT(DISTINCT i.id)::int AS "Skus"
        FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        LEFT JOIN department d ON i.department_id = d.id
        LEFT JOIN category   c ON i.category_id   = c.id
        WHERE po.date_created >= NOW() - make_interval(months => $1)
        GROUP BY d.name, c.name
        ORDER BY "Spend" DESC NULLS LAST
        LIMIT 30
    """, months)
    return {"rows": rows}


@router.get("/po-spend/items")
async def po_spend_items(months: int = 12, top: int = 30, _=Depends(_u)):
    rows = await fetch("""
        SELECT i.item_lookup_code AS "UPC", i.description AS "Description",
               COALESCE(s.supplier_name,'') AS "SupplierName",
               SUM(poe.quantity_ordered)::int AS "Units",
               SUM(poe.quantity_ordered * poe.price) AS "Spend",
               AVG(poe.price) AS "AvgCost"
        FROM purchase_order po
        JOIN purchase_order_entry poe ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        LEFT JOIN supplier s ON po.supplier_id = s.id
        WHERE po.date_created >= NOW() - make_interval(months => $1)
        GROUP BY i.item_lookup_code, i.description, s.supplier_name
        ORDER BY "Spend" DESC NULLS LAST
        LIMIT $2
    """, months, top)
    return {"rows": rows}


@router.get("/po-spend/item-price-drift")
async def po_spend_drift(upc: str, _=Depends(_u)):
    rows = await fetch("""
        SELECT po.date_created::date AS "Date",
               poe.price AS "UnitCost",
               poe.quantity_received AS "Qty"
        FROM purchase_order_entry poe
        JOIN purchase_order po ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        WHERE i.item_lookup_code = $1
        ORDER BY po.date_created
    """, upc)
    return {"rows": rows, "upc": upc}


# ============================================================== #
# COST ANALYSIS
# ============================================================== #

@router.get("/cost")
async def cost_analysis(upc: Optional[str] = None, months: int = 24, _=Depends(_u)):
    if not upc:
        movers = await fetch("""
            WITH per_item AS (
              SELECT i.id, i.item_lookup_code AS upc, i.description AS desc,
                     i.cost AS current_cost,
                     (SELECT poe.price FROM purchase_order_entry poe
                        JOIN purchase_order po ON poe.purchase_order_id = po.id
                        WHERE poe.item_id = i.id
                        ORDER BY po.date_created DESC LIMIT 1) AS latest_paid,
                     (SELECT AVG(poe.price) FROM purchase_order_entry poe
                        JOIN purchase_order po ON poe.purchase_order_id = po.id
                        WHERE poe.item_id = i.id
                          AND po.date_created >= NOW() - INTERVAL '365 days') AS avg_paid
              FROM item i
              WHERE i.inactive = 0
            )
            SELECT upc AS "UPC", "desc" AS "Description", current_cost AS "Cost",
                   latest_paid AS "LatestPaid", avg_paid AS "AvgPaid",
                   CASE WHEN avg_paid > 0 THEN (latest_paid - avg_paid)*100.0/avg_paid
                        ELSE NULL END AS "DriftPct"
            FROM per_item
            WHERE latest_paid IS NOT NULL AND avg_paid IS NOT NULL
              AND ABS(latest_paid - avg_paid) / NULLIF(avg_paid,0) > 0.05
            ORDER BY ABS(latest_paid - avg_paid) / NULLIF(avg_paid,0) DESC NULLS LAST
            LIMIT 50
        """)
        return {"mode": "movers", "rows": movers}
    series = await fetch("""
        SELECT po.date_created::date AS "Date",
               poe.price AS "UnitCost"
        FROM purchase_order_entry poe
        JOIN purchase_order po ON poe.purchase_order_id = po.id
        JOIN item i ON poe.item_id = i.id
        WHERE i.item_lookup_code = $1
          AND po.date_created >= NOW() - make_interval(months => $2)
        ORDER BY po.date_created
    """, upc, months)
    cur = await fetchrow("""
        SELECT i.cost AS "Cost", i.price AS "Price"
        FROM item i WHERE i.item_lookup_code = $1
    """, upc)
    return {"mode": "item", "series": series, "current": cur}


# ============================================================== #
# PRICING ANALYTICS
# ============================================================== #

@router.get("/pricing")
async def pricing(upc: Optional[str] = None, months: int = 12, _=Depends(_u)):
    if not upc:
        rows = await fetch("""
            WITH per_item AS (
              SELECT i.id, i.item_lookup_code AS upc, i.description AS desc,
                     i.cost AS cost, i.price AS price,
                     (SELECT AVG(price) FROM transaction_entry
                       WHERE item_id = i.id AND quantity > 0
                         AND transaction_time >= NOW() - INTERVAL '180 days') AS avg_sale_price,
                     (SELECT COUNT(*) FROM transaction_entry
                       WHERE item_id = i.id AND quantity > 0
                         AND price < i.price * 0.95
                         AND transaction_time >= NOW() - INTERVAL '180 days') AS promo_txns,
                     (SELECT COUNT(*) FROM transaction_entry
                       WHERE item_id = i.id AND quantity > 0
                         AND transaction_time >= NOW() - INTERVAL '180 days') AS all_txns
              FROM item i WHERE i.inactive = 0
            )
            SELECT upc AS "UPC", "desc" AS "Description",
                   cost AS "Cost", price AS "Price",
                   avg_sale_price AS "AvgSold",
                   CASE WHEN price > 0 THEN (price - cost)*100.0 / price ELSE NULL END AS "MarginPct",
                   CASE WHEN all_txns > 0 THEN promo_txns*100.0/all_txns ELSE 0 END AS "PromoPct"
            FROM per_item
            WHERE all_txns > 0
            ORDER BY all_txns DESC
            LIMIT 100
        """)
        return {"mode": "list", "rows": rows}
    series = await fetch("""
        SELECT date_trunc('week', transaction_time)::date AS "Week",
               AVG(price) AS "AvgSold",
               COUNT(*) AS "Txns"
        FROM transaction_entry
        WHERE item_id = (SELECT id FROM item WHERE item_lookup_code = $1)
          AND quantity > 0
          AND transaction_time >= NOW() - make_interval(months => $2)
        GROUP BY date_trunc('week', transaction_time)
        ORDER BY "Week"
    """, upc, months)
    cur = await fetchrow("""
        SELECT cost AS "Cost", price AS "Price"
        FROM item WHERE item_lookup_code = $1
    """, upc)
    return {"mode": "item", "series": series, "current": cur}


# ============================================================== #
# ADVISOR
# ============================================================== #

@router.get("/advisor/briefing")
async def advisor_briefing(_=Depends(_u)):
    briefing = await analytics.executive_dashboard()
    return briefing


@router.post("/advisor/ask")
async def advisor_ask(payload: dict = Body(...), _=Depends(_u)):
    q = str(payload.get("question", "")).strip()
    if not q:
        return {"answer": "Ask me a procurement question. Examples: 'What should I reorder?' or 'Who are my top customers?'"}
    ql = q.lower()
    if any(k in ql for k in ["reorder", "buy", "purchase", "order"]):
        recs = await analytics.reorder_recommendations(limit=10)
        return {"answer": f"Top {len(recs)} reorder candidates ranked by horizon need.",
                "data": recs}
    if any(k in ql for k in ["dead", "slow", "excess"]):
        rows = await analytics.dead_stock(limit=10)
        return {"answer": f"Top {len(rows)} items with capital tied up in non-moving stock.",
                "data": rows}
    if any(k in ql for k in ["customer", "rfm", "loyal"]):
        rows = await analytics.top_customers(top=10)
        return {"answer": f"Top {len(rows)} customers by spend.",
                "data": rows}
    if any(k in ql for k in ["supplier", "vendor"]):
        rows = await analytics.supplier_spend(top=10)
        return {"answer": f"Top {len(rows)} suppliers by COGS.", "data": rows}
    rows = await analytics.executive_dashboard()
    return {"answer": "Here's the executive snapshot — ask about reorder, dead stock, customers, or suppliers for drill-downs.",
            "data": rows}


# ============================================================== #
# DATA FILES + CONFIG
# ============================================================== #

@router.get("/data-files")
async def data_files(_=Depends(_u)):
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent.parent / "data"
    out = []
    if base.is_dir():
        for p in sorted(base.iterdir()):
            if p.is_file():
                st = p.stat()
                out.append({"name": p.name, "size": st.st_size,
                            "modified": datetime.fromtimestamp(st.st_mtime).isoformat()})
    return {"path": str(base), "files": out}


@router.get("/config")
async def get_config(_=Depends(_u)):
    import os
    counts = await fetchrow("""
        SELECT (SELECT COUNT(*) FROM item WHERE inactive = 0) AS active_skus,
               (SELECT COUNT(*) FROM "transaction") AS transactions,
               (SELECT COUNT(*) FROM transaction_entry) AS lines,
               (SELECT COUNT(*) FROM customer) AS customers,
               (SELECT COUNT(*) FROM purchase_order) AS pos,
               (SELECT seeded_at FROM seed_marker LIMIT 1) AS seeded_at
    """)
    return {
        "env": {
            "SYNTH_YEARS": os.environ.get("SYNTH_YEARS", "4"),
            "SYNTH_SEED": os.environ.get("SYNTH_SEED", ""),
            "AUTH_ALLOWED_EMAILS": os.environ.get("AUTH_ALLOWED_EMAILS", ""),
            "AUTH_ALLOWED_DOMAINS": os.environ.get("AUTH_ALLOWED_DOMAINS", ""),
            "AUTH_EMAIL_PROVIDER": os.environ.get("AUTH_EMAIL_PROVIDER", "none"),
            "DATABASE": os.environ.get("DATABASE_URL", "").split("@")[-1] if os.environ.get("DATABASE_URL") else "",
            "PUBLIC_URL": os.environ.get("PUBLIC_URL", ""),
        },
        "counts": dict(counts or {}),
        "policies": {
            "critical_mos_max": 0.25,
            "high_mos_max": 0.7,
            "moderate_mos_max": 2.0,
            "excess_mos_min": 12.0,
            "dead_mos_min": 24.0,
            "default_order_weeks": 12,
            "default_velocity_months": 18,
            "rtv_lookback_days": 180,
            "rtv_window_days": 90,
        },
    }
