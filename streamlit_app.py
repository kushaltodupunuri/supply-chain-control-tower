"""
Supply Chain Control Tower dashboard.

Run: streamlit run streamlit_app.py
"""
import io
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from pipeline import run_full_pipeline  # noqa: E402
from production import plan_production  # noqa: E402
from whatif import run_scenario  # noqa: E402

st.set_page_config(page_title="Supply Chain Control Tower", page_icon="📦", layout="wide")

REQUIRED_COLUMNS = ["date", "units_sold"]
MIN_SALES_ROWS = 60


@st.cache_data
def load_pipeline(sales_csv_bytes=None, avg_price_override=None):
    uploaded_df = pd.read_csv(io.BytesIO(sales_csv_bytes)) if sales_csv_bytes is not None else None
    return run_full_pipeline(uploaded_sales=uploaded_df, avg_price_override=avg_price_override)


st.title("Supply Chain Control Tower")
st.caption("Demand forecast -> procurement -> production -> inventory -> logistics -> risk -> "
           "performance, chained end-to-end.")

# ---------------------------------------------------------------- Data source
uploaded_file = st.file_uploader(
    "Upload your own sales history (CSV with 'date' and 'units_sold' columns, "
    "optionally 'promotion_flag', 'price', 'avg_temp_f')",
    type="csv",
)

uploaded_bytes, avg_price_override, raw_df = None, None, None
if uploaded_file is not None:
    raw_df = pd.read_csv(uploaded_file)
    missing = [c for c in REQUIRED_COLUMNS if c not in raw_df.columns]
    if missing:
        st.error(f"Missing required column(s): {', '.join(missing)}. "
                 f"Your file has: {', '.join(raw_df.columns)}")
        st.stop()
    if len(raw_df) < MIN_SALES_ROWS:
        st.error(f"Need at least {MIN_SALES_ROWS} rows of sales history - got {len(raw_df)}.")
        st.stop()
    uploaded_bytes = uploaded_file.getvalue()
    if "price" not in raw_df.columns:
        avg_price_override = st.number_input(
            "No 'price' column found - enter your average selling price per unit "
            "(needed to turn unit-based risk/disruption impacts into dollar figures)",
            min_value=0.01, value=20.0, step=0.5,
        )

try:
    data = load_pipeline(uploaded_bytes, avg_price_override)
except ValueError as e:
    st.error(str(e))
    st.stop()

if uploaded_file is not None:
    st.success(f"Using your uploaded data: {len(raw_df):,} rows, "
               f"{pd.to_datetime(raw_df['date']).min().date()} to {pd.to_datetime(raw_df['date']).max().date()}.")
else:
    st.info("Showing demo data from a synthetic example business - upload your own sales "
            "history above to see your real numbers.")

# ---------------------------------------------------------------- Real-time alert banner
quality_alerts = data["quality_reports"][data["quality_reports"]["emergency_cost"] > 0]
shipment_alerts = data["shipment_alerts"]
if len(quality_alerts) or len(shipment_alerts):
    st.subheader("Active Disruption Alerts")
    for row in quality_alerts.itertuples():
        st.warning(f"Day {row.day}: production quality rejection rate {row.rejection_rate:.1%} "
                   f"(expected ~2%) - ${row.emergency_cost:,.2f} in emergency overtime.")
    for row in shipment_alerts.itertuples():
        st.warning(f"{row.region} shipment delayed {row.delay_days:.0f} days beyond schedule - "
                   f"{row.still_exposed:,.0f} units still exposed after DC inventory coverage.")
else:
    st.success("No active disruption alerts this period.")
st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Executive Dashboard", "Demand Forecast", "Procurement", "Inventory",
    "Production Status", "Logistics", "Risk Analysis", "Financial Impact", "What-If Simulator",
])

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

# ---------------------------------------------------------------- Tab 5
with tab5:
    st.subheader("Production Status")
    st.caption("Drag the slider to see how the factory's capacity plan responds to a demand swing.")

    demand_adjust_pct = st.slider("Adjust demand", -50, 100, 0, step=5, format="%d%%")
    adjusted_demand = data["total_demand"] * (1 + demand_adjust_pct / 100)
    live_plan = plan_production(adjusted_demand, data["factory"], data["current_inventory"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Demand", f"{live_plan['total_demand']:,.0f} units")
    col2.metric("Factory available capacity", f"{live_plan['available_capacity']:,.0f} units")
    col3.metric("Shortfall", f"{live_plan['shortfall']:,.0f} units")
    col4.metric("Unmet (stockout)", f"{live_plan['unmet_units']:,.0f} units",
                delta_color="inverse" if live_plan["unmet_units"] > 0 else "off")

    segments = [{"lever": "Factory (in-house)", "units": live_plan["factory_units"]}]
    segments += [{"lever": item["lever"], "units": item["units"]} for item in live_plan["allocation"]]
    if live_plan["unmet_units"] > 0:
        segments.append({"lever": "UNMET (stockout)", "units": live_plan["unmet_units"]})
    seg_df = pd.DataFrame(segments)

    fig = px.bar(seg_df, x="units", y=["Demand coverage"] * len(seg_df), color="lever",
                 orientation="h", text="units", labels={"x": "Units", "y": ""})
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="")
    st.plotly_chart(fig, width='stretch')

    if len(live_plan["allocation"]):
        st.dataframe(pd.DataFrame(live_plan["allocation"]), width='stretch', hide_index=True)
    else:
        st.caption("Factory covers all demand in-house at this level - no extra levers needed.")

# ---------------------------------------------------------------- Tab 6
with tab6:
    st.subheader("Logistics Consolidation")
    plan = data["logistics_plan"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Unconsolidated cost", f"${plan['unconsolidated_cost'].sum():,.0f}")
    col2.metric("Consolidated cost", f"${plan['consolidated_cost'].sum():,.0f}")
    col3.metric("Savings from batching", f"${plan['savings'].sum():,.0f}")

    st.dataframe(plan[["region", "units", "num_orders", "containers", "leftover_mode",
                        "unconsolidated_cost", "consolidated_cost", "savings"]],
                 width='stretch', hide_index=True)

    melted = plan.melt(id_vars="region", value_vars=["unconsolidated_cost", "consolidated_cost"],
                        var_name="mode", value_name="cost")
    melted["mode"] = melted["mode"].map({"unconsolidated_cost": "Unconsolidated", "consolidated_cost": "Consolidated"})
    fig = px.bar(melted, x="region", y="cost", color="mode", barmode="group",
                 labels={"cost": "Cost ($)", "region": "Region"})
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="")
    st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Tab 7
with tab7:
    st.subheader("Risk Scenarios")
    scenarios = data["risk_scenarios"]
    top = scenarios.iloc[0]

    st.info(f"Top priority: **{top['scenario']}** - ${top['expected_loss_residual']:,.0f}/month "
            f"expected loss even after current mitigations.")

    st.dataframe(scenarios[["scenario", "probability", "unmitigated_cost", "residual_cost",
                             "expected_loss_unmitigated", "expected_loss_residual", "mitigation"]],
                 width='stretch', hide_index=True)

    fig = px.bar(scenarios, x="scenario", y="expected_loss_residual", color="scenario",
                 labels={"expected_loss_residual": "Expected loss, residual ($/mo)", "scenario": ""})
    fig.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Tab 8
with tab8:
    st.subheader("Financial Impact")
    finance = data["finance"]
    naive_total = finance["naive_cost"].sum()
    optimized_total = finance["optimized_cost"].sum()
    net_savings = naive_total - optimized_total

    col1, col2, col3 = st.columns(3)
    col1.metric("Naive baseline (no optimization)", f"${naive_total:,.0f}")
    col2.metric("Optimized (this system)", f"${optimized_total:,.0f}")
    col3.metric("Net savings", f"${net_savings:,.0f}/mo", f"{net_savings / naive_total:.1%}")

    waterfall = go.Figure(go.Waterfall(
        x=["Naive baseline"] + finance["category"].tolist() + ["Optimized total"],
        measure=["absolute"] + ["relative"] * len(finance) + ["total"],
        y=[naive_total] + (-finance["savings"]).tolist() + [optimized_total],
        text=[f"${naive_total:,.0f}"] + [f"{'+' if s < 0 else '-'}${abs(s):,.0f}" for s in finance["savings"]]
             + [f"${optimized_total:,.0f}"],
        increasing=dict(marker=dict(color="#d62728")),  # cost increase = red (bad)
        decreasing=dict(marker=dict(color="#2ca02c")),  # cost decrease/savings = green (good)
    ))
    waterfall.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(waterfall, width='stretch')

    st.dataframe(finance[["category", "naive_cost", "optimized_cost", "savings", "note"]],
                 width='stretch', hide_index=True)
    st.caption(f"If sustained monthly: ${net_savings * 12:,.0f}/year")

# ---------------------------------------------------------------- Tab 9
with tab9:
    st.subheader("What-If Simulator")
    st.caption("Move the sliders to re-run the real procurement/production/safety-stock logic "
               "under a hypothetical scenario - not a separate approximation.")

    daily_demand_std = data["sales"]["units_sold"].std()
    procurement_plan = data["procurement_plan"]
    baseline_lead_time_days = (
        (procurement_plan["units_ordered"] * procurement_plan["lead_time_weeks"]).sum()
        / procurement_plan["units_ordered"].sum() * 7
    )
    common = dict(
        baseline_demand=data["total_demand"], suppliers=data["suppliers"], factory=data["factory"],
        inventory=data["current_inventory"], daily_demand_std=daily_demand_std,
        baseline_lead_time_days=baseline_lead_time_days,
    )
    baseline_result = run_scenario(**common)

    col1, col2, col3 = st.columns(3)
    demand_pct = col1.slider("Demand", -50, 100, 0, step=5, format="%d%%", key="whatif_demand")
    price_pct = col2.slider("Raw material price", -20, 30, 0, step=5, format="%d%%", key="whatif_price")
    lead_time_pct = col3.slider("Supplier lead time", -30, 100, 0, step=10, format="%d%%", key="whatif_lead")

    live_result = run_scenario(**common, demand_pct=demand_pct, price_pct=price_pct, lead_time_pct=lead_time_pct)
    cost_delta = live_result["total_cost"] - baseline_result["total_cost"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Demand", f"{live_result['demand']:,.0f} units")
    col2.metric("Total cost", f"${live_result['total_cost']:,.0f}", f"{cost_delta:+,.0f} vs. baseline",
                delta_color="inverse")
    col3.metric("Service level", f"{live_result['service_level']:.1f}%",
                f"{live_result['service_level'] - 100:.1f} pts" if live_result["unmet_units"] > 0 else None)
    col4.metric("Safety stock needed", f"{live_result['safety_stock']:,.0f} units")

    if live_result["unmet_units"] > 0:
        st.warning(f"{live_result['unmet_units']:,.0f} units unmet at this setting - every lever "
                   f"(inventory, overtime, contractor) is maxed out.")

    st.divider()
    st.caption("Preset scenarios computed the same way, for reference:")
    st.dataframe(data["whatif_scenarios"][["scenario", "demand", "total_cost", "service_level",
                                            "unmet_units", "safety_stock", "cost_delta_vs_baseline"]],
                 width='stretch', hide_index=True)
