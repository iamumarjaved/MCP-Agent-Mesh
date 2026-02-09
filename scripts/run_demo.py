"""Interactive demo for the MCP Agent Mesh.

Submits a sample analysis task to the API and streams progress updates
via WebSocket, printing each agent activity and step transition to the
terminal.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --query "Analyze Q4 2025 sales performance"
    python scripts/run_demo.py --local  # Run orchestrator directly, no API needed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx

API_BASE = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

SAMPLE_QUERIES = [
    "Analyze Q4 2025 sales data and identify top-performing products by region",
    "Generate a financial health report comparing our metrics to industry benchmarks",
    "Perform market research on competitive landscape in the SaaS analytics segment",
]


def print_header() -> None:
    print()
    print("=" * 60)
    print("  MCP Agent Mesh -- Interactive Demo")
    print("=" * 60)
    print()


def print_step(label: str, detail: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"  [{timestamp}] {label:<20} {detail}")


async def submit_task(query: str, budget: float = 1.00) -> dict | None:
    """Submit a task to the API and return the response."""
    payload = {
        "query": query,
        "budget_limit_usd": budget,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_BASE}/tasks/", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return None
    except httpx.HTTPStatusError as exc:
        print(f"  API error: {exc.response.status_code} {exc.response.text}")
        return None


async def stream_updates(task_id: str) -> None:
    """Connect to WebSocket and stream task progress updates."""
    try:
        import websockets
    except ImportError:
        print("  websockets package not installed -- skipping live updates")
        print("  Install with: pip install websockets")
        return

    try:
        async with websockets.connect(f"{WS_URL}/{task_id}") as ws:
            print()
            print("  Streaming live updates...")
            print("  " + "-" * 50)

            async for message in ws:
                try:
                    event = json.loads(message)
                    event_type = event.get("event_type", "unknown")
                    data = event.get("data", {})

                    if event_type == "agent_activity":
                        print_step(
                            f"Agent: {data.get('agent', '?')}",
                            data.get("message", ""),
                        )
                    elif event_type == "step_update":
                        status = data.get("status", "?")
                        step_id = data.get("step_id", "?")
                        print_step(f"Step: {step_id}", f"-> {status}")
                    elif event_type == "task_complete":
                        print()
                        print_step("COMPLETE", f"Task {task_id} finished")
                        break
                    else:
                        print_step(event_type, json.dumps(data)[:80])

                except json.JSONDecodeError:
                    print(f"  (raw message: {message[:100]})")

    except Exception as exc:
        print(f"  WebSocket connection failed: {exc}")
        print("  The API server may not be running.")


async def run_local_demo(query: str) -> None:
    """Run the orchestrator locally without the API server."""
    print("  Running in local mode (no API server required)...")
    print()

    # Import the orchestrator directly
    try:
        from src.agents.orchestrator.agent import OrchestratorAgent
        from src.core.cost_tracker import CostTracker
    except ImportError as exc:
        print(f"  Import error: {exc}")
        print("  Make sure you are in the project root and deps are installed.")
        sys.exit(1)

    orchestrator = OrchestratorAgent()
    orchestrator.cost_tracker = CostTracker()

    print_step("PLANNING", f"Query: {query[:60]}...")

    task_payload = {
        "request": query,
        "budget_limit_usd": 1.00,
    }

    try:
        result = await orchestrator.execute(task=task_payload, context={})
    except Exception as exc:
        print_step("ERROR", str(exc))
        return

    print()
    print("  " + "-" * 50)
    print_step("STATUS", result.get("status", "unknown"))

    if result.get("final_output"):
        output = result["final_output"]
        print_step("SUMMARY", output.get("summary", "")[:80])

    if result.get("cost_breakdown"):
        breakdown = result["cost_breakdown"]
        total = breakdown.get("total_cost_usd", 0)
        print_step("COST", f"${total:.6f}")

    print()


async def run_api_demo(query: str) -> None:
    """Run the demo against the API server."""
    # Check if API is reachable
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/health", timeout=5)
            resp.raise_for_status()
    except Exception:
        print("  API server is not reachable at", API_BASE)
        print("  Falling back to local mode...")
        print()
        await run_local_demo(query)
        return

    print_step("SUBMITTING", f"Query: {query[:60]}...")

    result = await submit_task(query)
    if result is None:
        print("  Failed to submit task. Is the API server running?")
        return

    task_id = result.get("task_id", "unknown")
    print_step("ACCEPTED", f"Task ID: {task_id}")

    # Stream updates
    await stream_updates(task_id)

    # Fetch final result
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/tasks/{task_id}", timeout=30)
            if resp.status_code == 200:
                final = resp.json()
                print()
                print("  Final Result:")
                print("  " + json.dumps(final, indent=2, default=str)[:500])
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Agent Mesh Interactive Demo")
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="Business question to analyse",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run orchestrator locally (no API server needed)",
    )
    args = parser.parse_args()

    query = args.query or SAMPLE_QUERIES[0]

    print_header()
    print(f"  Query: {query}")
    print()

    if args.local:
        asyncio.run(run_local_demo(query))
    else:
        asyncio.run(run_api_demo(query))


if __name__ == "__main__":
    main()
