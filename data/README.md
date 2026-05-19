# data/

These eight CSVs are the public-safe inputs that bootstrap the demo:

| File | Source | Sensitivity |
|---|---|---|
| `departments.csv` | Real WINEZONE | Public |
| `categories.csv` | Real WINEZONE | Public |
| `suppliers.csv` | Real WINEZONE | Public (per owner) |
| `items.csv` | Real WINEZONE | Public — item catalog, costs, prices |
| `item_velocity.csv` | Aggregated real metric | Aggregate only; no per-txn data |
| `month_seasonality.csv` | Aggregated real metric | Aggregate only |
| `dow_seasonality.csv` | Aggregated real metric | Aggregate only |
| `hour_distribution.csv` | Aggregated real metric | Aggregate only |
| `baseline.csv` | Aggregated real metric | Aggregate only (avg txns/day) |

Generate or refresh these by running:

```bash
cd ../extract && python extract_real_catalog.py
```

All transaction-level data, customers, cashiers, etc. are **synthesized**
at deploy time by `seed/seed.py` — nothing customer-private lives in this
folder.
