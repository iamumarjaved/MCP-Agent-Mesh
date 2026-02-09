"""Locust-based load testing for the MCP Agent Mesh API.

Simulates concurrent users submitting analysis tasks and polling
for results.

Usage:
    # Start the API server first, then:
    locust -f scripts/load_test.py --host=http://localhost:8000

    # Headless mode (CI-friendly):
    locust -f scripts/load_test.py \\
        --host=http://localhost:8000 \\
        --headless \\
        --users 10 \\
        --spawn-rate 2 \\
        --run-time 60s
"""

from __future__ import annotations

import random
import time

from locust import HttpUser, between, task

SAMPLE_QUERIES = [
    "Analyze Q4 2025 sales data and identify top-performing products by region",
    "Generate a financial health report with key metrics and recommendations",
    "Compare our customer retention rates against industry benchmarks",
    "Identify anomalies in monthly revenue trends for the past year",
    "Break down revenue by customer segment and calculate growth rates",
    "Perform a competitive analysis of the SaaS analytics market",
    "Analyze the correlation between discount rates and sales volume",
    "Generate an executive summary of quarterly business performance",
]


class AnalystUser(HttpUser):
    """Simulates a business analyst interacting with the Agent Mesh API."""

    wait_time = between(2, 8)

    def on_start(self) -> None:
        """Called when a simulated user starts. Check health first."""
        self.submitted_task_ids: list[str] = []
        self.client.get("/health")

    @task(3)
    def submit_task(self) -> None:
        """Submit a new analysis task."""
        payload = {
            "query": random.choice(SAMPLE_QUERIES),
            "budget_limit_usd": round(random.uniform(0.50, 2.00), 2),
        }

        with self.client.post(
            "/tasks/",
            json=payload,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id")
                if task_id:
                    self.submitted_task_ids.append(task_id)
                resp.success()
            elif resp.status_code == 422:
                resp.success()  # Validation error is expected sometimes
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(5)
    def check_task_status(self) -> None:
        """Poll for the status of a previously submitted task."""
        if not self.submitted_task_ids:
            return

        task_id = random.choice(self.submitted_task_ids)
        with self.client.get(
            f"/tasks/{task_id}",
            name="/tasks/[task_id]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def list_tasks(self) -> None:
        """List all tasks."""
        self.client.get("/tasks/")

    @task(2)
    def check_agent_health(self) -> None:
        """Check agent health endpoint."""
        self.client.get("/agents/health")

    @task(1)
    def health_check(self) -> None:
        """Hit the health check endpoint."""
        self.client.get("/health")

    @task(1)
    def list_workflows(self) -> None:
        """List available workflows."""
        self.client.get("/workflows/")


class AdminUser(HttpUser):
    """Simulates an admin checking system health and costs."""

    wait_time = between(5, 15)
    weight = 1  # 1 admin per 3 analysts (default weight is 1)

    @task(3)
    def check_system_health(self) -> None:
        """Check overall system health."""
        self.client.get("/health")

    @task(2)
    def check_agent_health(self) -> None:
        """Check individual agent health."""
        self.client.get("/agents/health")

    @task(1)
    def check_cost_analytics(self) -> None:
        """Check cost analytics."""
        self.client.get("/analytics/costs")
