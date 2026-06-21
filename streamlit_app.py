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

BLANK = "—"
BLUE, GREEN, RED, AMBER, GRAY = "#3b82f6", "#16a34a", "#dc2626", "#d97706", "#9ca3af"

st.markdown("""
<style>
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin: 8px 0 22px 0;
}
.kpi-card {
    background: #ffffff;
    border-radius: 16px;
    border-left: 6px solid var(--kpi-color, #3b82f6);
    box-shadow: 0 4px 10px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.06);
    padding: 20px 20px 18px 20px;
}
.kpi-icon {
    font-size: 1.9rem;
    margin-bottom: 10px;
    line-height: 1;
}
.kpi-label {
    font-size: 0.8rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 10px;
}
.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1.15;
    color: var(--kpi-color, #111827);
}
.kpi-sub {
    font-size: 0.85rem;
    font-weight: 700;
    margin-top: 6px;
    color: var(--kpi-color, #6b7280);
}
.perf-table-wrap {
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.06);
    overflow: hidden;
    margin: 8px 0 20px 0;
}
table.perf-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.perf-table th {
    background: #f9fafb;
    text-align: left;
    padding: 12px 18px;
    font-size: 0.72rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid #e5e7eb;
}
.perf-table td { padding: 14px 18px; border-bottom: 1px solid #f1f1f4; vertical-align: middle; }
.perf-table tr:last-child td { border-bottom: none; }
.perf-table .metric-cell { font-weight: 700; color: #111827; white-space: nowrap; }
.perf-table .num-cell { text-align: right; font-weight: 600; color: #111827; white-space: nowrap; }
.perf-table .note-cell { color: #6b7280; font-size: 0.85rem; }
.perf-pill {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    font-size: 0.76rem; font-weight: 700; color: #fff; white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)

PERF_ROW_META = {
    "Demand forecast": ("📈", "{:,.0f} units"),
    "Procurement cost": ("💰", "${:,.0f}"),
    "Production cost": ("🏭", "${:,.0f}"),
    "Logistics cost": ("🚚", "${:,.0f}"),
    "Inventory (units)": ("📦", "{:,.0f} units"),
    "On-time delivery (%)": ("✅", "{:.0f}%"),
}


def performance_table(df):
    rows_html = []
    for row in df.itertuples():
        icon, fmt = PERF_ROW_META.get(row.metric, ("📊", "{:,.1f}"))
        pill_color = GREEN if row.accuracy_pct >= 95 else (AMBER if row.accuracy_pct >= 85 else RED)
        rows_html.append(
            f'<tr>'
            f'<td class="metric-cell">{icon} {row.metric}</td>'
            f'<td class="num-cell">{fmt.format(row.planned)}</td>'
            f'<td class="num-cell">{fmt.format(row.actual)}</td>'
            f'<td><span class="perf-pill" style="background:{pill_color}">{row.accuracy_pct:.0f}% accurate</span></td>'
            f'<td class="note-cell">{row.note}</td>'
            f'</tr>'
        )
    table_html = (
        '<div class="perf-table-wrap"><table class="perf-table">'
        '<tr><th>Metric</th><th style="text-align:right">Planned</th><th style="text-align:right">Actual</th>'
        '<th>Accuracy</th><th>Note</th></tr>'
        + "".join(rows_html) + "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


def kpi_card(label, value, sub=None, color=BLUE, icon=""):
    icon_html = f'<div class="kpi-icon">{icon}</div>' if icon else ""
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="kpi-card" style="--kpi-color:{color}">{icon_html}'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>{sub_html}</div>')


def kpi_row(cards):
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def blank_kpi_row(labels_icons):
    kpi_row([kpi_card(label, BLANK, color=GRAY, icon=icon) for label, icon in labels_icons])


@st.cache_data
def load_pipeline(sales_csv_bytes=None, avg_price_override=None):
    uploaded_df = pd.read_csv(io.BytesIO(sales_csv_bytes)) if sales_csv_bytes is not None else None
    return run_full_pipeline(uploaded_sales=uploaded_df, avg_price_override=avg_price_override)


st.title("Supply Chain Control Tower")
st.caption("Demand forecast -> procurement -> production -> inventory -> logistics -> risk -> "
           "performance, chained end-to-end.")

# ---------------------------------------------------------------- Data source
data_source = st.radio(
    "Data source",
    ["Use demo dataset", "Upload my own data"],
    index=None,
    horizontal=True,
)

data = None
uploaded_bytes, avg_price_override, raw_df = None, None, None

if data_source is None:
    st.info("Choose a data source above to populate this dashboard. "
            "The layout below is visible either way, so you can see what you'll get.")

elif data_source == "Upload my own data":
    uploaded_file = st.file_uploader(
        "Upload your sales history (CSV with 'date' and 'units_sold' columns, "
        "optionally 'promotion_flag', 'price', 'avg_temp_f')",
        type="csv",
    )
    if uploaded_file is None:
        st.info("Upload a CSV to populate this dashboard.")
    else:
        raw_df = pd.read_csv(uploaded_file)
        missing = [c for c in REQUIRED_COLUMNS if c not in raw_df.columns]
        if missing:
            st.error(f"Missing required column(s): {', '.join(missing)}. "
                     f"Your file has: {', '.join(raw_df.columns)}")
        elif len(raw_df) < MIN_SALES_ROWS:
            st.error(f"Need at least {MIN_SALES_ROWS} rows of sales history - got {len(raw_df)}.")
        else:
            uploaded_bytes = uploaded_file.getvalue()
            if "price" not in raw_df.columns:
                avg_price_override = st.number_input(
                    "No 'price' column found - enter your average selling price per unit "
                    "(needed to turn unit-based risk/disruption impacts into dollar figures)",
                    min_value=0.01, value=20.0, step=0.5,
                )
            try:
                data = load_pipeline(uploaded_bytes, avg_price_override)
                st.success(f"Using your uploaded data: {len(raw_df):,} rows, "
                           f"{pd.to_datetime(raw_df['date']).min().date()} to "
                           f"{pd.to_datetime(raw_df['date']).max().date()}.")
            except ValueError as e:
                st.error(str(e))

else:  # Use demo dataset
    try:
        data = load_pipeline()
        st.info("Showing demo data from a synthetic example business.")
    except ValueError as e:
        st.error(str(e))

# ---------------------------------------------------------------- Real-time alert banner
if data is not None:
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
else:
    st.subheader("Active Disruption Alerts")
    st.caption(f"{BLANK} no data loaded yet")
st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Executive Dashboard", "Demand Forecast", "Procurement", "Inventory",
    "Production Status", "Logistics", "Risk Analysis", "Financial Impact", "What-If Simulator",
])

# ---------------------------------------------------------------- Tab 1
with tab1:
    if data is None:
        blank_kpi_row([
            ("Demand (next 30 days)", "📦"), ("Net savings vs. naive plan", "💰"),
            ("Service level", "🎯"), ("Top risk (expected loss)", "⚠️"),
        ])
    else:
        production_plan = data["production_plan"]
        service_level = (production_plan["total_demand"] - production_plan["unmet_units"]) / production_plan["total_demand"] * 100
        net_savings = data["finance"]["savings"].sum()
        top_risk = data["risk_scenarios"].iloc[0]

        kpi_row([
            kpi_card("Demand (next 30 days)", f"{data['total_demand']:,.0f} units", color=BLUE, icon="📦"),
            kpi_card("Net savings vs. naive plan", f"${net_savings:,.0f}/mo",
                     "vs. naive baseline" if net_savings >= 0 else "costs more than naive",
                     GREEN if net_savings >= 0 else RED, icon="💰"),
            kpi_card("Service level", f"{service_level:.1f}%",
                     None if service_level >= 100 else "below 100%",
                     GREEN if service_level >= 100 else RED, icon="🎯"),
            kpi_card("Top risk (expected loss)", f"${top_risk['expected_loss_residual']:,.0f}/mo",
                     top_risk["scenario"], AMBER, icon="⚠️"),
        ])

    st.divider()
    st.subheader("Plan vs. actual this period")
    if data is None:
        st.caption(f"{BLANK} select a data source above")
    else:
        performance_table(data["performance"])

# ---------------------------------------------------------------- Tab 2
with tab2:
    st.subheader("Demand Forecast")
    if data is None:
        blank_kpi_row([("Backtest accuracy (30-day holdout)", "🎯"), ("Actuals within forecast interval", "📊")])
        st.caption(f"{BLANK} select a data source above")
    else:
        kpi_row([
            kpi_card("Backtest accuracy (30-day holdout)", f"{data['backtest_accuracy']:.1f}%", color=GREEN, icon="🎯"),
            kpi_card("Actuals within forecast interval", f"{data['backtest_within_interval']:.0f}%", color=BLUE, icon="📊"),
        ])

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
    if data is None:
        blank_kpi_row([("Total cost", "💰"), ("Suppliers used", "🏭"), ("Diversification premium", "🛡️")])
        st.caption(f"{BLANK} select a data source above")
    else:
        plan = data["procurement_plan"]
        finance_row = data["finance"].loc[data["finance"]["category"] == "Procurement"].iloc[0]

        kpi_row([
            kpi_card("Total cost", f"${plan['cost'].sum():,.0f}", color=BLUE, icon="💰"),
            kpi_card("Suppliers used", str(len(plan)), color=BLUE, icon="🏭"),
            kpi_card("Diversification premium", f"${finance_row['savings'] * -1:,.0f}",
                     "buys faster failover", AMBER, icon="🛡️"),
        ])

        st.dataframe(plan[["name", "units_ordered", "unit_cost", "cost", "pct_of_order",
                            "lead_time_weeks", "reliability_pct"]],
                     width='stretch', hide_index=True)

        fig = px.bar(plan, x="name", y="cost", color="name", text="units_ordered",
                     labels={"cost": "Cost ($)", "name": "Supplier"})
        fig.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=30, b=20), bargap=0.6)
        st.plotly_chart(fig, width='stretch')

        st.caption(finance_row["note"])

# ---------------------------------------------------------------- Tab 4
with tab4:
    st.subheader("Inventory Positioning")
    if data is None:
        blank_kpi_row([("Current holding cost", "📦"), ("Optimized holding cost", "📦"), ("Factory safety stock", "🏭")])
        st.caption(f"{BLANK} select a data source above")
    else:
        plan = data["inventory_plan"]
        finance_row = data["finance"].loc[data["finance"]["category"] == "Inventory"].iloc[0]
        cost_up = finance_row["savings"] < 0

        kpi_row([
            kpi_card("Current holding cost", f"${plan['current_holding_cost'].sum():,.0f}/mo", color=GRAY, icon="📦"),
            kpi_card("Optimized holding cost", f"${plan['optimized_holding_cost'].sum():,.0f}/mo",
                     f"{finance_row['savings']:+,.0f} vs. current",
                     RED if cost_up else GREEN, icon="📦"),
            kpi_card("Factory safety stock", f"{data['safety_stock']:,.0f} units", color=BLUE, icon="🏭"),
        ])

        st.dataframe(plan[["location", "units_on_hand", "optimized_units",
                            "current_holding_cost", "optimized_holding_cost"]],
                     width='stretch', hide_index=True)

        melted = plan.melt(id_vars="location", value_vars=["units_on_hand", "optimized_units"],
                            var_name="state", value_name="units")
        melted["state"] = melted["state"].map({"units_on_hand": "Current", "optimized_units": "Optimized"})
        fig = px.bar(melted, x="location", y="units", color="state", barmode="group",
                     labels={"units": "Units", "location": "Location"})
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="",
                           bargap=0.4, bargroupgap=0.15)
        st.plotly_chart(fig, width='stretch')

        st.caption(finance_row["note"])

# ---------------------------------------------------------------- Tab 5
with tab5:
    st.subheader("Production Status")
    st.caption("Drag the slider to see how the factory's capacity plan responds to a demand swing.")

    demand_adjust_pct = st.slider("Adjust demand", -50, 100, 0, step=5, format="%d%%",
                                   disabled=data is None)

    if data is None:
        blank_kpi_row([
            ("Demand", "📈"), ("Factory available capacity", "🏭"),
            ("Shortfall", "⚠️"), ("Unmet (stockout)", "🚨"),
        ])
        st.caption(f"{BLANK} select a data source above")
    else:
        adjusted_demand = data["total_demand"] * (1 + demand_adjust_pct / 100)
        live_plan = plan_production(adjusted_demand, data["factory"], data["current_inventory"])
        has_unmet = live_plan["unmet_units"] > 0

        kpi_row([
            kpi_card("Demand", f"{live_plan['total_demand']:,.0f} units", color=BLUE, icon="📈"),
            kpi_card("Factory available capacity", f"{live_plan['available_capacity']:,.0f} units", color=BLUE, icon="🏭"),
            kpi_card("Shortfall", f"{live_plan['shortfall']:,.0f} units",
                     color=AMBER if live_plan["shortfall"] > 0 else GREEN, icon="⚠️"),
            kpi_card("Unmet (stockout)", f"{live_plan['unmet_units']:,.0f} units",
                     "every lever maxed out" if has_unmet else "fully covered",
                     RED if has_unmet else GREEN, icon="🚨"),
        ])

        segments = [{"lever": "Factory (in-house)", "units": live_plan["factory_units"]}]
        segments += [{"lever": item["lever"], "units": item["units"]} for item in live_plan["allocation"]]
        if live_plan["unmet_units"] > 0:
            segments.append({"lever": "UNMET (stockout)", "units": live_plan["unmet_units"]})
        seg_df = pd.DataFrame(segments)

        fig = px.bar(seg_df, x="units", y=["Demand coverage"] * len(seg_df), color="lever",
                     orientation="h", text="units", labels={"x": "Units", "y": ""})
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="", bargap=0.7)
        st.plotly_chart(fig, width='stretch')

        if len(live_plan["allocation"]):
            st.dataframe(pd.DataFrame(live_plan["allocation"]), width='stretch', hide_index=True)
        else:
            st.caption("Factory covers all demand in-house at this level - no extra levers needed.")

# ---------------------------------------------------------------- Tab 6
with tab6:
    st.subheader("Logistics Consolidation")
    if data is None:
        blank_kpi_row([("Unconsolidated cost", "🚚"), ("Consolidated cost", "📦"), ("Savings from batching", "💰")])
        st.caption(f"{BLANK} select a data source above")
    else:
        plan = data["logistics_plan"]

        kpi_row([
            kpi_card("Unconsolidated cost", f"${plan['unconsolidated_cost'].sum():,.0f}", color=GRAY, icon="🚚"),
            kpi_card("Consolidated cost", f"${plan['consolidated_cost'].sum():,.0f}", color=BLUE, icon="📦"),
            kpi_card("Savings from batching", f"${plan['savings'].sum():,.0f}", color=GREEN, icon="💰"),
        ])

        st.dataframe(plan[["region", "units", "num_orders", "containers", "leftover_mode",
                            "unconsolidated_cost", "consolidated_cost", "savings"]],
                     width='stretch', hide_index=True)

        melted = plan.melt(id_vars="region", value_vars=["unconsolidated_cost", "consolidated_cost"],
                            var_name="mode", value_name="cost")
        melted["mode"] = melted["mode"].map({"unconsolidated_cost": "Unconsolidated", "consolidated_cost": "Consolidated"})
        fig = px.bar(melted, x="region", y="cost", color="mode", barmode="group",
                     labels={"cost": "Cost ($)", "region": "Region"})
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20), legend_title_text="",
                           bargap=0.4, bargroupgap=0.15)
        st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Tab 7
with tab7:
    st.subheader("Risk Scenarios")
    if data is None:
        blank_kpi_row([("Top priority scenario", "⚠️"), ("Expected loss (residual)", "💸"), ("Scenarios tracked", "📋")])
        st.caption(f"{BLANK} select a data source above")
    else:
        scenarios = data["risk_scenarios"]
        top = scenarios.iloc[0]

        kpi_row([
            kpi_card("Top priority scenario", top["scenario"], color=RED, icon="⚠️"),
            kpi_card("Expected loss (residual)", f"${top['expected_loss_residual']:,.0f}/mo",
                     "even after current mitigations", AMBER, icon="💸"),
            kpi_card("Scenarios tracked", str(len(scenarios)), color=BLUE, icon="📋"),
        ])

        st.dataframe(scenarios[["scenario", "probability", "unmitigated_cost", "residual_cost",
                                 "expected_loss_unmitigated", "expected_loss_residual", "mitigation"]],
                     width='stretch', hide_index=True)

        fig = px.bar(scenarios, x="scenario", y="expected_loss_residual", color="scenario",
                     labels={"expected_loss_residual": "Expected loss, residual ($/mo)", "scenario": ""})
        fig.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=30, b=20), bargap=0.5)
        st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Tab 8
with tab8:
    st.subheader("Financial Impact")
    if data is None:
        blank_kpi_row([("Naive baseline (no optimization)", "📊"), ("Optimized (this system)", "✅"), ("Net savings", "💰")])
        st.caption(f"{BLANK} select a data source above")
    else:
        finance = data["finance"]
        naive_total = finance["naive_cost"].sum()
        optimized_total = finance["optimized_cost"].sum()
        net_savings = naive_total - optimized_total

        kpi_row([
            kpi_card("Naive baseline (no optimization)", f"${naive_total:,.0f}", color=GRAY, icon="📊"),
            kpi_card("Optimized (this system)", f"${optimized_total:,.0f}", color=BLUE, icon="✅"),
            kpi_card("Net savings", f"${net_savings:,.0f}/mo", f"{net_savings / naive_total:.1%} vs. naive",
                     GREEN if net_savings >= 0 else RED, icon="💰"),
        ])

        waterfall = go.Figure(go.Waterfall(
            x=["Naive baseline"] + finance["category"].tolist() + ["Optimized total"],
            measure=["absolute"] + ["relative"] * len(finance) + ["total"],
            y=[naive_total] + (-finance["savings"]).tolist() + [optimized_total],
            text=[f"${naive_total:,.0f}"] + [f"{'+' if s < 0 else '-'}${abs(s):,.0f}" for s in finance["savings"]]
                 + [f"${optimized_total:,.0f}"],
            increasing=dict(marker=dict(color="#d62728")),  # cost increase = red (bad)
            decreasing=dict(marker=dict(color="#2ca02c")),  # cost decrease/savings = green (good)
        ))
        waterfall.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20), bargap=0.3)
        st.plotly_chart(waterfall, width='stretch')

        st.dataframe(finance[["category", "naive_cost", "optimized_cost", "savings", "note"]],
                     width='stretch', hide_index=True)
        st.caption(f"If sustained monthly: ${net_savings * 12:,.0f}/year")

# ---------------------------------------------------------------- Tab 9
with tab9:
    st.subheader("What-If Simulator")
    st.caption("Move the sliders to re-run the real procurement/production/safety-stock logic "
               "under a hypothetical scenario - not a separate approximation.")

    col1, col2, col3 = st.columns(3)
    demand_pct = col1.slider("Demand", -50, 100, 0, step=5, format="%d%%", key="whatif_demand",
                              disabled=data is None)
    price_pct = col2.slider("Raw material price", -20, 30, 0, step=5, format="%d%%", key="whatif_price",
                             disabled=data is None)
    lead_time_pct = col3.slider("Supplier lead time", -30, 100, 0, step=10, format="%d%%", key="whatif_lead",
                                 disabled=data is None)

    if data is None:
        blank_kpi_row([("Demand", "📈"), ("Total cost", "💰"), ("Service level", "🎯"), ("Safety stock needed", "📦")])
        st.caption(f"{BLANK} select a data source above")
    else:
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
        live_result = run_scenario(**common, demand_pct=demand_pct, price_pct=price_pct, lead_time_pct=lead_time_pct)
        cost_delta = live_result["total_cost"] - baseline_result["total_cost"]
        has_unmet = live_result["unmet_units"] > 0

        kpi_row([
            kpi_card("Demand", f"{live_result['demand']:,.0f} units", color=BLUE, icon="📈"),
            kpi_card("Total cost", f"${live_result['total_cost']:,.0f}",
                     f"{cost_delta:+,.0f} vs. baseline" if cost_delta else "at baseline",
                     RED if cost_delta > 0 else (GREEN if cost_delta < 0 else BLUE), icon="💰"),
            kpi_card("Service level", f"{live_result['service_level']:.1f}%",
                     f"{live_result['service_level'] - 100:.1f} pts" if has_unmet else None,
                     RED if has_unmet else GREEN, icon="🎯"),
            kpi_card("Safety stock needed", f"{live_result['safety_stock']:,.0f} units", color=BLUE, icon="📦"),
        ])

        if live_result["unmet_units"] > 0:
            st.warning(f"{live_result['unmet_units']:,.0f} units unmet at this setting - every lever "
                       f"(inventory, overtime, contractor) is maxed out.")

        st.divider()
        st.caption("Preset scenarios computed the same way, for reference:")
        st.dataframe(data["whatif_scenarios"][["scenario", "demand", "total_cost", "service_level",
                                                "unmet_units", "safety_stock", "cost_delta_vs_baseline"]],
                     width='stretch', hide_index=True)
