"""
Synthetic catalog fallback.

The full demo expects 9 CSVs in data/ produced by extract/extract_real_catalog.py
(run once against the WINEZONE SQL Server). When those CSVs aren't there
— typical on a fresh Render deploy before anyone has run the extractor —
this module materialises a plausible liquor-store catalog in their place
so the seed still completes.

Everything generated here is fake (Faker-based brand names, made-up
prices). Swap to the real catalog by running the extractor and pushing.
"""
from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Iterable

# ----------------------------------------------------------------------- #
# Hand-rolled domain shape for a liquor store
# ----------------------------------------------------------------------- #

DEPARTMENTS = [
    (1, "WINE"),
    (2, "BEER"),
    (3, "LIQUOR"),
    (4, "LIQUOR FRONT DESK"),
    (5, "MIXES"),
    (6, "TOBACCO"),
    (7, "SNACKS"),
    (8, "OTHER"),
]

CATEGORIES = [
    # id, name, dept_id, typical_cost_range, typical_size_tokens
    (1,  "RED - DOMESTIC",   1, (8,  22),  ["750ML", "1.5L"]),
    (2,  "RED - IMPORTED",   1, (12, 40),  ["750ML", "1.5L"]),
    (3,  "WHITE - DOMESTIC", 1, (8,  20),  ["750ML", "1.5L"]),
    (4,  "WHITE - IMPORTED", 1, (10, 30),  ["750ML", "1.5L"]),
    (5,  "ROSE",             1, (8,  20),  ["750ML"]),
    (6,  "SPARKLING",        1, (15, 75),  ["750ML", "1.5L"]),
    (7,  "DOMESTIC BEER",    2, (10, 28),  ["12PK", "24PK", "6PK"]),
    (8,  "IMPORTED BEER",    2, (14, 36),  ["12PK", "24PK", "6PK"]),
    (9,  "CRAFT BEER",       2, (12, 36),  ["6PK", "12PK", "4PK"]),
    (10, "COOLERS",          2, (12, 22),  ["8PK", "12PK", "4PK"]),
    (11, "RUM - DOMESTIC",   3, (10, 28),  ["750ML", "1L", "1.75L"]),
    (12, "RUM - IMPORTED",   3, (16, 32),  ["750ML", "1L", "1.75L"]),
    (13, "VODKA - DOMESTIC", 3, (8,  26),  ["750ML", "1L", "1.75L"]),
    (14, "VODKA - IMPORTED", 3, (14, 35),  ["750ML", "1L", "1.75L"]),
    (15, "WHISKEY",          3, (16, 60),  ["750ML", "1L", "1.75L"]),
    (16, "BOURBON",          3, (14, 50),  ["750ML", "1L", "1.75L"]),
    (17, "SCOTCH",           3, (22, 80),  ["750ML", "1L"]),
    (18, "TEQUILA",          3, (14, 45),  ["750ML", "1L", "1.75L"]),
    (19, "GIN",              3, (12, 30),  ["750ML", "1L", "1.75L"]),
    (20, "BRANDY",           3, (14, 38),  ["750ML", "1L"]),
    (21, "CORDIAL",          3, (12, 32),  ["750ML", "1L"]),
    (22, "RUM FD",           4, (1,   5),  ["50ML", "200ML"]),
    (23, "VODKA FD",         4, (1,   5),  ["50ML", "200ML"]),
    (24, "WHISKEY FD",       4, (1,   6),  ["50ML", "200ML"]),
    (25, "MIXES",            5, (1,   8),  ["1L", "1.75L"]),
    (26, "CIGARETTES",       6, (3,   9),  ["PACK", "CARTON"]),
    (27, "CIGARS",           6, (2,  18),  ["EACH", "BOX"]),
    (28, "CHIPS",            7, (1,   4),  ["BAG"]),
    (29, "NUTS",             7, (2,   8),  ["BAG", "CAN"]),
    (30, "MISC",             8, (1,  10),  ["EACH"]),
]

SUPPLIERS = [
    (1,  "ALLIED LIBERTY"),
    (2,  "ALLIED (MIKE)"),
    (3,  "ALLIED (DEWIS)"),
    (4,  "FEDWAY ASSOCIATES"),
    (5,  "LOS ANDES WINE CO"),
    (6,  "REPUBLIC NATIONAL"),
    (7,  "SOUTHERN GLAZERS"),
    (8,  "BREAKTHRU BEVERAGE"),
    (9,  "OPICI WINE GROUP"),
    (10, "EMPIRE MERCHANTS"),
    (11, "MARTIGNETTI"),
    (12, "RNDC"),
    (13, "INVENTORY ADJUSTMENTS"),  # phantom, used by some legacy items
]

# Brand pools per category-family — kept generic enough not to claim real
# trademark associations.
BRAND_POOLS = {
    "wine_red":     ["VINEYARD HEIGHTS", "OAKBROOK", "CRIMSON ESTATES", "RED ROCK",
                     "NORTH RIDGE", "STONE GATE", "DUSK VALLEY", "TIMBER LANE",
                     "CANYON CREST", "MERIDIAN", "PINNACLE", "EBONY HOUSE"],
    "wine_white":   ["SILVER SPRINGS", "PEARL COAST", "RIVER BLUFF", "WHITE PINE",
                     "GOLDEN BAY", "SUNSET POINT", "EVERGREEN", "WINDWARD",
                     "BRIGHT MEADOW", "CLEAR LAKE", "MARBLE HILL"],
    "wine_other":   ["TWIN PEAKS", "AURORA", "RIVERSIDE", "ELM HOUSE", "GRANITE PEAK"],
    "beer":         ["IRON HORSE", "PILSNER PRIME", "AMBER CITY", "OLD HARBOR",
                     "BLACKWATER", "GRAINSTONE", "BEAR FOOT", "TWIN STACK",
                     "RIPCURRENT", "TIMBER WOLF", "HEATHWICK", "STONEBRIDGE"],
    "rum":          ["ISLAND CROWN", "TROPICANA GOLD", "PALM BAY", "REEF BAY",
                     "COVE LINE", "SUGAR CANE", "PORT ROYAL", "CAPTAIN'S RESERVE"],
    "vodka":        ["TUNDRA", "ICE CASTLE", "ARCTIC SHIELD", "POLAR LINE",
                     "WHITE FLAG", "GLACIER", "SILVER FROST", "NORTHWIND"],
    "whiskey":      ["BLACK BARREL", "RYE & OAK", "OLD KEYSTONE", "STONEBROOK",
                     "BIRCH HOLLOW", "COPPER STILL", "MILLERTON", "RIDGEPOST"],
    "tequila":      ["AGAVE SUN", "CACTUS BLOOM", "DESERT LINE", "EL VALLE",
                     "MEZA REAL", "BLUE AGAVE", "OAXACA PRIME"],
    "gin":          ["JUNIPER FIELD", "BOTANIC LANE", "PINE PRESS", "ELDERWICK",
                     "ALPINE STILL", "HEATHGATE"],
    "brandy":       ["FRENCH OAK", "VINTAGE COURT", "AMBER CASK", "ROSE HOUSE"],
    "liqueur":      ["AMARO ROSSO", "VELVET HARBOR", "BLOOM & BERRY",
                     "MIDNIGHT ROSE", "ORCHARD CRESCENT"],
    "fd":           ["TROPI SHOTS", "QUICK POUR", "MIX-N-GO"],
    "mixes":        ["BARTENDER'S CHOICE", "ZESTLINE", "REFRESH CO"],
    "tobacco":      ["TRIPLE CROWN", "GOLDLEAF", "BLUEPRINT", "MERIDIAN STATE"],
    "snacks":       ["CRUNCH HOUSE", "GOLDEN HARVEST", "SNACKWICK"],
}


def _brand_pool_for(cat_name: str) -> list[str]:
    n = cat_name.lower()
    if "red" in n or "rose" in n or "sparkling" in n: return BRAND_POOLS["wine_red"]
    if "white" in n: return BRAND_POOLS["wine_white"]
    if "rum fd" in n: return BRAND_POOLS["fd"]
    if "vodka fd" in n: return BRAND_POOLS["fd"]
    if "whiskey fd" in n: return BRAND_POOLS["fd"]
    if "rum" in n: return BRAND_POOLS["rum"]
    if "vodka" in n: return BRAND_POOLS["vodka"]
    if "whiskey" in n or "bourbon" in n or "scotch" in n: return BRAND_POOLS["whiskey"]
    if "tequila" in n: return BRAND_POOLS["tequila"]
    if "gin" in n: return BRAND_POOLS["gin"]
    if "brandy" in n: return BRAND_POOLS["brandy"]
    if "cordial" in n: return BRAND_POOLS["liqueur"]
    if "beer" in n or "coolers" in n: return BRAND_POOLS["beer"]
    if "mix" in n: return BRAND_POOLS["mixes"]
    if "cigarette" in n or "cigar" in n: return BRAND_POOLS["tobacco"]
    if "chip" in n or "nut" in n: return BRAND_POOLS["snacks"]
    return BRAND_POOLS["wine_other"]


# ----------------------------------------------------------------------- #
# CSV writers
# ----------------------------------------------------------------------- #

def write_csv(path: Path, header: list[str], rows: Iterable[Iterable]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        n = 0
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def generate(data_dir: Path, seed: int = 20260518) -> None:
    """Write the 9 catalog CSVs into data_dir using a deterministic seed."""
    rng = random.Random(seed)
    out = data_dir
    out.mkdir(parents=True, exist_ok=True)

    write_csv(out / "departments.csv", ["id", "name"], DEPARTMENTS)
    write_csv(out / "categories.csv",  ["id", "name"], [(c[0], c[1]) for c in CATEGORIES])
    write_csv(out / "suppliers.csv",   ["id", "supplier_name"], SUPPLIERS)

    # Items
    item_rows = []
    velocity_rows = []
    item_id = 1
    for cat_id, cat_name, dept_id, (cost_lo, cost_hi), sizes in CATEGORIES:
        brands = _brand_pool_for(cat_name)
        # Roughly 25-50 SKUs per category to keep total ~1000
        n_skus = rng.randint(20, 55)
        for _ in range(n_skus):
            brand = rng.choice(brands)
            size = rng.choice(sizes)
            variety = rng.choice([
                "CLASSIC", "RESERVE", "SELECT", "PREMIUM", "PRIVATE",
                "LIGHT", "SMOOTH", "ESTATE", "AGED", "DOUBLE", "TRIPLE",
                "ORIGINAL", "GOLDEN", "SILVER", "BLACK", "RED",
                "BLUE", "WHITE", "VINTAGE", "CASK", "BARREL"
            ])
            description = f"{brand} {variety} {size}".strip()
            cost = round(rng.uniform(cost_lo, cost_hi), 2)
            markup = rng.uniform(1.15, 1.45)
            price = round(cost * markup, 2)
            supplier_id = rng.choice([s[0] for s in SUPPLIERS])
            qty = rng.randint(0, 60)
            committed = 0
            reorder_point = rng.randint(0, 6)
            restock_level = reorder_point + rng.randint(4, 18) if reorder_point > 0 else 0
            bin_loc = f"{rng.randint(1,9999)}"
            last_received = "2026-04-15"
            last_sold = "2026-05-10"
            inactive = 1 if rng.random() < 0.08 else 0
            taxable = 1
            date_created = "2022-01-01"
            upc = f"{rng.randint(80000000000, 89999999999)}"

            item_rows.append([
                item_id, upc, description, dept_id, cat_id, supplier_id,
                bin_loc, qty, committed, reorder_point, restock_level,
                cost, price, last_received, last_sold, "", "",
                inactive, taxable, date_created,
            ])

            # Velocity profile: avg daily units, returns rate, avg sold price.
            # Distribution roughly log-normal — most slow, a tail of fast.
            base_daily = max(0.0, rng.lognormvariate(-1.5, 1.2))
            base_daily *= 0.25 if inactive else 1.0
            velocity_rows.append([
                item_id, round(base_daily, 4),
                round(base_daily * 0.02, 4),  # returns
                price * rng.uniform(0.92, 1.0),
            ])
            item_id += 1

    write_csv(out / "items.csv", [
        "id", "item_lookup_code", "description", "department_id", "category_id",
        "supplier_id", "bin_location", "quantity", "quantity_committed",
        "reorder_point", "restock_level", "cost", "price",
        "last_received", "last_sold", "last_counted", "last_updated",
        "inactive", "taxable", "date_created",
    ], item_rows)

    write_csv(out / "item_velocity.csv", [
        "item_id", "avg_daily_units", "avg_daily_returns", "avg_sold_price"
    ], velocity_rows)

    # Seasonality — plausible liquor store curves.
    # Months: peak in Dec, dip in Jan/Feb, bump in summer.
    month_multipliers = {
        1:  0.85, 2:  0.82, 3:  0.92, 4:  0.95, 5:  1.05, 6:  1.10,
        7:  1.15, 8:  1.18, 9:  1.05, 10: 1.05, 11: 1.10, 12: 1.40,
    }
    write_csv(out / "month_seasonality.csv", ["month_of_year", "multiplier"],
              [(m, round(v, 4)) for m, v in month_multipliers.items()])

    # Day-of-week: SQL Server convention 1=Sun..7=Sat; Fri/Sat highest.
    dow_multipliers = {1: 0.85, 2: 0.80, 3: 0.85, 4: 0.95,
                       5: 1.10, 6: 1.30, 7: 1.35}
    write_csv(out / "dow_seasonality.csv", ["day_of_week", "multiplier"],
              [(d, round(v, 4)) for d, v in dow_multipliers.items()])

    # Hour distribution: closed 02:00-09:00, peak 17:00-20:00.
    hour_dist = {
        0: 0.005, 1: 0.002, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0,
        7: 0, 8: 0.01, 9: 0.02, 10: 0.03, 11: 0.04, 12: 0.05,
        13: 0.05, 14: 0.06, 15: 0.07, 16: 0.08, 17: 0.10,
        18: 0.12, 19: 0.13, 20: 0.10, 21: 0.07, 22: 0.04,
        23: 0.02,
    }
    s = sum(hour_dist.values()) or 1
    hour_dist = {h: v / s for h, v in hour_dist.items()}
    write_csv(out / "hour_distribution.csv", ["hour_of_day", "share"],
              [(h, round(v, 6)) for h, v in hour_dist.items()])

    # Baseline txn/day — pick a plausible liquor store volume.
    write_csv(out / "baseline.csv", ["metric", "value"],
              [("avg_txns_per_day", 420)])


def ensure_present(data_dir: Path, seed: int = 20260518) -> bool:
    """If items.csv is missing, populate the entire catalog. Returns True
    if synthetic catalog was generated (False if real CSVs were found)."""
    if (data_dir / "items.csv").exists():
        return False
    print(f"[synthetic_catalog] data/items.csv not found — generating fallback catalog into {data_dir}")
    generate(data_dir, seed)
    return True
