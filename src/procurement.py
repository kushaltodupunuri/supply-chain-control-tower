"""
Module 2: Procurement Planning.

Takes the demand forecast from Module 1 and decides how many units to buy
from each external supplier, minimizing total cost subject to each
supplier's capacity and a diversification cap (no single supplier should
cover the whole order - a delay or quality failure at one supplier would
otherwise stall the entire order).

Run: python src/procurement.py
"""
import pandas as pd
import pulp

MAX_SINGLE_SUPPLIER_SHARE = 0.70  # no supplier can cover more than 70% of demand


def get_total_demand(path="outputs/demand_forecast.csv"):
    forecast = pd.read_csv(path)
    return forecast["yhat"].sum()


def plan_procurement(total_demand, suppliers):
    problem = pulp.LpProblem("procurement_cost_minimization", pulp.LpMinimize)

    qty = {
        row.supplier_id: pulp.LpVariable(f"qty_{row.supplier_id}", lowBound=0, upBound=row.max_capacity_units)
        for row in suppliers.itertuples()
    }

    problem += pulp.lpSum(qty[row.supplier_id] * row.unit_cost for row in suppliers.itertuples())
    problem += pulp.lpSum(qty.values()) >= total_demand

    cap_per_supplier = MAX_SINGLE_SUPPLIER_SHARE * total_demand
    for supplier_id in qty:
        problem += qty[supplier_id] <= cap_per_supplier

    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Procurement plan infeasible: {pulp.LpStatus[status]}")

    plan = suppliers.copy()
    plan["units_ordered"] = plan["supplier_id"].map(lambda sid: round(qty[sid].value()))
    plan["cost"] = (plan["units_ordered"] * plan["unit_cost"]).round(2)
    plan["pct_of_order"] = (plan["units_ordered"] / plan["units_ordered"].sum() * 100).round(1)
    return plan[plan["units_ordered"] > 0].reset_index(drop=True)


if __name__ == "__main__":
    total_demand = get_total_demand()
    suppliers = pd.read_csv("data/suppliers.csv")

    plan = plan_procurement(total_demand, suppliers)
    plan.to_csv("outputs/procurement_plan.csv", index=False)

    print(f"Demand to cover: {total_demand:,.0f} units\n")
    print(plan[["name", "units_ordered", "unit_cost", "cost", "pct_of_order", "lead_time_weeks", "reliability_pct"]]
          .to_string(index=False))
    print(f"\nTOTAL COST: ${plan['cost'].sum():,.2f}")
    print(f"Sourced from {len(plan)} supplier(s), capped at {MAX_SINGLE_SUPPLIER_SHARE:.0%} per supplier "
          f"so a single delay/quality failure can't stall the whole order.")
    print("\nSaved to outputs/procurement_plan.csv")
