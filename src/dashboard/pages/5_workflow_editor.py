"""Workflow Viewer/Editor."""

import streamlit as st
import yaml

st.set_page_config(page_title="Workflows", page_icon="\U0001f4cb", layout="wide")
st.title("\U0001f4cb Workflow Manager")

# ---------------------------------------------------------------------------
# Sample workflow YAML
# ---------------------------------------------------------------------------

SAMPLE_WORKFLOW = """\
name: "Q4 Sales Analysis"
description: "End-to-end sales analysis with executive report"
version: "1.0"
steps:
  - id: ingest
    agent: data-ingestion-agent
    action: ingest_and_clean
    timeout: 60s
  - id: analyze
    agent: analytics-agent
    action: full_analysis
    depends_on: [ingest]
    timeout: 90s
  - id: validate
    agent: guardian-agent
    action: validate
    depends_on: [analyze]
  - id: insights
    agent: insight-generator-agent
    action: generate
    depends_on: [validate]
  - id: report
    agent: presentation-agent
    action: compile
    depends_on: [insights]
  - id: final_review
    agent: guardian-agent
    action: final_validation
    depends_on: [report]
"""

# ---------------------------------------------------------------------------
# Preset workflows
# ---------------------------------------------------------------------------

PRESET_WORKFLOWS = {
    "Q4 Sales Analysis": SAMPLE_WORKFLOW,
    "Market Research": """\
name: "Market Research Pipeline"
description: "Gather and analyze market data"
version: "1.0"
steps:
  - id: ingest
    agent: data-ingestion-agent
    action: web_scrape
    timeout: 120s
  - id: analyze
    agent: analytics-agent
    action: market_analysis
    depends_on: [ingest]
    timeout: 120s
  - id: validate
    agent: guardian-agent
    action: validate
    depends_on: [analyze]
  - id: insights
    agent: insight-generator-agent
    action: generate
    depends_on: [validate]
""",
    "Financial Report": """\
name: "Financial Report"
description: "Quarterly financial summary with compliance checks"
version: "1.0"
steps:
  - id: ingest
    agent: data-ingestion-agent
    action: load_financials
    timeout: 60s
  - id: analyze
    agent: analytics-agent
    action: financial_analysis
    depends_on: [ingest]
    timeout: 90s
  - id: compliance
    agent: guardian-agent
    action: compliance_check
    depends_on: [analyze]
  - id: report
    agent: presentation-agent
    action: compile_financials
    depends_on: [compliance]
  - id: final_review
    agent: guardian-agent
    action: final_validation
    depends_on: [report]
""",
}

# ---------------------------------------------------------------------------
# Workflow selector
# ---------------------------------------------------------------------------

selected_preset = st.selectbox("Load Preset Workflow", list(PRESET_WORKFLOWS.keys()))
initial_yaml = PRESET_WORKFLOWS[selected_preset]

# ---------------------------------------------------------------------------
# Two-column editor + visualization
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)

with col1:
    st.subheader("Workflow Definition (YAML)")
    workflow_yaml = st.text_area("Edit Workflow", initial_yaml, height=500)

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Validate Workflow", type="primary"):
            try:
                parsed = yaml.safe_load(workflow_yaml)
                if not parsed or "steps" not in parsed:
                    st.error("Workflow must contain a 'steps' key.")
                else:
                    st.success(
                        f"Valid workflow: **{parsed.get('name', 'Unnamed')}** "
                        f"with {len(parsed['steps'])} steps"
                    )
            except yaml.YAMLError as exc:
                st.error(f"Invalid YAML: {exc}")
    with btn_col2:
        if st.button("Export YAML"):
            st.download_button(
                "Download YAML",
                data=workflow_yaml,
                file_name="workflow.yaml",
                mime="text/yaml",
            )

with col2:
    st.subheader("Workflow Visualization")
    try:
        parsed = yaml.safe_load(workflow_yaml)
        if parsed and "steps" in parsed:
            st.markdown(f"**{parsed.get('name', 'Unnamed')}** v{parsed.get('version', '?')}")
            st.caption(parsed.get("description", ""))
            st.markdown("---")

            for i, step in enumerate(parsed["steps"]):
                deps = step.get("depends_on", [])
                dep_label = ", ".join(deps) if deps else "start"
                timeout = step.get("timeout", "default")

                st.markdown(f"**Step {i + 1}: `{step['id']}`**")
                st.caption(
                    f"Agent: `{step['agent']}` | "
                    f"Action: `{step['action']}` | "
                    f"Depends on: `{dep_label}` | "
                    f"Timeout: `{timeout}`"
                )

                if i < len(parsed["steps"]) - 1:
                    st.markdown("\u2193")  # down arrow

            st.markdown("---")
            st.success(f"Pipeline complete -- {len(parsed['steps'])} steps")
        else:
            st.info("Add a 'steps' key to your workflow YAML to see the visualization.")
    except yaml.YAMLError:
        st.info("Fix the YAML syntax to see the visualization.")
