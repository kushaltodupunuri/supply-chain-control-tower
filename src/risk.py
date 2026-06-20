"""
Module 6: Risk & Scenario Analysis.

Stress-tests the plan built in Weeks 1-3 against four disruption scenarios.
Each scenario reports an "unmitigated" cost (if nothing in the existing
plan helped) and a "residual" cost (what's actually still exposed once the
real mitigations already built into the plan - backup suppliers, overtime/
contractor capacity, DC inventory - are applied). Scenarios are ranked by
probability x residual cost, since that's the risk still worth acting on.

Probabilities for the factory-outbreak, demand-drop, and port-delay
scenarios are hand-curated assumptions (no free real-time source for
them); the supplier-failure probability is the one real number available,
taken directly from that supplier's own reliability_pct.

Run: python src/risk.py
"""
import pandas as pd
from procurement import plan_procurement
from production import plan_production

OUTBREAK_DAYS = 10  # ~2 weeks of a ~30-day production month
OUTBREAK_PROBABILITY = 0.05
DEMAND_DROP_PCT = 0.30
DEMAND_DROP_PROBABILITY = 0.08
DEMAND_DROP_CANCELLATION_FEE_PCT = 0.05  # flexible-contract cancellation fee on avoided units
PORT_DELAY_DISCOUNT_PCT = 0.10  # customer-retention discount on late units
PORT_DELAY_PROBABILITY = 0.12


def scenario_supplier_failure(total_demand, suppliers, procurement_plan, avg_price):
    top = procurement_plan.loc[procurement_plan["units_ordered"].idxmax()]
    probability = (100 - top["reliability_pct"]) / 100

    unmitigated = top["units_ordered"] * avg_price  # no replacement at all

    backup_suppliers = suppliers[suppliers["supplier_id"] != top["supplier_id"]]
    mitigated_plan = plan_procurement(total_demand, backup_suppliers)
    residual = mitigated_plan["cost"].sum() - procurement_plan["cost"].sum()

    return {
        "scenario": f"{top['name']} fails to deliver",
        "probability": probability,
        "unmitigated_cost": unmitigated,
        "residual_cost": max(0.0, residual),
        "mitigation": f"Backup suppliers ({', '.join(backup_suppliers['name'])}) absorb the volume "
                       f"at a higher blended cost instead of a stockout.",
    }


def scenario_factory_outbreak(total_demand, factory, inventory, production_plan, avg_price):
    lost_units = production_plan["factory_units"] * (OUTBREAK_DAYS / 30)
    unmitigated = lost_units * avg_price

    reduced_demand = total_demand - lost_units  # factory produces nothing during the outbreak
    mitigated_plan = plan_production(reduced_demand, factory, inventory)
    baseline_added_cost = sum(item["cost"] for item in production_plan["allocation"])
    residual = mitigated_plan["allocation"]
    residual_cost = sum(item["cost"] for item in residual) - baseline_added_cost
    unmet_revenue_loss = mitigated_plan["unmet_units"] * avg_price

    return {
        "scenario": f"Factory outbreak ({OUTBREAK_DAYS}-day stoppage)",
        "probability": OUTBREAK_PROBABILITY,
        "unmitigated_cost": unmitigated,
        "residual_cost": max(0.0, residual_cost) + unmet_revenue_loss,
        "mitigation": "Existing inventory/overtime/contractor levers absorb the lost output at extra cost.",
    }


def scenario_demand_drop(procurement_plan, avg_cost):
    baseline_units = procurement_plan["units_ordered"].sum()
    excess_units = baseline_units * DEMAND_DROP_PCT

    unmitigated = excess_units * avg_cost  # cash tied up in unsold inventory
    residual = unmitigated * DEMAND_DROP_CANCELLATION_FEE_PCT  # flexible contract: just a cancellation fee

    return {
        "scenario": f"Demand drops {DEMAND_DROP_PCT:.0%}",
        "probability": DEMAND_DROP_PROBABILITY,
        "unmitigated_cost": unmitigated,
        "residual_cost": residual,
        "mitigation": "Flexible supplier contracts let orders be reduced before shipment, "
                       "for a small cancellation fee instead of eating the full excess.",
    }


def scenario_port_delay(logistics_plan, inventory_plan, avg_price):
    worst = logistics_plan.loc[logistics_plan["units"].idxmax()]
    delayed_units = worst["units"]

    unmitigated = delayed_units * avg_price * PORT_DELAY_DISCOUNT_PCT

    dc_location = {
        "Asia": "Asia DC", "Europe": "Europe DC",
        "North America": "Stores", "Latin America": "Stores",
    }.get(worst["region"])
    dc_inventory = 0
    if dc_location is not None:
        match = inventory_plan.loc[inventory_plan["location"] == dc_location, "optimized_units"]
        dc_inventory = match.iloc[0] if len(match) else 0

    units_still_exposed = max(0, delayed_units - dc_inventory)
    residual = units_still_exposed * avg_price * PORT_DELAY_DISCOUNT_PCT

    return {
        "scenario": f"Port delay - {worst['region']} shipment",
        "probability": PORT_DELAY_PROBABILITY,
        "unmitigated_cost": unmitigated,
        "residual_cost": residual,
        "mitigation": f"{dc_location or 'Local stock'} covers urgent orders during the delay; "
                       f"only the remainder needs a retention discount.",
    }


if __name__ == "__main__":
    forecast = pd.read_csv("outputs/demand_forecast.csv")
    total_demand = forecast["yhat"].sum()

    suppliers = pd.read_csv("data/suppliers.csv")
    factory = pd.read_csv("data/factory_status.csv")
    inventory = pd.read_csv("data/inventory.csv")
    sales = pd.read_csv("data/sales_history.csv")
    avg_price = sales["price"].mean()

    procurement_plan = plan_procurement(total_demand, suppliers)
    production_plan = plan_production(total_demand, factory, inventory)
    avg_supplier_cost = (procurement_plan["units_ordered"] * procurement_plan["unit_cost"]).sum() / procurement_plan["units_ordered"].sum()

    logistics_plan = pd.read_csv("outputs/logistics_plan.csv")
    inventory_plan = pd.read_csv("outputs/inventory_plan.csv")

    scenarios = [
        scenario_supplier_failure(total_demand, suppliers, procurement_plan, avg_price),
        scenario_factory_outbreak(total_demand, factory, inventory, production_plan, avg_price),
        scenario_demand_drop(procurement_plan, avg_supplier_cost),
        scenario_port_delay(logistics_plan, inventory_plan, avg_price),
    ]

    df = pd.DataFrame(scenarios)
    df["expected_loss_unmitigated"] = df["probability"] * df["unmitigated_cost"]
    df["expected_loss_residual"] = df["probability"] * df["residual_cost"]
    df = df.sort_values("expected_loss_residual", ascending=False).reset_index(drop=True)
    df.to_csv("outputs/risk_scenarios.csv", index=False)

    print(f"Demand: {total_demand:,.0f} units | avg selling price: ${avg_price:.2f}\n")
    for row in df.itertuples():
        print(f"{row.scenario}  (probability: {row.probability:.0%})")
        print(f"  Unmitigated cost: ${row.unmitigated_cost:,.0f}  ->  Residual after mitigation: ${row.residual_cost:,.0f}")
        print(f"  Mitigation: {row.mitigation}")
        print(f"  Expected loss - unmitigated: ${row.expected_loss_unmitigated:,.0f}  |  "
              f"residual: ${row.expected_loss_residual:,.0f}\n")

    print(f"TOP PRIORITY (highest residual expected loss): {df.iloc[0]['scenario']} "
          f"(${df.iloc[0]['expected_loss_residual']:,.0f}/month expected)")
    print("\nSaved to outputs/risk_scenarios.csv")
