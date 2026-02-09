"""Dashboard creation tool.

Produces a self-contained HTML dashboard with embedded Plotly charts,
optional KPI metric cards, and a summary section.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime, timezone
from typing import Any


def _format_metric_value(value: Any) -> str:
    """Produce a display string for a KPI card value."""
    if isinstance(value, float):
        if abs(value) < 1 and value != 0:
            return f"{value:.2%}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


async def create_dashboard(arguments: dict) -> dict:
    """Create an interactive HTML dashboard.

    Parameters (via *arguments* dict)
    ----------------------------------
    title : str
        Dashboard title.
    charts : list[dict]
        Each dict has ``title`` (str) and ``chart_json`` (str).
    summary : str
        Summary text displayed at the top.
    metrics : dict | None
        Key-value pairs rendered as KPI cards.

    Returns
    -------
    dict
        ``{"html": str, "chart_count": int, "title": str}``
    """
    title: str = arguments["title"]
    charts: list[dict[str, str]] = arguments["charts"]
    summary: str = arguments["summary"]
    metrics: dict[str, Any] | None = arguments.get("metrics")

    escaped_title = html_lib.escape(title)
    escaped_summary = html_lib.escape(summary)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ----- KPI cards -----
    kpi_html = ""
    if metrics:
        cards: list[str] = []
        for key, value in metrics.items():
            label = html_lib.escape(key.replace("_", " ").title())
            display_value = html_lib.escape(_format_metric_value(value))
            cards.append(
                f'      <div class="kpi-card">\n'
                f'        <div class="kpi-value">{display_value}</div>\n'
                f'        <div class="kpi-label">{label}</div>\n'
                f'      </div>'
            )
        kpi_html = (
            '    <div class="kpi-grid">\n'
            + "\n".join(cards)
            + "\n    </div>"
        )

    # ----- Chart panels -----
    chart_panels: list[str] = []
    chart_scripts: list[str] = []
    for idx, chart in enumerate(charts):
        chart_title = html_lib.escape(chart.get("title", f"Chart {idx + 1}"))
        chart_json = chart.get("chart_json", "{}")
        div_id = f"dashboard-chart-{idx}"

        chart_panels.append(
            f'      <div class="chart-panel">\n'
            f'        <h3>{chart_title}</h3>\n'
            f'        <div id="{div_id}" class="chart-area"></div>\n'
            f'      </div>'
        )
        chart_scripts.append(
            f"      (function() {{\n"
            f"        var spec = {chart_json};\n"
            f"        Plotly.newPlot('{div_id}', spec.data || [], spec.layout || {{}}, "
            f"{{responsive: true}});\n"
            f"      }})();"
        )

    dashboard_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-card: #1e293b;
      --text-primary: #f1f5f9;
      --text-secondary: #94a3b8;
      --accent: #3b82f6;
      --accent-light: #60a5fa;
      --border: #334155;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      min-height: 100vh;
    }}
    .dashboard-header {{
      background: linear-gradient(135deg, #1e293b, #0f172a);
      padding: 2rem 3rem;
      border-bottom: 1px solid var(--border);
    }}
    .dashboard-header h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
    }}
    .dashboard-header .timestamp {{
      color: var(--text-secondary);
      font-size: 0.85rem;
    }}
    .dashboard-body {{
      padding: 2rem 3rem;
      max-width: 1400px;
      margin: 0 auto;
    }}
    .summary {{
      background: var(--bg-card);
      border-radius: 0.75rem;
      padding: 1.5rem;
      margin-bottom: 2rem;
      border: 1px solid var(--border);
      line-height: 1.7;
      color: var(--text-secondary);
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}
    .kpi-card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.25rem;
      text-align: center;
    }}
    .kpi-value {{
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--accent-light);
      margin-bottom: 0.25rem;
    }}
    .kpi-label {{
      font-size: 0.85rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
      gap: 1.5rem;
    }}
    .chart-panel {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.25rem;
    }}
    .chart-panel h3 {{
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--text-primary);
    }}
    .chart-area {{
      min-height: 350px;
      width: 100%;
    }}
    @media (max-width: 600px) {{
      .dashboard-header {{ padding: 1.5rem; }}
      .dashboard-body {{ padding: 1rem; }}
      .chart-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="dashboard-header">
    <h1>{escaped_title}</h1>
    <p class="timestamp">Generated: {timestamp}</p>
  </header>
  <main class="dashboard-body">
    <div class="summary">{escaped_summary}</div>
{kpi_html}
    <div class="chart-grid">
{chr(10).join(chart_panels)}
    </div>
  </main>
  <script>
{chr(10).join(chart_scripts)}
  </script>
</body>
</html>"""

    return {
        "html": dashboard_html,
        "chart_count": len(charts),
        "title": title,
    }
