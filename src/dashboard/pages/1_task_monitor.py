"""Task Monitor Page -- Real-time task execution tracking."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Task Monitor", page_icon="\U0001f4ca", layout="wide")
st.title("\U0001f4ca Task Monitor")

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_TASKS = [
    {
        "task_id": "task_001",
        "request": "Analyze Q4 sales data",
        "status": "completed",
        "steps": [
            {"step_id": "s1", "agent": "Data Ingestion", "status": "completed", "duration": 3.2, "cost": 0.003},
            {"step_id": "s2", "agent": "Analytics", "status": "completed", "duration": 5.8, "cost": 0.012},
            {"step_id": "s3", "agent": "Guardian", "status": "completed", "duration": 2.1, "cost": 0.008},
            {"step_id": "s4", "agent": "Insight Generator", "status": "completed", "duration": 4.5, "cost": 0.015},
            {"step_id": "s5", "agent": "Presentation", "status": "completed", "duration": 3.0, "cost": 0.005},
            {"step_id": "s6", "agent": "Guardian (Final)", "status": "completed", "duration": 2.0, "cost": 0.007},
        ],
        "total_cost": 0.05,
        "quality_score": 0.92,
        "created_at": "2026-02-09T10:00:00Z",
    },
    {
        "task_id": "task_002",
        "request": "Generate market research summary",
        "status": "in_progress",
        "steps": [
            {"step_id": "s1", "agent": "Data Ingestion", "status": "completed", "duration": 2.8, "cost": 0.003},
            {"step_id": "s2", "agent": "Analytics", "status": "in_progress", "duration": 3.1, "cost": 0.008},
            {"step_id": "s3", "agent": "Guardian", "status": "pending", "duration": 0, "cost": 0},
            {"step_id": "s4", "agent": "Insight Generator", "status": "pending", "duration": 0, "cost": 0},
        ],
        "total_cost": 0.011,
        "quality_score": None,
        "created_at": "2026-02-09T10:30:00Z",
    },
]


# ---------------------------------------------------------------------------
# Timeline (Gantt chart)
# ---------------------------------------------------------------------------

def render_task_timeline(task: dict) -> go.Figure:
    """Render a horizontal stacked bar chart showing step durations."""
    colors = {
        "completed": "#2ecc71",
        "in_progress": "#3498db",
        "failed": "#e74c3c",
        "pending": "#95a5a6",
    }

    fig = go.Figure()
    for step in task["steps"]:
        fig.add_trace(
            go.Bar(
                x=[step["duration"]],
                y=[step["agent"]],
                orientation="h",
                marker_color=colors.get(step["status"], "#95a5a6"),
                text=f"{step['duration']}s | ${step['cost']:.3f}",
                textposition="inside",
                name=step["agent"],
                showlegend=False,
            )
        )

    fig.update_layout(
        title=f"Task Execution Timeline -- {task['task_id']}",
        xaxis_title="Duration (seconds)",
        barmode="stack",
        height=max(250, len(task["steps"]) * 50),
        margin=dict(l=0, r=0, t=40, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# Activity Feed
# ---------------------------------------------------------------------------

def render_activity_feed():
    """Render a scrollable live agent activity feed."""
    activities = [
        {"time": "10:00:01", "agent": "Orchestrator", "action": "Planning task decomposition", "icon": "\U0001f9e0"},
        {"time": "10:00:02", "agent": "Data Ingestion", "action": "Loading sales_q4_2025.csv", "icon": "\U0001f4e5"},
        {"time": "10:00:05", "agent": "Data Ingestion", "action": "Data profiling complete -- 98.5% quality", "icon": "\u2705"},
        {"time": "10:00:06", "agent": "Analytics", "action": "Running trend analysis", "icon": "\U0001f4c8"},
        {"time": "10:00:12", "agent": "Analytics", "action": "Anomaly detection: 3 anomalies found", "icon": "\u26a0\ufe0f"},
        {"time": "10:00:14", "agent": "Guardian", "action": "Validating analytics output -- Score: 0.92", "icon": "\U0001f6e1\ufe0f"},
        {"time": "10:00:16", "agent": "Insight Generator", "action": "Generating executive narrative", "icon": "\U0001f4a1"},
        {"time": "10:00:21", "agent": "Presentation", "action": "Compiling PDF report with 4 charts", "icon": "\U0001f4c4"},
        {"time": "10:00:24", "agent": "Guardian", "action": "Final review passed -- Score: 0.94", "icon": "\u2705"},
    ]
    for a in activities:
        st.markdown(f"`{a['time']}` {a['icon']} **{a['agent']}** -- {a['action']}")


# ---------------------------------------------------------------------------
# Task selector
# ---------------------------------------------------------------------------

task_options = {t["task_id"]: t for t in DEMO_TASKS}
selected_id = st.selectbox(
    "Select Task",
    options=list(task_options.keys()),
    format_func=lambda tid: f"{tid} -- {task_options[tid]['request']} [{task_options[tid]['status']}]",
)
selected_task = task_options[selected_id]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

col1, col2 = st.columns([2, 1])

with col1:
    st.plotly_chart(render_task_timeline(selected_task), use_container_width=True)

with col2:
    st.subheader("Live Activity Feed")
    render_activity_feed()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

completed_steps = [s for s in selected_task["steps"] if s["status"] == "completed"]
total_duration = sum(s["duration"] for s in selected_task["steps"])
total_cost = selected_task["total_cost"]
quality = selected_task["quality_score"]
step_count = len(selected_task["steps"])
completed_count = len(completed_steps)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Duration", f"{total_duration:.1f}s")
c2.metric("Total Cost", f"${total_cost:.3f}")
c3.metric("Quality Score", f"{quality:.2f}" if quality is not None else "Pending", "0.07" if quality else None)
c4.metric("Steps Completed", f"{completed_count}/{step_count}")

# ---------------------------------------------------------------------------
# Step detail table
# ---------------------------------------------------------------------------

st.subheader("Step Details")
step_rows = []
for s in selected_task["steps"]:
    status_icon = {
        "completed": "\u2705",
        "in_progress": "\U0001f535",
        "failed": "\U0001f534",
        "pending": "\u26aa",
    }.get(s["status"], "\u26aa")
    step_rows.append(
        {
            "Status": f"{status_icon} {s['status']}",
            "Agent": s["agent"],
            "Duration (s)": s["duration"],
            "Cost ($)": f"{s['cost']:.3f}",
        }
    )

st.dataframe(step_rows, use_container_width=True, hide_index=True)
