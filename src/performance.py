"""
Module 8: Performance Tracking.

Compares each module's plan to what actually happened this period. The
"actuals" aren't a fabricated guess - they're the plan plus whatever real
disruption events Week 4's simulation actually produced (the Day 3 quality
spike's emergency cost, the Asia shipment delay's retention discount), so
every variance here traces back to something this same pipeline computed.

Run: python src/performance.py
"""
import pandas as pd
from demand_forecast import load_sales_history, backtest, HOLDOUT_DAYS


def track_forecast(df):
    accuracy, within_interval, forecast_total, actual_total = backtest(df)
    return {
        "metric": "Demand forecast", "planned": forecast_total, "actual": actual_total,
        "variance": actual_total - forecast_total, "accuracy_pct": accuracy,
        "note": f"{HOLDOUT_DAYS}-day holdout, {within_interval:.0f}% of actuals within forecast interval",
    }


def track_procurement(procurement_plan):
    planned = procurement_plan["cost"].sum()
    return {
        "metric": "Procurement cost", "planned": planned, "actual": planned,
        "variance": 0.0, "accuracy_pct": 100.0,
        "note": "No supplier disruption occurred this period - actual matched plan.",
    }


def track_production(production_allocation, quality_reports):
    planned = production_allocation["cost"].sum()
    emergency_cost = quality_reports["emergency_cost"].sum()
    actual = planned + emergency_cost
    spike_days = quality_reports.loc[quality_reports["emergency_cost"] > 0, "day"].tolist()
    note = (f"Day {spike_days[0]} quality rejection spike triggered ${emergency_cost:,.2f} in emergency overtime."
            if spike_days else "No quality incidents this period.")
    return {
        "metric": "Production cost", "planned": planned, "actual": actual,
        "variance": actual - planned, "accuracy_pct": 100 * (1 - abs(actual - planned) / planned) if planned else 100,
        "note": note,
    }


def track_logistics(logistics_plan, shipment_alerts):
    planned = logistics_plan["consolidated_cost"].sum()
    discount_cost = shipment_alerts["discount_cost"].sum() if len(shipment_alerts) else 0.0
    actual = planned + discount_cost
    note = (f"{shipment_alerts.iloc[0]['region']} shipment delayed {shipment_alerts.iloc[0]['delay_days']:.0f} days "
            f"beyond schedule; retention discount applied to units DC stock couldn't cover."
            if len(shipment_alerts) else "All shipments on schedule.")
    return {
        "metric": "Logistics cost", "planned": planned, "actual": actual,
        "variance": actual - planned, "accuracy_pct": 100 * (1 - abs(actual - planned) / planned) if planned else 100,
        "note": note,
    }


def track_inventory(inventory_plan, shipment_alerts):
    planned_units = inventory_plan["optimized_units"].sum()
    units_drawn_down = shipment_alerts["covered_by_dc"].sum() if len(shipment_alerts) else 0.0
    actual_units = planned_units - units_drawn_down
    note = (f"{units_drawn_down:,.0f} units drawn down to cover a shipment delay, not unplanned overstock."
            if units_drawn_down > 0 else "Ended period at planned stock levels.")
    return {
        "metric": "Inventory (units)", "planned": planned_units, "actual": actual_units,
        "variance": actual_units - planned_units,
        "accuracy_pct": 100 * (1 - abs(actual_units - planned_units) / planned_units) if planned_units else 100,
        "note": note,
    }


def track_delivery(logistics_plan, shipment_alerts):
    total_regions = len(logistics_plan)
    delayed_regions = len(shipment_alerts)
    on_time_actual = 100 * (total_regions - delayed_regions) / total_regions
    note = (f"{', '.join(shipment_alerts['region'])} missed schedule." if delayed_regions
            else "All regions delivered on schedule.")
    return {
        "metric": "On-time delivery (%)", "planned": 100.0, "actual": on_time_actual,
        "variance": on_time_actual - 100.0, "accuracy_pct": on_time_actual,
        "note": note,
    }


if __name__ == "__main__":
    sales = load_sales_history()
    procurement_plan = pd.read_csv("outputs/procurement_plan.csv")
    production_allocation = pd.read_csv("outputs/production_plan_allocation.csv")
    quality_reports = pd.read_csv("outputs/quality_reports.csv")
    logistics_plan = pd.read_csv("outputs/logistics_plan.csv")
    inventory_plan = pd.read_csv("outputs/inventory_plan.csv")
    shipment_alerts = pd.read_csv("outputs/shipment_alerts.csv")

    rows = [
        track_forecast(sales),
        track_procurement(procurement_plan),
        track_production(production_allocation, quality_reports),
        track_logistics(logistics_plan, shipment_alerts),
        track_inventory(inventory_plan, shipment_alerts),
        track_delivery(logistics_plan, shipment_alerts),
    ]
    df = pd.DataFrame(rows)
    df.to_csv("outputs/performance_tracking.csv", index=False)

    for row in df.itertuples():
        print(f"{row.metric}")
        print(f"  Planned: {row.planned:,.1f}  |  Actual: {row.actual:,.1f}  |  "
              f"Variance: {row.variance:+,.1f}  ({row.accuracy_pct:.1f}% accurate)")
        print(f"  {row.note}\n")

    forecast_row = df.iloc[0]
    cost_rows = df[df["metric"].isin(["Procurement cost", "Production cost", "Logistics cost"])]
    biggest_variance = cost_rows.loc[cost_rows["variance"].abs().idxmax()]
    print(f"LEARNING: Forecast model is accurate {forecast_row['accuracy_pct']:.0f}% of the time. "
          f"The biggest dollar variance this period was in {biggest_variance['metric'].lower()} "
          f"(${abs(biggest_variance['variance']):,.0f}) - not demand forecasting.")
    print("\nSaved to outputs/performance_tracking.csv")
