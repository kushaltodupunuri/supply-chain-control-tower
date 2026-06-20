# Supply Chain Control Tower

An 8-week build of an end-to-end supply chain planning system: demand forecasting,
procurement, production, inventory, logistics, real-time disruption tracking,
risk/what-if scenarios, and financial performance — surfaced in a Streamlit dashboard.

## Status

**Week 1 — Demand Forecasting:** done.

- `src/generate_data.py` — synthetic sales history (2 years, daily), suppliers, inventory, and
  factory status data.
- `src/demand_forecast.py` — Prophet model (promotion/price/weather as regressors), 30-day holdout
  backtest, and a 30-day forward forecast.

**Week 2 — Procurement + Production:** done.

- `src/procurement.py` — PuLP linear program: minimizes supplier cost to meet the Week 1 demand
  forecast, capped at 70% of the order per supplier so one delayed/defective supplier can't stall
  the whole order.
- `src/production.py` — checks the in-house factory's available capacity (capacity minus existing
  bookings) against demand. Any shortfall is filled by the cheapest combination of levers in order:
  existing finished-goods inventory (free) -> overtime (capped, cheap) -> outsourced contractor
  (uncapped, most expensive).

**Week 3 — Inventory + Logistics:** done.

- `src/inventory.py` — network safety stock sized from demand variability and the procurement
  plan's weighted supplier lead time, held centrally at the factory (cheapest). Each forward
  DC/store gets only the cycle stock it needs to cover its *own* transit time from the factory
  (e.g. Asia's 18-day ocean transit vs. North America's 3-day truck transit), not a flat
  one-size-fits-all buffer. Result: today's stock is under-positioned for the overseas DCs' real
  transit times - this surfaces as a real cost increase, not a saving, which is reported honestly
  rather than tuned to match a "saves money" narrative.
- `src/logistics.py` — splits demand into per-region order volume, compares shipping every order
  individually against batching into full containers, and for each region's leftover units, picks
  whichever is cheaper: an LTL shipment or rounding up to one more container.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
python src/generate_data.py      # generates data/*.csv
python src/demand_forecast.py    # backtests, then writes outputs/demand_forecast.csv
python src/procurement.py        # writes outputs/procurement_plan.csv
python src/production.py         # writes outputs/production_plan_summary.csv + _allocation.csv
python src/inventory.py          # writes outputs/inventory_plan.csv
python src/logistics.py          # writes outputs/logistics_plan.csv
```

Current backtest accuracy: **94.0%** (30-day holdout, target was 90%+).
Logistics consolidation saves **~$26.5K** vs. shipping every order individually.
