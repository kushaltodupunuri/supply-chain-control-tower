"""
Module 5: What-If Simulator.

Re-runs the actual procurement, production, and safety-stock logic from
Weeks 1-3 with perturbed inputs (demand, raw-material price, and supplier
lead time), instead of approximating their impact separately. This is the
same function (`run_scenario`) a future Streamlit slider would call - move
the sliders, get this same comparison back.

Run: python src/whatif.py
"""
import math
import pandas as pd
from procurement import plan_procurement
from production import plan_production

SERVICE_LEVEL_Z = 1.65


def run_scenario(baseline_demand, suppliers, factory, inventory, daily_demand_std, baseline_lead_time_days,
                  demand_pct=0, price_pct=0, lead_time_pct=0):
    adjusted_demand = baseline_demand * (1 + demand_pct / 100)

    adjusted_suppliers = suppliers.copy()
    adjusted_suppliers["unit_cost"] = adjusted_suppliers["unit_cost"] * (1 + price_pct / 100)

    procurement_plan = plan_procurement(adjusted_demand, adjusted_suppliers)
    production_plan = plan_production(adjusted_demand, factory, inventory)

    adjusted_lead_time_days = baseline_lead_time_days * (1 + lead_time_pct / 100)
    safety_stock = math.ceil(SERVICE_LEVEL_Z * daily_demand_std * math.sqrt(adjusted_lead_time_days))

    total_cost = procurement_plan["cost"].sum() + sum(item["cost"] for item in production_plan["allocation"])
    unmet_units = production_plan["unmet_units"]
    service_level = (adjusted_demand - unmet_units) / adjusted_demand * 100

    return {
        "demand": adjusted_demand,
        "total_cost": total_cost,
        "unmet_units": unmet_units,
        "service_level": service_level,
        "safety_stock": safety_stock,
    }


if __name__ == "__main__":
    forecast = pd.read_csv("outputs/demand_forecast.csv")
    baseline_demand = forecast["yhat"].sum()

    suppliers = pd.read_csv("data/suppliers.csv")
    factory = pd.read_csv("data/factory_status.csv")
    inventory = pd.read_csv("data/inventory.csv")
    sales = pd.read_csv("data/sales_history.csv")
    daily_demand_std = sales["units_sold"].std()

    procurement_plan = plan_procurement(baseline_demand, suppliers)
    baseline_lead_time_days = (
        (procurement_plan["units_ordered"] * procurement_plan["lead_time_weeks"]).sum()
        / procurement_plan["units_ordered"].sum() * 7
    )

    common = dict(baseline_demand=baseline_demand, suppliers=suppliers, factory=factory, inventory=inventory,
                  daily_demand_std=daily_demand_std, baseline_lead_time_days=baseline_lead_time_days)

    baseline = run_scenario(**common)

    scenarios = [
        ("Baseline", {}),
        ("Demand +20% (peak season)", {"demand_pct": 20}),
        ("Demand -20% (slowdown)", {"demand_pct": -20}),
        ("Lead time +50% (port congestion)", {"lead_time_pct": 50}),
        ("Raw material price +15%", {"price_pct": 15}),
        ("Worst case: demand +20% AND lead time +50%", {"demand_pct": 20, "lead_time_pct": 50}),
        ("Demand +70% (viral spike - exceeds every lever)", {"demand_pct": 70}),
    ]

    rows = []
    for label, overrides in scenarios:
        result = run_scenario(**common, **overrides)
        rows.append({"scenario": label, **result})

    df = pd.DataFrame(rows)
    df["cost_delta_vs_baseline"] = df["total_cost"] - baseline["total_cost"]
    df.to_csv("outputs/whatif_scenarios.csv", index=False)

    print(f"Baseline: {baseline['demand']:,.0f} units, ${baseline['total_cost']:,.2f} cost, "
          f"{baseline['service_level']:.1f}% service level, {baseline['safety_stock']:,.0f} safety stock\n")

    for row in df.itertuples():
        print(f"{row.scenario}")
        print(f"  Demand: {row.demand:,.0f} units | Cost: ${row.total_cost:,.2f} "
              f"({row.cost_delta_vs_baseline:+,.2f} vs baseline)")
        print(f"  Service level: {row.service_level:.1f}%"
              + (f" | UNMET: {row.unmet_units:,.0f} units" if row.unmet_units > 0 else "")
              + f" | Safety stock needed: {row.safety_stock:,.0f}\n")

    print("Saved to outputs/whatif_scenarios.csv")
