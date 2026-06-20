"""
Supply Chain Control Tower dashboard.

Run: streamlit run streamlit_app.py
"""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from pipeline import run_full_pipeline  # noqa: E402

st.set_page_config(page_title="Supply Chain Control Tower", layout="wide")


@st.cache_data
def load_pipeline():
    return run_full_pipeline()


data = load_pipeline()

st.title("Supply Chain Control Tower")
st.caption("Demand forecast -> procurement -> production -> inventory -> logistics -> risk -> "
           "performance, chained end-to-end on one synthetic T-shirt business.")

tab1, tab2, tab3, tab4 = st.tabs(["Executive Dashboard", "Demand Forecast", "Procurement", "Inventory"])

# ---------------------------------------------------------------- Tab 1
with tab1:
    production_plan = data["production_plan"]
    service_level = (production_plan["total_demand"] - production_plan["unmet_units"]) / production_plan["total_demand"] * 100
    net_savings = data["finance"]["savings"].sum()
    top_risk = data["risk_scenarios"].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Demand (next 30 days)", f"{data['total_demand']:,.0f} units")
    col2.metric("Net savings vs. naive plan", f"${net_savings:,.0f}/mo")
    col3.metric("Service level", f"{service_level:.1f}%")
    col4.metric("Top risk (expected loss)", f"${top_risk['expected_loss_residual']:,.0f}/mo", top_risk["scenario"])

    st.divider()
    st.subheader("Active alerts")
    alerted = False
    quality_alerts = data["quality_reports"][data["quality_reports"]["emergency_cost"] > 0]
    for row in quality_alerts.itertuples():
        st.warning(f"Day {row.day}: production quality rejection rate {row.rejection_rate:.1%} "
                   f"(expected ~2%) - ${row.emergency_cost:,.2f} in emergency overtime.")
        alerted = True
    for row in data["shipment_alerts"].itertuples():
        st.warning(f"{row.region} shipment delayed {row.delay_days:.0f} days beyond schedule - "
                   f"{row.still_exposed:,.0f} units still exposed after DC inventory coverage.")
        alerted = True
    if not alerted:
        st.success("No active disruption alerts this period.")

    st.divider()
    st.subheader("Plan vs. actual this period")
    st.dataframe(data["performance"][["metric", "planned", "actual", "variance", "note"]],
                 width='stretch', hide_index=True)

# ---------------------------------------------------------------- Tab 2
with tab2:
    st.subheader("Demand Forecast")
    col1, col2 = st.columns(2)
    col1.metric("Backtest accuracy (30-day holdout)", f"{data['backtest_accuracy']:.1f}%")
    col2.metric("Actuals within forecast interval", f"{data['backtest_within_interval']:.0f}%")

    history = data["sales"].tail(90)
    forecast = data["forecast"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history["date"], y=history["units_sold"], name="Historical sales",
                              line=dict(color="steelblue")))
    fig.add_trace(go.Scatter(x=forecast["ds"], y=forecast["yhat"], name="Forecast",
                              line=dict(color="orange")))
    fig.add_trace(go.Scatter(x=forecast["ds"], y=forecast["yhat_upper"], name="Upper bound",
                              line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=forecast["ds"], y=forecast["yhat_lower"], name="Confidence interval",
                              fill="tonexty", fillcolor="rgba(255,165,0,0.2)", line=dict(width=0)))
    fig.update_layout(height=450, margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h"))
    st.plotly_chart(fig, width='stretch')

    st.dataframe(forecast.rename(columns={"ds": "date", "yhat": "forecast",
                                           "yhat_lower": "lower", "yhat_upper": "upper"}),
                 width='stretch', hide_index=True)

# ---------------------------------------------------------------- Tab 3
with tab3:
    st.subheader("Procurement Plan")
    plan = data["procurement_plan"]
    finance_row = data["finance"].loc[data["finance"]["category"] == "Procurement"].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total cost", f"${plan['cost'].sum():,.0f}")
    col2.metric("Suppliers used", len(plan))
    col3.metric("Diversification premium", f"${finance_row['savings'] * -1:,.0f}",
                help="Extra cost vs. buying everything from the single cheapest supplier - "
                     "buys faster failover if a supplier fails.")

    st.dataframe(plan[["name", "units_ordered", "unit_cost", "cost", "pct_of_order",
                        "lead_time_weeks", "reliability_pct"]],
                 width='stretch', hide_index=True)

    fig = px.bar(plan, x="name", y="cost", color="name", text="units_ordered",
                 labels={"cost": "Cost ($)", "name": "Supplier"})
    fig.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, width='stretch')

    st.caption(finance_row["note"])

# ---------------------------------------------------------------- Tab 4
with tab4:
    st.subheader("Inventory Positioning")
    plan = data["inventory_plan"]
    finance_row = data["finance"].loc[data["finance"]["category"] == "Inventory"].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Current holding cost", f"${plan['current_holding_cost'].sum():,.0f}/mo")
    col2.metric("Optimized holding cost", f"${plan['optimized_holding_cost'].sum():,.0f}/mo",
                f"{finance_row['savings']:+,.0f}")
    col3.metric("Factory safety stock", f"{data['safety_stock']:,.0f} units")

    st.dataframe(plan[["location", "units_on_hand", "optimized_units",
                        "current_holding_cost", "optimized_holding_cost"]],
                 width='stretch', hide_index=True)

    melted = plan.melt(id_vars="location", value_vars=["units_on_hand", "optimized_units"],
                        var_name="state", value_name="units")
    melted["state"] = melted["state"].map({"units_on_hand": "Current", "optimized_units": "Optimized"})
    fig = px.bar(melted, x="location", y="units", color="state", barmode="group",
                 labels={"units": "Units", "location": "Location"})
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="")
    st.plotly_chart(fig, width='stretch')

    st.caption(finance_row["note"])
