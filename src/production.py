"""
Module 9: Production Planning.

Checks whether the in-house factory can actually produce what demand
requires once existing bookings are accounted for. If there's a shortfall,
covers it with the cheapest combination of available levers: existing
finished-goods inventory (free), overtime (capped, cheap), then an
outsourced contractor (capped, most expensive) - filling each lever to
its limit before moving to the next, which minimizes total added cost.
Any demand left over after every lever is maxed out is reported as a
real stockout (unmet_units), not silently absorbed.

Run: python src/production.py
"""
import pandas as pd


def get_total_demand(path="outputs/demand_forecast.csv"):
    forecast = pd.read_csv(path)
    return forecast["yhat"].sum()


def plan_production(total_demand, factory, inventory):
    capacity = factory["capacity_units_per_month"].iloc[0]
    booked = factory["already_booked_units"].iloc[0]
    available_capacity = capacity - booked

    factory_units = min(total_demand, available_capacity)
    shortfall = max(0, total_demand - available_capacity)

    levers = [
        ("Existing finished-goods inventory", inventory["units_on_hand"].sum(), 0.0),
        ("Overtime", factory["overtime_capacity_units"].iloc[0], factory["overtime_unit_cost"].iloc[0]),
        ("Outsource to contractor", factory["contractor_capacity_units"].iloc[0], factory["contractor_unit_cost"].iloc[0]),
    ]
    levers.sort(key=lambda lever: lever[2])  # cheapest lever first

    remaining = shortfall
    allocation = []
    for name, capacity_avail, unit_cost in levers:
        if remaining <= 0:
            break
        used = min(remaining, capacity_avail)
        if used > 0:
            allocation.append({"lever": name, "units": round(used), "unit_cost": unit_cost,
                                "cost": round(used * unit_cost, 2)})
        remaining -= used

    return {
        "total_demand": total_demand,
        "factory_capacity": capacity,
        "already_booked": booked,
        "available_capacity": available_capacity,
        "factory_units": round(factory_units),
        "shortfall": round(shortfall),
        "unmet_units": round(max(0, remaining)),
        "allocation": allocation,
    }


if __name__ == "__main__":
    total_demand = get_total_demand()
    factory = pd.read_csv("data/factory_status.csv")
    inventory = pd.read_csv("data/inventory.csv")

    result = plan_production(total_demand, factory, inventory)

    print(f"Demand: {result['total_demand']:,.0f} units")
    print(f"Factory capacity: {result['factory_capacity']:,.0f}/month, "
          f"already booked: {result['already_booked']:,.0f} -> available: {result['available_capacity']:,.0f}")

    if result["shortfall"] == 0:
        print(f"\nFactory can cover demand in-house: {result['factory_units']:,.0f} units. No shortfall.")
        allocation_df = pd.DataFrame(columns=["lever", "units", "unit_cost", "cost"])
    else:
        print(f"\nSHORTFALL: need {result['shortfall']:,.0f} more units than the factory can make.\n")
        allocation_df = pd.DataFrame(result["allocation"])
        print(allocation_df.to_string(index=False))
        added_cost = allocation_df["cost"].sum()
        print(f"\nPlan: {result['factory_units']:,.0f} units in-house + "
              + " + ".join(f"{row.units:,.0f} via {row.lever.lower()}" for row in allocation_df.itertuples())
              + f"\nAdded cost: ${added_cost:,.2f}")
        if result["unmet_units"] > 0:
            print(f"WARNING: {result['unmet_units']:,.0f} units still unmet even after every lever - "
                  f"reduce forecast or accept a stockout.")

    summary = pd.DataFrame([{
        "total_demand": result["total_demand"],
        "factory_units": result["factory_units"],
        "shortfall": result["shortfall"],
        "unmet_units": result["unmet_units"],
    }])
    summary.to_csv("outputs/production_plan_summary.csv", index=False)
    allocation_df.to_csv("outputs/production_plan_allocation.csv", index=False)
    print("\nSaved to outputs/production_plan_summary.csv and outputs/production_plan_allocation.csv")
