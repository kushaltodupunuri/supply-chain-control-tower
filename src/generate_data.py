"""
Generates synthetic supply chain data for Module 1 (Demand Forecasting):
- sales_history.csv: daily unit sales with seasonality, promotions, weather, price
- suppliers.csv: supplier cost/capacity/lead-time profile (used by later modules)
- inventory.csv: current on-hand inventory by location (used by later modules)

Run: python src/generate_data.py
"""
import numpy as np
import pandas as pd

np.random.seed(42)

OUT_DIR = "data"


def generate_sales_history(days=730, start="2024-01-01"):
    dates = pd.date_range(start=start, periods=days, freq="D")

    baseline = 1_300  # ~40,000/month average
    trend = np.linspace(0, 150, days)  # slow growth over 2 years

    day_of_year = dates.dayofyear.to_numpy()
    yearly_seasonality = 250 * np.sin(2 * np.pi * (day_of_year - 80) / 365.25)

    weekday = dates.dayofweek.to_numpy()
    weekly_seasonality = np.where(weekday >= 5, 180, 0)  # weekend boost

    avg_temp = 60 + 20 * np.sin(2 * np.pi * (day_of_year - 80) / 365.25) + np.random.normal(0, 4, days)
    weather_effect = (avg_temp - 60) * 6  # warmer weather -> more T-shirt sales

    price = np.full(days, 12.99)
    promotion_flag = np.zeros(days, dtype=int)
    rng = np.random.default_rng(42)
    promo_starts = rng.choice(np.arange(10, days - 10), size=days // 45, replace=False)
    for s in promo_starts:
        length = rng.integers(3, 8)
        promotion_flag[s:s + length] = 1
        price[s:s + length] = 12.99 * 0.85  # 15% off during promo

    price_change_days = rng.choice(np.arange(0, days), size=days // 200, replace=False)
    for d in price_change_days:
        price[d:] = round(price[d:][0] * rng.uniform(0.95, 1.07), 2)

    price_effect = (12.99 - price) * 250  # cheaper price -> more sales
    promo_effect = promotion_flag * rng.normal(700, 100, days)

    noise = np.random.normal(0, 90, days)

    units_sold = (
        baseline + trend + yearly_seasonality + weekly_seasonality
        + weather_effect + price_effect + promo_effect + noise
    )
    units_sold = np.clip(units_sold, 200, None).round().astype(int)

    return pd.DataFrame({
        "date": dates,
        "units_sold": units_sold,
        "promotion_flag": promotion_flag,
        "avg_temp_f": avg_temp.round(1),
        "price": price.round(2),
    })


def generate_suppliers():
    return pd.DataFrame([
        {"supplier_id": "SUP-A", "name": "Supplier A", "unit_cost": 2.00, "lead_time_weeks": 6, "max_capacity_units": 35_000, "reliability_pct": 92},
        {"supplier_id": "SUP-B", "name": "Supplier B", "unit_cost": 2.30, "lead_time_weeks": 4, "max_capacity_units": 25_000, "reliability_pct": 97},
        {"supplier_id": "SUP-C", "name": "Supplier C", "unit_cost": 2.15, "lead_time_weeks": 5, "max_capacity_units": 20_000, "reliability_pct": 95},
    ])


def generate_inventory():
    return pd.DataFrame([
        {"location": "Factory Warehouse", "units_on_hand": 8_000, "holding_cost_per_unit_month": 1.00},
        {"location": "Asia DC", "units_on_hand": 2_000, "holding_cost_per_unit_month": 1.20},
        {"location": "Europe DC", "units_on_hand": 1_000, "holding_cost_per_unit_month": 1.30},
        {"location": "Stores", "units_on_hand": 3_000, "holding_cost_per_unit_month": 1.50},
    ])


if __name__ == "__main__":
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    sales = generate_sales_history()
    sales.to_csv(f"{OUT_DIR}/sales_history.csv", index=False)
    print(f"Wrote {OUT_DIR}/sales_history.csv ({len(sales)} rows)")
    print(sales.tail())

    suppliers = generate_suppliers()
    suppliers.to_csv(f"{OUT_DIR}/suppliers.csv", index=False)
    print(f"\nWrote {OUT_DIR}/suppliers.csv ({len(suppliers)} rows)")

    inventory = generate_inventory()
    inventory.to_csv(f"{OUT_DIR}/inventory.csv", index=False)
    print(f"\nWrote {OUT_DIR}/inventory.csv ({len(inventory)} rows)")
