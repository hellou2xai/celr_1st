"""
Single source of truth for the risk classifier.

Mirrors the rules used across procurement_app:
    Dead       — no sales velocity over the lookback window
    Excess     — months-of-stock (incl. open PO) > 12
    Critical   — current MoS <= 0.25 (≤ 1 week)
    High       — current MoS <= 0.7  (≤ 3 weeks)
    Moderate   — current MoS <= 2.0  (≤ 2 months)
    Healthy    — everything else

Two APIs:
    - sql_case(...)  -> emits a SQL CASE expression to embed in queries
    - classify(...)  -> Python classifier for already-computed numbers

Centralising it here means risk badges across the app stay consistent —
no more silently-divergent CASE clauses sprinkled across endpoints.
"""
from __future__ import annotations

from typing import Optional


CRITICAL_MAX = 0.25
HIGH_MAX     = 0.70
MODERATE_MAX = 2.00
EXCESS_MIN   = 12.0


def classify(mos_now: Optional[float],
             daily_units: Optional[float],
             mos_with_open_po: Optional[float] = None) -> str:
    """Classify a single SKU into a risk tier.

    Inputs may be None — we degrade gracefully.
    `mos_with_open_po` is optional; falls back to `mos_now` when absent.
    """
    if not daily_units or daily_units <= 0:
        return "Dead"
    projected = mos_with_open_po if mos_with_open_po is not None else mos_now
    if projected is not None and projected > EXCESS_MIN:
        return "Excess"
    if mos_now is None:
        return "Healthy"
    if mos_now <= CRITICAL_MAX:
        return "Critical"
    if mos_now <= HIGH_MAX:
        return "High"
    if mos_now <= MODERATE_MAX:
        return "Moderate"
    return "Healthy"


def action_for(risk: str, has_open_po: bool = False) -> str:
    """Operational suggestion paired with a risk label."""
    if risk == "Dead":     return "Delist"
    if risk == "Excess":   return "Cancel / RTV"
    if risk == "Critical": return "On PO — wait" if has_open_po else "Reorder NOW"
    if risk == "High":     return "Reorder soon"
    if risk == "Moderate": return "Watch"
    return "OK"


# --------------------------------------------------------------------------- #
# SQL helpers — every endpoint that wants a risk column should call this
# instead of hand-rolling the CASE clause.
# --------------------------------------------------------------------------- #

def sql_case(mos_now_expr: str,
             daily_units_expr: str,
             mos_with_open_po_expr: Optional[str] = None) -> str:
    """Emit a SQL CASE expression that classifies risk.

    Pass column or expression names, e.g.:
        risk_expr = sql_case(
            mos_now_expr      = "(i.quantity - i.quantity_committed) / NULLIF(v.daily_units * 30, 0)",
            daily_units_expr  = "v.daily_units",
            mos_with_open_po_expr = "(i.quantity - i.quantity_committed + pl.qty_open) / NULLIF(v.daily_units * 30, 0)",
        )
    The result is a snippet you embed directly in a SELECT clause.
    """
    proj = mos_with_open_po_expr or mos_now_expr
    return f"""
    CASE
      WHEN COALESCE({daily_units_expr}, 0) = 0                THEN 'Dead'
      WHEN ({proj}) > {EXCESS_MIN}                            THEN 'Excess'
      WHEN ({mos_now_expr}) <= {CRITICAL_MAX}                 THEN 'Critical'
      WHEN ({mos_now_expr}) <= {HIGH_MAX}                     THEN 'High'
      WHEN ({mos_now_expr}) <= {MODERATE_MAX}                 THEN 'Moderate'
      ELSE 'Healthy'
    END
    """.strip()


def sql_action(risk_expr: str, has_open_po_expr: str = "false") -> str:
    """SQL counterpart to `action_for`. Pass a column / expression that
    yields a risk tier string."""
    return f"""
    CASE {risk_expr}
      WHEN 'Dead'     THEN 'Delist'
      WHEN 'Excess'   THEN 'Cancel / RTV'
      WHEN 'Critical' THEN CASE WHEN {has_open_po_expr} THEN 'On PO — wait' ELSE 'Reorder NOW' END
      WHEN 'High'     THEN 'Reorder soon'
      WHEN 'Moderate' THEN 'Watch'
      ELSE 'OK'
    END
    """.strip()
