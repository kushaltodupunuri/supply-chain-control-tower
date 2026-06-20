"""
Module 7: Financial Dashboard.

Compares this system's optimized plan against the naive baseline each
module would have produced without its own optimization - reusing the
real functions (plan_procurement, plan_production) rather than guessing
naive numbers, and the actual "without consolidation" / "current
inventory" figures already computed in Weeks 2-3.

Run: python src/finance.py
"""
import pandas as pd
from procurement import plan_procurement
from production import plan_production


def compare_procurement(total_demand, suppliers):
    optimized = plan_procurement(total_demand, suppliers)
    naive = plan_procurement(total_demand, suppliers, max_supplier_share=1.0)  # no diversification cap
    return {
        "category": "Procurement", "naive_cost": naive["cost"].sum(), "optimized_cost": optimized["cost"].sum(),
        "note": "Diversification premium - buys faster failover if a supplier fails, not a cost saving.",
    }


def compare_production(total_demand, factory, inventory):
    optimized = plan_production(total_demand, factory, inventory)
    optimized_cost = sum(item["cost"] for item in optimized["allocation"])

    naive_cost = optimized["shortfall"] * factory["contractor_unit_cost"].iloc[0]  # naive: contractor for everything
    return {
        "category": "Production", "naive_cost": naive_cost, "optimized_cost": optimized_cost,
        "note": "Naive = outsource the whole shortfall to a contractor instead of using "
                "free inventory + cheap overtime first.",
    }


def compare_logistics(logistics_plan):
    return {
        "category": "Logistics",
        "naive_cost": logistics_plan["unconsolidated_cost"].sum(),
        "optimized_cost": logistics_plan["consolidated_cost"].sum(),
        "note": "Naive = ship every order individually instead of batching into containers.",
    }


def compare_inventory(inventory_plan):
    return {
        "category": "Inventory",
        "naive_cost": inventory_plan["current_holding_cost"].sum(),
        "optimized_cost": inventory_plan["optimized_holding_cost"].sum(),
        "note": "Optimized costs MORE - today's stock is under-positioned for real overseas "
                "transit times; this is the cost of closing that gap, not a saving.",
    }


if __name__ == "__main__":
    forecast = pd.read_csv("outputs/demand_forecast.csv")
    total_demand = forecast["yhat"].sum()
    suppliers = pd.read_csv("data/suppliers.csv")
    factory = pd.read_csv("data/factory_status.csv")
    inventory = pd.read_csv("data/inventory.csv")
    logistics_plan = pd.read_csv("outputs/logistics_plan.csv")
    inventory_plan = pd.read_csv("outputs/inventory_plan.csv")

    rows = [
        compare_procurement(total_demand, suppliers),
        compare_production(total_demand, factory, inventory),
        compare_logistics(logistics_plan),
        compare_inventory(inventory_plan),
    ]
    df = pd.DataFrame(rows)
    df["savings"] = df["naive_cost"] - df["optimized_cost"]
    df.to_csv("outputs/financial_dashboard.csv", index=False)

    print("WITHOUT OPTIMIZATION (naive baseline):")
    for row in df.itertuples():
        print(f"  {row.category}: ${row.naive_cost:,.2f}")
    naive_total = df["naive_cost"].sum()
    print(f"  TOTAL: ${naive_total:,.2f}\n")

    print("WITH THIS SYSTEM (optimized):")
    for row in df.itertuples():
        sign = "saved" if row.savings >= 0 else "cost"
        print(f"  {row.category}: ${row.optimized_cost:,.2f}  ({sign} ${abs(row.savings):,.2f} - {row.note})")
    optimized_total = df["optimized_cost"].sum()
    print(f"  TOTAL: ${optimized_total:,.2f}\n")

    net_savings = naive_total - optimized_total
    print(f"NET SAVINGS THIS PERIOD: ${net_savings:,.2f} ({net_savings / naive_total:.1%} of naive total)")
    print(f"If sustained monthly: ${net_savings * 12:,.2f}/year")
    print("\nSaved to outputs/financial_dashboard.csv")
