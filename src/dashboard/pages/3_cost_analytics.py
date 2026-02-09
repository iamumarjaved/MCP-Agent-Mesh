"""Cost Analytics Dashboard."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Cost Analytics", page_icon="\U0001f4b0", layout="wide")
st.title("\U0001f4b0 Cost Analytics")

# ---------------------------------------------------------------------------
# Demo cost data
# ---------------------------------------------------------------------------

_agents = ["Data Ingestion", "Analytics", "Insight Generator", "Presentation", "Guardian", "Orchestrator"]
_dates = pd.date_range("2026-02-05", periods=5)

cost_data = pd.DataFrame(
    {
        "Agent": _agents * 5,
        "Date": _dates.repeat(6),
        "Cost": [
            0.003, 0.012, 0.015, 0.005, 0.015, 0.002,
            0.004, 0.014, 0.013, 0.006, 0.016, 0.002,
            0.003, 0.011, 0.014, 0.005, 0.014, 0.002,
            0.005, 0.015, 0.016, 0.007, 0.017, 0.003,
            0.004, 0.013, 0.015, 0.006, 0.015, 0.002,
        ],
        "Tokens": [
            450, 1200, 1500, 600, 1400, 300,
            500, 1400, 1300, 700, 1500, 350,
            420, 1100, 1400, 580, 1350, 280,
            550, 1500, 1600, 750, 1600, 380,
            480, 1300, 1500, 650, 1450, 320,
        ],
    }
)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

total_spend = cost_data["Cost"].sum()
total_tokens = int(cost_data["Tokens"].sum())
avg_cost_per_task = total_spend / 5  # 5 tasks in demo window

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Spend (7d)", f"${total_spend:.3f}", "-12%")
c2.metric("Avg Cost/Task", f"${avg_cost_per_task:.3f}")
c3.metric("Total Tokens", f"{total_tokens:,}")
c4.metric("Cache Hit Rate", "42%", "+5%")

# ---------------------------------------------------------------------------
# Cost distribution + daily breakdown
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)

with col1:
    agent_costs = cost_data.groupby("Agent")["Cost"].sum().reset_index()
    fig_pie = px.pie(
        agent_costs,
        values="Cost",
        names="Agent",
        title="Cost Distribution by Agent",
        hole=0.35,
    )
    fig_pie.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    daily = cost_data.groupby(["Date", "Agent"])["Cost"].sum().reset_index()
    fig_bar = px.bar(
        daily,
        x="Date",
        y="Cost",
        color="Agent",
        title="Daily Cost Breakdown",
        barmode="stack",
    )
    fig_bar.update_layout(xaxis_title="Date", yaxis_title="Cost ($)")
    st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------------------------
# Token usage table
# ---------------------------------------------------------------------------

st.subheader("Token Usage Breakdown")

token_summary = (
    cost_data.groupby("Agent")
    .agg({"Tokens": "sum", "Cost": "sum"})
    .reset_index()
)
token_summary["Avg Cost/Token"] = (
    (token_summary["Cost"] / token_summary["Tokens"] * 1000).round(4)
)
token_summary.columns = ["Agent", "Total Tokens", "Total Cost ($)", "Cost per 1K Tokens ($)"]
token_summary = token_summary.sort_values("Total Cost ($)", ascending=False)

st.dataframe(token_summary, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Cumulative cost over time
# ---------------------------------------------------------------------------

st.subheader("Cumulative Cost Over Time")

daily_total = cost_data.groupby("Date")["Cost"].sum().reset_index()
daily_total["Cumulative"] = daily_total["Cost"].cumsum()

fig_cum = go.Figure()
fig_cum.add_trace(
    go.Scatter(
        x=daily_total["Date"],
        y=daily_total["Cumulative"],
        mode="lines+markers",
        fill="tozeroy",
        line=dict(color="#3498db", width=2),
        marker=dict(size=8),
    )
)
fig_cum.update_layout(
    xaxis_title="Date",
    yaxis_title="Cumulative Cost ($)",
    height=350,
    margin=dict(t=20, b=40),
)
st.plotly_chart(fig_cum, use_container_width=True)
