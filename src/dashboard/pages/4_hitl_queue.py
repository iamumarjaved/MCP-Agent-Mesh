"""Human-in-the-Loop Approval Queue."""

import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Approval Queue", page_icon="\u2705", layout="wide")
st.title("\u2705 Human-in-the-Loop Approval Queue")

# ---------------------------------------------------------------------------
# Demo HITL requests
# ---------------------------------------------------------------------------

HITL_QUEUE = [
    {
        "id": "hitl_001",
        "task_id": "task_003",
        "step": "Analytics Output",
        "reason": "Guardian score below threshold (0.58)",
        "quality_score": 0.58,
        "created_at": "2026-02-09T10:15:00Z",
        "status": "pending",
        "context": (
            "Anomaly detection returned 45% anomaly rate which seems unusually high. "
            "Statistical validation flagged 2 claims as unverifiable."
        ),
    },
    {
        "id": "hitl_002",
        "task_id": "task_005",
        "step": "Final Report",
        "reason": "PII detected in output",
        "quality_score": 0.72,
        "created_at": "2026-02-09T10:20:00Z",
        "status": "pending",
        "context": (
            "Email addresses found in the generated report text. "
            "3 instances of potential PII detected."
        ),
    },
    {
        "id": "hitl_003",
        "task_id": "task_007",
        "step": "Insight Generator Output",
        "reason": "Budget threshold exceeded",
        "quality_score": 0.88,
        "created_at": "2026-02-09T10:25:00Z",
        "status": "pending",
        "context": (
            "Task cost ($1.85) approaching budget limit ($2.00). "
            "Requesting approval before continuing to presentation step."
        ),
    },
]

# ---------------------------------------------------------------------------
# Pending count
# ---------------------------------------------------------------------------

pending = [h for h in HITL_QUEUE if h["status"] == "pending"]
if pending:
    st.warning(f"\u26a0\ufe0f {len(pending)} approval(s) pending review")
else:
    st.success("No pending approvals. All clear!")

# ---------------------------------------------------------------------------
# Pending items
# ---------------------------------------------------------------------------

for req in HITL_QUEUE:
    if req["status"] != "pending":
        continue

    score = req["quality_score"]
    score_color = "green" if score >= 0.85 else "orange" if score >= 0.60 else "red"

    with st.expander(
        f"\U0001f514 {req['step']} -- Task {req['task_id']} (Score: {score})",
        expanded=True,
    ):
        st.markdown(f"**Reason:** {req['reason']}")
        st.markdown(f"**Context:** {req['context']}")
        st.markdown(f"**Quality Score:** :{score_color}[{score:.2f}]")
        st.markdown(f"**Created:** {req['created_at']}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("\u2705 Approve", key=f"approve_{req['id']}"):
                st.success("Approved! Pipeline will continue.")
        with col2:
            if st.button("\u274c Reject", key=f"reject_{req['id']}"):
                st.error("Rejected. Task will be cancelled.")
        with col3:
            if st.button("\U0001f504 Reprocess", key=f"reprocess_{req['id']}"):
                st.info("Sent back for reprocessing.")

        notes = st.text_area("Reviewer Notes", key=f"notes_{req['id']}")

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Approval History")

history = [
    {
        "id": "hitl_000",
        "task_id": "task_001",
        "step": "Analytics",
        "decision": "approved",
        "score": 0.61,
        "reviewer": "admin",
        "resolved_at": "2026-02-09T09:45:00Z",
    },
    {
        "id": "hitl_prev_001",
        "task_id": "task_002",
        "step": "Final Report",
        "decision": "rejected",
        "score": 0.42,
        "reviewer": "admin",
        "resolved_at": "2026-02-09T09:30:00Z",
    },
    {
        "id": "hitl_prev_002",
        "task_id": "task_004",
        "step": "Insight Generator",
        "decision": "approved",
        "score": 0.78,
        "reviewer": "analyst",
        "resolved_at": "2026-02-09T08:55:00Z",
    },
]

for h in history:
    icon = "\u2705" if h["decision"] == "approved" else "\u274c"
    st.markdown(
        f"{icon} **{h['step']}** (Task {h['task_id']}) -- "
        f"{h['decision']} by {h['reviewer']} at {h['resolved_at']} "
        f"(score: {h['score']:.2f})"
    )
