# Supply Chain Control Tower

An 8-week build of an end-to-end supply chain planning system: demand forecasting,
procurement, production, inventory, logistics, real-time disruption tracking,
risk/what-if scenarios, and financial performance — surfaced in a Streamlit dashboard.

## Status

**Week 1 — Demand Forecasting:** done.

- `src/generate_data.py` — synthetic sales history (2 years, daily), suppliers, and inventory data.
- `src/demand_forecast.py` — Prophet model (promotion/price/weather as regressors), 30-day holdout
  backtest, and a 30-day forward forecast.

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
```

Current backtest accuracy: **94.0%** (30-day holdout, target was 90%+).
