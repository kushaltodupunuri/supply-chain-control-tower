"""
Module 10: Real-Time Disruption Detection & Tracking.

Simulates a week of daily factory quality reports and a spot-check of each
region's shipment transit time, flags anything outside normal range, and
computes an auto-response using whatever spare capacity/inventory the
existing plan didn't already commit elsewhere. There's no live factory or
carrier feed wired up yet, so "real-time" here means the alerting and
auto-response logic that would run against one once there is - the daily
reports/transit checks are seeded random simulations standing in for it.

Run: python src/disruption.py
"""
import numpy as np
import pandas as pd

QUALITY_BASELINE_RATE = 0.02
QUALITY_ALERT_MULTIPLE = 2.5  # alert if actual rejection rate exceeds 2.5x baseline
N_DAYS = 7
SPIKE_DAY = 3  # guarantees at least one demonstrable alert, like any real week eventually has

DELAY_ALERT_THRESHOLD_DAYS = 2
RETENTION_DISCOUNT_PCT = 0.10

rng = np.random.default_rng(7)


def simulate_quality_reports(daily_output):
    reports = []
    for day in range(1, N_DAYS + 1):
        if day == SPIKE_DAY:
            rate = rng.uniform(0.06, 0.10)
        else:
            rate = max(0.0, rng.normal(QUALITY_BASELINE_RATE, 0.005))
        reports.append({"day": day, "units_produced": daily_output, "rejection_rate": rate})
    return pd.DataFrame(reports)


def emergency_allocation(miss_units, spare_overtime, overtime_cost, spare_contractor, contractor_cost):
    levers = sorted([
        ("Overtime", spare_overtime, overtime_cost),
        ("Contractor", spare_contractor, contractor_cost),
    ], key=lambda lever: lever[2])

    remaining = miss_units
    allocation = []
    for name, capacity, cost in levers:
        if remaining <= 0:
            break
        used = min(remaining, capacity)
        if used > 0:
            allocation.append({"lever": name, "units": used, "cost": used * cost})
        remaining -= used
    return allocation, max(0, remaining)


def check_shipment_delays(logistics_plan, regional_demand, inventory_plan, avg_price):
    alerts = []
    for row in logistics_plan.itertuples():
        scheduled = regional_demand.loc[regional_demand["region"] == row.region, "transit_days_from_factory"].iloc[0]
        delay_days = rng.poisson(0.5)
        if row.region == "Asia":  # guarantee one demonstrable shipment alert
            delay_days = max(delay_days, 4)
        actual = scheduled + delay_days

        if delay_days <= DELAY_ALERT_THRESHOLD_DAYS:
            continue

        dc_location = {
            "Asia": "Asia DC", "Europe": "Europe DC",
            "North America": "Stores", "Latin America": "Stores",
        }.get(row.region)
        dc_inventory = 0
        if dc_location is not None:
            match = inventory_plan.loc[inventory_plan["location"] == dc_location, "optimized_units"]
            dc_inventory = match.iloc[0] if len(match) else 0

        covered = min(row.units, dc_inventory)
        exposed = row.units - covered
        discount_cost = exposed * RETENTION_DISCOUNT_PCT * avg_price

        alerts.append({
            "region": row.region, "scheduled_days": scheduled, "actual_days": actual,
            "delay_days": delay_days, "units_at_risk": row.units,
            "covered_by_dc": covered, "still_exposed": exposed,
            "dc_location": dc_location, "discount_cost": discount_cost,
        })
    return alerts


if __name__ == "__main__":
    production_plan_summary = pd.read_csv("outputs/production_plan_summary.csv")
    production_allocation = pd.read_csv("outputs/production_plan_allocation.csv")
    factory = pd.read_csv("data/factory_status.csv")
    logistics_plan = pd.read_csv("outputs/logistics_plan.csv")
    regional_demand = pd.read_csv("data/regional_demand.csv")
    inventory_plan = pd.read_csv("outputs/inventory_plan.csv")
    avg_price = pd.read_csv("data/sales_history.csv")["price"].mean()

    available_capacity = factory["capacity_units_per_month"].iloc[0] - factory["already_booked_units"].iloc[0]
    daily_output = available_capacity / 30

    print("=" * 60)
    print("PRODUCTION QUALITY MONITORING")
    print("=" * 60)
    reports = simulate_quality_reports(daily_output)

    used_overtime = production_allocation.loc[production_allocation["lever"] == "Overtime", "units"].sum()
    used_contractor = production_allocation.loc[production_allocation["lever"] == "Contractor", "units"].sum()
    spare_overtime = factory["overtime_capacity_units"].iloc[0] - used_overtime
    spare_contractor = factory["contractor_capacity_units"].iloc[0] - used_contractor

    emergency_costs = []
    for row in reports.itertuples():
        if row.rejection_rate <= QUALITY_BASELINE_RATE * QUALITY_ALERT_MULTIPLE:
            print(f"Day {row.day}: produced {row.units_produced:,.0f} units, "
                  f"rejection rate {row.rejection_rate:.1%} (normal)")
            emergency_costs.append(0.0)
            continue

        miss_units = row.units_produced * (row.rejection_rate - QUALITY_BASELINE_RATE)
        print(f"\n[ALERT] Day {row.day}: rejection rate {row.rejection_rate:.1%} "
              f"(expected ~{QUALITY_BASELINE_RATE:.0%}) - will miss ~{miss_units:,.0f} units today")

        allocation, unmet = emergency_allocation(miss_units, spare_overtime, factory["overtime_unit_cost"].iloc[0],
                                                   spare_contractor, factory["contractor_unit_cost"].iloc[0])
        for item in allocation:
            print(f"  Auto-response: {item['units']:,.0f} units via {item['lever']} (${item['cost']:,.2f})")
            if item["lever"] == "Overtime":
                spare_overtime -= item["units"]
            else:
                spare_contractor -= item["units"]
        if unmet > 0:
            print(f"  WARNING: {unmet:,.0f} units still unmet - no spare capacity left today")
        emergency_costs.append(sum(item["cost"] for item in allocation))

    reports["emergency_cost"] = emergency_costs

    print("\n" + "=" * 60)
    print("SHIPMENT TRACKING")
    print("=" * 60)
    alerts = check_shipment_delays(logistics_plan, regional_demand, inventory_plan, avg_price)
    if not alerts:
        print("All shipments within normal transit variance.")
    for a in alerts:
        print(f"\n[ALERT] {a['region']}: scheduled {a['scheduled_days']:.0f} days, "
              f"now tracking {a['actual_days']:.0f} days (+{a['delay_days']:.0f})")
        print(f"  {a['units_at_risk']:,.0f} units at risk")
        if a["covered_by_dc"] > 0:
            print(f"  Auto-response: {a['covered_by_dc']:,.0f} units covered from {a['dc_location']} inventory")
        if a["still_exposed"] > 0:
            print(f"  {a['still_exposed']:,.0f} units still exposed - offering retention discount "
                  f"(~${a['discount_cost']:,.2f})")

    pd.DataFrame(alerts).to_csv("outputs/shipment_alerts.csv", index=False)
    reports.to_csv("outputs/quality_reports.csv", index=False)
    print("\nSaved to outputs/quality_reports.csv and outputs/shipment_alerts.csv")
