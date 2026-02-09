"""MCP Agent Mesh -- Real-Time Dashboard"""

import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(
    page_title="MCP Agent Mesh",
    page_icon="\U0001f578\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000"


def fetch_api(endpoint: str, method: str = "GET", payload: dict | None = None) -> dict | None:
    """Helper to call the backend API with error handling."""
    try:
        url = f"{API_BASE}{endpoint}"
        if method == "GET":
            resp = requests.get(url, timeout=10)
        elif method == "POST":
            resp = requests.post(url, json=payload, timeout=30)
        else:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return None
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    """Render the sidebar with task submission and active task list."""
    with st.sidebar:
        st.header("Submit Analysis Task")

        query = st.text_area(
            "Business Question",
            placeholder="e.g., Analyze Q4 sales data...",
        )
        workflow = st.selectbox(
            "Workflow",
            ["Auto-detect", "Sales Analysis", "Market Research", "Financial Report"],
        )
        budget = st.slider("Budget Limit ($)", 0.10, 2.00, 1.00, 0.10)

        if st.button("\U0001f680 Submit Task", type="primary"):
            if not query.strip():
                st.warning("Please enter a business question.")
            else:
                payload = {
                    "query": query,
                    "workflow": workflow,
                    "budget_limit": budget,
                }
                result = fetch_api("/tasks/", method="POST", payload=payload)
                if result:
                    st.success(f"Task submitted: {result.get('task_id', 'unknown')}")
                else:
                    st.info(
                        "Backend not available. Task would be submitted with: "
                        f"workflow={workflow}, budget=${budget:.2f}"
                    )

        st.divider()
        st.header("Active Tasks")

        # Attempt to fetch active tasks from the API
        tasks = fetch_api("/tasks/?status=active")
        if tasks and isinstance(tasks, list):
            for task in tasks:
                status_icon = {
                    "running": "\U0001f7e2",
                    "pending": "\U0001f7e1",
                    "failed": "\U0001f534",
                    "completed": "\u2705",
                }.get(task.get("status", ""), "\u26aa")
                st.markdown(
                    f"{status_icon} **{task.get('task_id', '')}** -- "
                    f"{task.get('request', '')[:40]}..."
                )
        else:
            st.caption("No active tasks (backend offline or empty queue).")


# ---------------------------------------------------------------------------
# Tab: Task Monitor
# ---------------------------------------------------------------------------

def show_task_monitor():
    """Display real-time task execution status."""
    st.subheader("Task Execution Monitor")

    tasks = fetch_api("/tasks/")
    if tasks and isinstance(tasks, list):
        for task in tasks:
            with st.expander(
                f"{task.get('task_id', '')} -- {task.get('status', 'unknown')}"
            ):
                st.json(task)
    else:
        st.info(
            "Backend is not reachable. Start the API server at "
            f"`{API_BASE}` to see live task data. "
            "Visit the **Task Monitor** page for a demo view."
        )


# ---------------------------------------------------------------------------
# Tab: Agent Health
# ---------------------------------------------------------------------------

def show_agent_health():
    """Display agent health summary."""
    st.subheader("Agent Health Overview")

    agents = fetch_api("/agents/health")
    if agents and isinstance(agents, list):
        cols = st.columns(3)
        for idx, agent in enumerate(agents):
            with cols[idx % 3]:
                status = agent.get("status", "unknown")
                icon = "\U0001f7e2" if status == "healthy" else "\U0001f534"
                st.markdown(f"### {icon} {agent.get('name', 'Unknown')}")
                st.metric("Uptime", agent.get("uptime", "N/A"))
                st.metric("Avg Latency", agent.get("avg_latency", "N/A"))
    else:
        st.info(
            "Backend is not reachable. Visit the **Agent Health** page for a demo view."
        )


# ---------------------------------------------------------------------------
# Tab: Cost Analytics
# ---------------------------------------------------------------------------

def show_cost_analytics():
    """Display cost analytics summary."""
    st.subheader("Cost Summary")

    costs = fetch_api("/analytics/costs")
    if costs:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Spend (7d)", f"${costs.get('total_7d', 0):.3f}")
        c2.metric("Avg Cost/Task", f"${costs.get('avg_per_task', 0):.3f}")
        c3.metric("Total Tokens", f"{costs.get('total_tokens', 0):,}")
        c4.metric("Cache Hit Rate", f"{costs.get('cache_hit_rate', 0):.0%}")
    else:
        st.info(
            "Backend is not reachable. Visit the **Cost Analytics** page for a demo view."
        )


# ---------------------------------------------------------------------------
# Tab: HITL Approval Queue
# ---------------------------------------------------------------------------

def show_hitl_queue():
    """Display pending human-in-the-loop approvals."""
    st.subheader("Pending Approvals")

    queue = fetch_api("/hitl/queue")
    if queue and isinstance(queue, list):
        pending = [h for h in queue if h.get("status") == "pending"]
        if pending:
            st.warning(f"\u26a0\ufe0f {len(pending)} approval(s) pending review")
        for req in pending:
            with st.expander(
                f"\U0001f514 {req.get('step', '')} -- Task {req.get('task_id', '')}"
            ):
                st.markdown(f"**Reason:** {req.get('reason', '')}")
                st.markdown(f"**Context:** {req.get('context', '')}")
    else:
        st.info(
            "Backend is not reachable. Visit the **Approvals** page for a demo view."
        )


# ---------------------------------------------------------------------------
# Tab: Results
# ---------------------------------------------------------------------------

def show_results():
    """Display completed task results."""
    st.subheader("Completed Results")

    results = fetch_api("/tasks/?status=completed")
    if results and isinstance(results, list):
        for result in results:
            with st.expander(
                f"{result.get('task_id', '')} -- {result.get('request', '')[:60]}"
            ):
                st.markdown(f"**Quality Score:** {result.get('quality_score', 'N/A')}")
                st.markdown(f"**Total Cost:** ${result.get('total_cost', 0):.3f}")
                if result.get("output"):
                    st.markdown("---")
                    st.markdown(result["output"])
    else:
        st.info(
            "Backend is not reachable. Visit the **Results** page tab "
            "once tasks have completed."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.title("\U0001f578\ufe0f MCP Agent Mesh -- Business Analyst")
    st.markdown("*AI-powered multi-agent system for business intelligence*")

    render_sidebar()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "\U0001f4ca Task Monitor",
            "\U0001f916 Agent Health",
            "\U0001f4b0 Cost Analytics",
            "\u2705 Approvals",
            "\U0001f4cb Results",
        ]
    )

    with tab1:
        show_task_monitor()
    with tab2:
        show_agent_health()
    with tab3:
        show_cost_analytics()
    with tab4:
        show_hitl_queue()
    with tab5:
        show_results()


if __name__ == "__main__":
    main()
