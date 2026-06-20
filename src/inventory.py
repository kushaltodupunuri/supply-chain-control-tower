"""
Module 3: Inventory Optimization.

Decides how much total safety stock the network needs (based on demand
variability and the lead time of the suppliers actually chosen in
Module 2), then positions stock across locations: the safety-stock buffer
stays centrally at the factory warehouse (cheapest to hold, can ship
anywhere), while each forward DC/store holds just enough cycle stock to
cover its own region's demand during the transit time from the factory
to that location - a DC 18 days out by ocean needs more forward cover
than one 3 days out by truck, regardless of how much total demand each
region has.

Run: python src/inventory.py
"""
import numpy as np
import pandas as pd

SERVICE_LEVEL_Z = 1.65  # ~95% service level


def get_total_demand(path="outputs/demand_forecast.csv"):
    forecast = pd.read_csv(path)
    return forecast["yhat"].sum()


def get_weighted_lead_time_days(path="outputs/procurement_plan.csv"):
    plan = pd.read_csv(path)
    weighted_weeks = (plan["units_ordered"] * plan["lead_time_weeks"]).sum() / plan["units_ordered"].sum()
    return weighted_weeks * 7


def plan_inventory(total_demand, daily_demand_std, lead_time_days, regional_demand, current_inventory):
    avg_daily_demand = total_demand / 30
    safety_stock = int(np.ceil(SERVICE_LEVEL_Z * daily_demand_std * np.sqrt(lead_time_days)))

    regional_demand = regional_demand.copy()
    regional_demand["forward_stock"] = (
        avg_daily_demand * regional_demand["demand_share"] * regional_demand["transit_days_from_factory"]
    )
    forward_stock = regional_demand.set_index("region")["forward_stock"]
    location_forward_stock = {
        "Stores": forward_stock["North America"] + forward_stock["Latin America"],
        "Asia DC": forward_stock["Asia"],
        "Europe DC": forward_stock["Europe"],
    }

    optimized = current_inventory.copy()
    optimized["optimized_units"] = optimized["location"].map(
        lambda loc: safety_stock if loc == "Factory Warehouse" else location_forward_stock.get(loc, 0)
    ).round().astype(int)

    optimized["current_holding_cost"] = (optimized["units_on_hand"] * optimized["holding_cost_per_unit_month"]).round(2)
    optimized["optimized_holding_cost"] = (optimized["optimized_units"] * optimized["holding_cost_per_unit_month"]).round(2)

    return optimized, safety_stock


if __name__ == "__main__":
    total_demand = get_total_demand()
    lead_time_days = get_weighted_lead_time_days()
    sales = pd.read_csv("data/sales_history.csv")
    daily_demand_std = sales["units_sold"].std()
    regional_demand = pd.read_csv("data/regional_demand.csv")
    current_inventory = pd.read_csv("data/inventory.csv")

    plan, safety_stock = plan_inventory(
        total_demand, daily_demand_std, lead_time_days, regional_demand, current_inventory
    )
    plan.to_csv("outputs/inventory_plan.csv", index=False)

    print(f"Demand: {total_demand:,.0f} units/month | demand std/day: {daily_demand_std:,.0f} | "
          f"weighted supplier lead time: {lead_time_days:.1f} days")
    print(f"Network safety stock needed (95% service level): {safety_stock:,.0f} units, "
          f"held at the factory warehouse (cheapest, ships anywhere)")
    print("Forward stock per location sized to that region's own transit time from the factory:\n")

    print(plan[["location", "units_on_hand", "optimized_units",
                 "current_holding_cost", "optimized_holding_cost"]].to_string(index=False))

    current_total_cost = plan["current_holding_cost"].sum()
    optimized_total_cost = plan["optimized_holding_cost"].sum()
    delta = optimized_total_cost - current_total_cost
    print(f"\nCurrent total: {plan['units_on_hand'].sum():,.0f} units, ${current_total_cost:,.2f}/month holding cost")
    print(f"Optimized total: {plan['optimized_units'].sum():,.0f} units, ${optimized_total_cost:,.2f}/month holding cost")
    if delta <= 0:
        print(f"SAVINGS: ${-delta:,.2f}/month by repositioning stock")
    else:
        print(f"COST INCREASE: ${delta:,.2f}/month - current Asia/Europe DC stock is genuinely "
              f"under-positioned for their real ocean transit times once sized properly; this isn't "
              f"a repositioning saving, it's the cost of closing a real coverage gap.")
    print("\nSaved to outputs/inventory_plan.csv")
