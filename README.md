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
```

Current backtest accuracy: **94.0%** (30-day holdout, target was 90%+).
