"""Agent Health Dashboard."""

import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Agent Health", page_icon="\U0001f916", layout="wide")
st.title("\U0001f916 Agent Health Matrix")

# ---------------------------------------------------------------------------
# Demo agent data
# ---------------------------------------------------------------------------

AGENTS = [
    {
        "name": "Orchestrator",
        "status": "healthy",
        "uptime": "99.9%",
        "avg_latency": "120ms",
        "error_rate": "0.1%",
        "tasks_completed": 142,
        "model": "GPT-4o",
    },
    {
        "name": "Data Ingestion",
        "status": "healthy",
        "uptime": "99.8%",
        "avg_latency": "3200ms",
        "error_rate": "0.5%",
        "tasks_completed": 156,
        "model": "GPT-4o-mini",
    },
    {
        "name": "Analytics",
        "status": "healthy",
        "uptime": "99.7%",
        "avg_latency": "5500ms",
        "error_rate": "0.8%",
        "tasks_completed": 148,
        "model": "GPT-4o",
    },
    {
        "name": "Insight Generator",
        "status": "healthy",
        "uptime": "99.9%",
        "avg_latency": "4200ms",
        "error_rate": "0.3%",
        "tasks_completed": 139,
        "model": "GPT-4o",
    },
    {
        "name": "Presentation",
        "status": "healthy",
        "uptime": "99.8%",
        "avg_latency": "2800ms",
        "error_rate": "0.2%",
        "tasks_completed": 135,
        "model": "GPT-4o-mini",
    },
    {
        "name": "Guardian",
        "status": "healthy",
        "uptime": "100%",
        "avg_latency": "1800ms",
        "error_rate": "0.0%",
        "tasks_completed": 284,
        "model": "GPT-4o",
    },
]

# ---------------------------------------------------------------------------
# Health cards in a 3-column grid
# ---------------------------------------------------------------------------

for row_start in range(0, len(AGENTS), 3):
    cols = st.columns(3)
    for offset, col in enumerate(cols):
        idx = row_start + offset
        if idx >= len(AGENTS):
            break
        agent = AGENTS[idx]
        with col:
            status_color = "\U0001f7e2" if agent["status"] == "healthy" else "\U0001f534"
            st.markdown(f"### {status_color} {agent['name']}")
            st.caption(f"Model: {agent['model']}")

            m1, m2 = st.columns(2)
            m1.metric("Uptime", agent["uptime"])
            m2.metric("Avg Latency", agent["avg_latency"])

            m3, m4 = st.columns(2)
            m3.metric("Error Rate", agent["error_rate"])
            m4.metric("Tasks", agent["tasks_completed"])

# ---------------------------------------------------------------------------
# Latency comparison bar chart
# ---------------------------------------------------------------------------

st.divider()

latency_values = [float(a["avg_latency"].replace("ms", "")) for a in AGENTS]
agent_names = [a["name"] for a in AGENTS]
bar_colors = ["#3498db", "#2ecc71", "#e67e22", "#9b59b6", "#1abc9c", "#e74c3c"]

fig = go.Figure(
    data=[
        go.Bar(
            x=agent_names,
            y=latency_values,
            marker_color=bar_colors[: len(AGENTS)],
            text=[f"{v:.0f}ms" for v in latency_values],
            textposition="outside",
        )
    ]
)
fig.update_layout(
    title="Average Latency by Agent (ms)",
    yaxis_title="Latency (ms)",
    height=400,
    margin=dict(t=50, b=40),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Task completion comparison
# ---------------------------------------------------------------------------

st.subheader("Task Completion Volume")

task_counts = [a["tasks_completed"] for a in AGENTS]
fig2 = go.Figure(
    data=[
        go.Bar(
            x=agent_names,
            y=task_counts,
            marker_color=bar_colors[: len(AGENTS)],
            text=[str(c) for c in task_counts],
            textposition="outside",
        )
    ]
)
fig2.update_layout(
    yaxis_title="Tasks Completed",
    height=350,
    margin=dict(t=30, b=40),
)
st.plotly_chart(fig2, use_container_width=True)
