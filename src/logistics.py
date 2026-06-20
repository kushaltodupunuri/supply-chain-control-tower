"""
Module 4: Logistics Planning & Consolidation.

Splits total demand into per-region order volume, then compares shipping
every order individually against batching each region's volume into full
containers (with any leftover going by LTL or into one more container,
whichever is cheaper).

Run: python src/logistics.py
"""
import math
import pandas as pd

CONTAINER_CAPACITY_UNITS = 5_000
LTL_COST_PER_UNIT = 1.20  # consolidated small-shipment rate for leftover units


def get_total_demand(path="outputs/demand_forecast.csv"):
    forecast = pd.read_csv(path)
    return forecast["yhat"].sum()


def plan_logistics(total_demand, regional_demand):
    plan = regional_demand.copy()
    plan["units"] = (total_demand * plan["demand_share"]).round().astype(int)
    plan["num_orders"] = (plan["units"] / plan["avg_order_units"]).round().astype(int)

    plan["unconsolidated_cost"] = plan["num_orders"] * plan["individual_shipping_cost_per_order"]

    full_containers = plan["units"] // CONTAINER_CAPACITY_UNITS
    leftover_units = plan["units"] % CONTAINER_CAPACITY_UNITS

    ltl_cost = leftover_units * LTL_COST_PER_UNIT
    use_extra_container = ltl_cost > plan["container_cost"]

    plan["containers"] = full_containers + use_extra_container.astype(int)
    plan["leftover_units"] = leftover_units.where(~use_extra_container, 0)
    plan["leftover_mode"] = leftover_units.gt(0).map({True: "LTL", False: "-"})
    plan.loc[use_extra_container, "leftover_mode"] = "extra container"

    plan["consolidated_cost"] = (
        plan["containers"] * plan["container_cost"]
        + plan["leftover_units"] * LTL_COST_PER_UNIT
    )
    plan["savings"] = plan["unconsolidated_cost"] - plan["consolidated_cost"]

    return plan


if __name__ == "__main__":
    total_demand = get_total_demand()
    regional_demand = pd.read_csv("data/regional_demand.csv")

    plan = plan_logistics(total_demand, regional_demand)
    plan.to_csv("outputs/logistics_plan.csv", index=False)

    print(f"Total demand to ship: {total_demand:,.0f} units\n")
    for row in plan.itertuples():
        mode = f"{row.containers} container(s)"
        if row.leftover_mode == "LTL":
            mode += f" + LTL ({row.leftover_units:,.0f} units)"
        print(f"{row.region}: {row.units:,.0f} units, {row.num_orders:,.0f} orders -> {mode}")
        print(f"  Unconsolidated: ${row.unconsolidated_cost:,.2f}  |  "
              f"Consolidated: ${row.consolidated_cost:,.2f}  |  Saves: ${row.savings:,.2f}")

    total_unconsolidated = plan["unconsolidated_cost"].sum()
    total_consolidated = plan["consolidated_cost"].sum()
    print(f"\nTOTAL without consolidation: ${total_unconsolidated:,.2f}")
    print(f"TOTAL with consolidation:    ${total_consolidated:,.2f}")
    print(f"SAVINGS: ${total_unconsolidated - total_consolidated:,.2f} from batching orders into containers")
    print("\nSaved to outputs/logistics_plan.csv")
