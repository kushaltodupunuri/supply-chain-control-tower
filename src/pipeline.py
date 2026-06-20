"""
Runs every module from Weeks 1-5 in order and returns the resulting
dataframes in memory, so the Streamlit dashboard doesn't have to shell out
to ten separate scripts. Each step still writes its CSV to outputs/ as a
side effect, so the file-based artifacts stay identical to running the
scripts by hand.
"""
import pandas as pd

from generate_data import (
    generate_sales_history, generate_suppliers, generate_factory_status,
    generate_regional_demand, generate_inventory,
)
from demand_forecast import build_model, backtest, forecast_next_period, REGRESSORS, HOLDOUT_DAYS
from procurement import plan_procurement
from production import plan_production
from inventory import plan_inventory
from logistics import plan_logistics
from risk import (
    scenario_supplier_failure, scenario_factory_outbreak,
    scenario_demand_drop, scenario_port_delay,
)
from disruption import simulate_quality_reports, emergency_allocation, check_shipment_delays
from whatif import run_scenario
from performance import (
    track_forecast, track_procurement, track_production,
    track_logistics, track_inventory, track_delivery,
)
from finance import compare_procurement, compare_production, compare_logistics, compare_inventory


def run_full_pipeline():
    sales = generate_sales_history()
    suppliers = generate_suppliers()
    factory = generate_factory_status()
    regional_demand = generate_regional_demand()
    current_inventory = generate_inventory()

    sales.to_csv("data/sales_history.csv", index=False)
    suppliers.to_csv("data/suppliers.csv", index=False)
    factory.to_csv("data/factory_status.csv", index=False)
    regional_demand.to_csv("data/regional_demand.csv", index=False)
    current_inventory.to_csv("data/inventory.csv", index=False)

    # Week 1 - Demand Forecasting
    forecast_input = sales.rename(columns={"date": "ds", "units_sold": "y"})
    accuracy, within_interval, backtest_forecast_total, backtest_actual_total = backtest(forecast_input)
    forecast = forecast_next_period(forecast_input)
    forecast.to_csv("outputs/demand_forecast.csv", index=False)
    total_demand = forecast["yhat"].sum()

    # Week 2 - Procurement + Production
    procurement_plan = plan_procurement(total_demand, suppliers)
    procurement_plan.to_csv("outputs/procurement_plan.csv", index=False)

    production_plan = plan_production(total_demand, factory, current_inventory)
    production_allocation = pd.DataFrame(production_plan["allocation"])
    if production_allocation.empty:
        production_allocation = pd.DataFrame(columns=["lever", "units", "unit_cost", "cost"])
    production_allocation.to_csv("outputs/production_plan_allocation.csv", index=False)

    # Week 3 - Inventory + Logistics
    daily_demand_std = sales["units_sold"].std()
    weighted_lead_time_days = (
        (procurement_plan["units_ordered"] * procurement_plan["lead_time_weeks"]).sum()
        / procurement_plan["units_ordered"].sum() * 7
    )
    inventory_plan, safety_stock = plan_inventory(
        total_demand, daily_demand_std, weighted_lead_time_days, regional_demand, current_inventory
    )
    inventory_plan.to_csv("outputs/inventory_plan.csv", index=False)

    logistics_plan = plan_logistics(total_demand, regional_demand)
    logistics_plan.to_csv("outputs/logistics_plan.csv", index=False)

    # Week 4 - Risk, Disruption, What-If
    avg_price = sales["price"].mean()
    avg_supplier_cost = (
        (procurement_plan["units_ordered"] * procurement_plan["unit_cost"]).sum()
        / procurement_plan["units_ordered"].sum()
    )
    risk_scenarios = pd.DataFrame([
        scenario_supplier_failure(total_demand, suppliers, procurement_plan, avg_price),
        scenario_factory_outbreak(total_demand, factory, current_inventory, production_plan, avg_price),
        scenario_demand_drop(procurement_plan, avg_supplier_cost),
        scenario_port_delay(logistics_plan, inventory_plan, avg_price),
    ])
    risk_scenarios["expected_loss_unmitigated"] = risk_scenarios["probability"] * risk_scenarios["unmitigated_cost"]
    risk_scenarios["expected_loss_residual"] = risk_scenarios["probability"] * risk_scenarios["residual_cost"]
    risk_scenarios = risk_scenarios.sort_values("expected_loss_residual", ascending=False).reset_index(drop=True)
    risk_scenarios.to_csv("outputs/risk_scenarios.csv", index=False)

    available_capacity = factory["capacity_units_per_month"].iloc[0] - factory["already_booked_units"].iloc[0]
    daily_output = available_capacity / 30
    quality_reports = simulate_quality_reports(daily_output)

    used_overtime = production_allocation.loc[production_allocation["lever"] == "Overtime", "units"].sum() \
        if len(production_allocation) else 0
    used_contractor = production_allocation.loc[production_allocation["lever"] == "Contractor", "units"].sum() \
        if len(production_allocation) else 0
    spare_overtime = factory["overtime_capacity_units"].iloc[0] - used_overtime
    spare_contractor = factory["contractor_capacity_units"].iloc[0] - used_contractor

    emergency_costs = []
    for row in quality_reports.itertuples():
        if row.rejection_rate <= 0.02 * 2.5:
            emergency_costs.append(0.0)
            continue
        miss_units = row.units_produced * (row.rejection_rate - 0.02)
        allocation, _ = emergency_allocation(miss_units, spare_overtime, factory["overtime_unit_cost"].iloc[0],
                                              spare_contractor, factory["contractor_unit_cost"].iloc[0])
        for item in allocation:
            if item["lever"] == "Overtime":
                spare_overtime -= item["units"]
            else:
                spare_contractor -= item["units"]
        emergency_costs.append(sum(item["cost"] for item in allocation))
    quality_reports["emergency_cost"] = emergency_costs
    quality_reports.to_csv("outputs/quality_reports.csv", index=False)

    shipment_alerts = pd.DataFrame(
        check_shipment_delays(logistics_plan, regional_demand, inventory_plan, avg_price)
    )
    shipment_alerts.to_csv("outputs/shipment_alerts.csv", index=False)

    whatif_common = dict(
        baseline_demand=total_demand, suppliers=suppliers, factory=factory, inventory=current_inventory,
        daily_demand_std=daily_demand_std, baseline_lead_time_days=weighted_lead_time_days,
    )
    whatif_scenarios_def = [
        ("Baseline", {}),
        ("Demand +20% (peak season)", {"demand_pct": 20}),
        ("Demand -20% (slowdown)", {"demand_pct": -20}),
        ("Lead time +50% (port congestion)", {"lead_time_pct": 50}),
        ("Raw material price +15%", {"price_pct": 15}),
        ("Worst case: demand +20% AND lead time +50%", {"demand_pct": 20, "lead_time_pct": 50}),
        ("Demand +70% (viral spike - exceeds every lever)", {"demand_pct": 70}),
    ]
    whatif_rows = [{"scenario": label, **run_scenario(**whatif_common, **overrides)}
                   for label, overrides in whatif_scenarios_def]
    whatif_scenarios = pd.DataFrame(whatif_rows)
    baseline_cost = whatif_scenarios.loc[whatif_scenarios["scenario"] == "Baseline", "total_cost"].iloc[0]
    whatif_scenarios["cost_delta_vs_baseline"] = whatif_scenarios["total_cost"] - baseline_cost
    whatif_scenarios.to_csv("outputs/whatif_scenarios.csv", index=False)

    # Week 5 - Performance + Finance
    performance = pd.DataFrame([
        track_forecast(forecast_input),
        track_procurement(procurement_plan),
        track_production(production_allocation, quality_reports),
        track_logistics(logistics_plan, shipment_alerts),
        track_inventory(inventory_plan, shipment_alerts),
        track_delivery(logistics_plan, shipment_alerts),
    ])
    performance.to_csv("outputs/performance_tracking.csv", index=False)

    finance = pd.DataFrame([
        compare_procurement(total_demand, suppliers),
        compare_production(total_demand, factory, current_inventory),
        compare_logistics(logistics_plan),
        compare_inventory(inventory_plan),
    ])
    finance["savings"] = finance["naive_cost"] - finance["optimized_cost"]
    finance.to_csv("outputs/financial_dashboard.csv", index=False)

    return {
        "sales": sales, "suppliers": suppliers, "factory": factory,
        "regional_demand": regional_demand, "current_inventory": current_inventory,
        "total_demand": total_demand, "forecast": forecast,
        "backtest_accuracy": accuracy, "backtest_within_interval": within_interval,
        "backtest_forecast_total": backtest_forecast_total, "backtest_actual_total": backtest_actual_total,
        "procurement_plan": procurement_plan, "production_plan": production_plan,
        "production_allocation": production_allocation,
        "inventory_plan": inventory_plan, "safety_stock": safety_stock,
        "logistics_plan": logistics_plan,
        "risk_scenarios": risk_scenarios, "quality_reports": quality_reports,
        "shipment_alerts": shipment_alerts, "whatif_scenarios": whatif_scenarios,
        "performance": performance, "finance": finance,
    }
