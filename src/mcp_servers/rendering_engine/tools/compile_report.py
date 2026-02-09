"""Report compilation tool.

Assembles text sections and optional Plotly chart references into a
single formatted report document.  Supports Markdown and HTML output.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internal formatters
# ---------------------------------------------------------------------------

def _compile_markdown(
    title: str,
    sections: list[dict[str, str]],
    charts: list[dict[str, str]] | None,
) -> str:
    """Compile sections into a Markdown document."""
    parts: list[str] = [f"# {title}\n"]
    parts.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n")

    for section in sections:
        heading = section["heading"]
        content = section["content"]
        parts.append(f"## {heading}\n\n{content}\n")

    if charts:
        parts.append("## Charts\n")
        for chart in charts:
            chart_title = chart.get("title", "Chart")
            parts.append(f"### {chart_title}\n")
            parts.append(f"*[Interactive Plotly chart: {chart_title}]*\n")
            parts.append(f"```json\n{chart.get('chart_json', '{}')}\n```\n")

    return "\n".join(parts)


def _compile_html(
    title: str,
    sections: list[dict[str, str]],
    charts: list[dict[str, str]] | None,
) -> str:
    """Compile sections into an HTML document with embedded Plotly charts."""
    escaped_title = html_lib.escape(title)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html_parts: list[str] = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        f"  <title>{escaped_title}</title>",
        "  <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>",
        "  <style>",
        "    body { font-family: 'Inter', Arial, sans-serif; max-width: 960px;",
        "           margin: 0 auto; padding: 2rem; color: #1a1a2e; background: #fafafa; }",
        "    h1 { border-bottom: 2px solid #e0e0e0; padding-bottom: 0.5rem; }",
        "    h2 { color: #16213e; margin-top: 2rem; }",
        "    .timestamp { color: #888; font-size: 0.9rem; }",
        "    .chart-container { margin: 1.5rem 0; min-height: 400px; }",
        "    p, li { line-height: 1.7; }",
        "  </style>",
        "</head>",
        "<body>",
        f"  <h1>{escaped_title}</h1>",
        f"  <p class=\"timestamp\">Generated: {timestamp}</p>",
    ]

    for section in sections:
        heading = html_lib.escape(section["heading"])
        # Convert simple markdown-like content to HTML paragraphs
        content = section["content"]
        content_html = _markdown_content_to_html(content)
        html_parts.append(f"  <h2>{heading}</h2>")
        html_parts.append(f"  {content_html}")

    if charts:
        html_parts.append("  <h2>Charts</h2>")
        for idx, chart in enumerate(charts):
            chart_title = html_lib.escape(chart.get("title", "Chart"))
            chart_json = chart.get("chart_json", "{}")
            div_id = f"chart-{idx}"
            html_parts.extend([
                f"  <h3>{chart_title}</h3>",
                f"  <div id=\"{div_id}\" class=\"chart-container\"></div>",
                "  <script>",
                f"    (function() {{",
                f"      var chartData = {chart_json};",
                f"      Plotly.newPlot('{div_id}', chartData.data || [], chartData.layout || {{}});",
                f"    }})();",
                "  </script>",
            ])

    html_parts.extend(["</body>", "</html>"])
    return "\n".join(html_parts)


def _markdown_content_to_html(content: str) -> str:
    """Convert simple markdown-ish content to HTML.

    Handles bullet lists (``-`` / ``*``), numbered lists, and bold
    (``**text**``).  Everything else is wrapped in ``<p>`` tags.
    """
    lines = content.split("\n")
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        # Bullet list item
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = html_lib.escape(stripped[2:])
            item = _inline_bold(item)
            html_lines.append(f"  <li>{item}</li>")
        # Numbered list item
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in (".", ")"):
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            item = html_lib.escape(stripped[2:].lstrip())
            item = _inline_bold(item)
            html_lines.append(f"  <li>{item}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            escaped = html_lib.escape(stripped)
            escaped = _inline_bold(escaped)
            html_lines.append(f"<p>{escaped}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n  ".join(html_lines)


def _inline_bold(text: str) -> str:
    """Replace ``**text**`` with ``<strong>text</strong>``."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def _count_words(text: str) -> int:
    """Count words in a string, stripping markup."""
    import re
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"[#*`\-\[\]]", " ", clean)
    return len(clean.split())


# ---------------------------------------------------------------------------
# Public tool handler
# ---------------------------------------------------------------------------

async def compile_report(arguments: dict) -> dict:
    """Compile sections and charts into a formatted report.

    Parameters (via *arguments* dict)
    ----------------------------------
    title : str
        Report title.
    sections : list[dict]
        Each dict has ``heading`` (str) and ``content`` (str).
    charts : list[dict] | None
        Each dict has ``title`` (str) and ``chart_json`` (str).
    format : str
        ``"markdown"`` or ``"html"``.  Defaults to ``"markdown"``.

    Returns
    -------
    dict
        ``{"report": str, "format": str, "word_count": int,
        "section_count": int}``
    """
    title: str = arguments["title"]
    sections: list[dict[str, str]] = arguments["sections"]
    charts: list[dict[str, str]] | None = arguments.get("charts")
    output_format: str = arguments.get("format", "markdown")

    if output_format not in ("markdown", "html"):
        output_format = "markdown"

    if output_format == "html":
        report = _compile_html(title, sections, charts)
    else:
        report = _compile_markdown(title, sections, charts)

    return {
        "report": report,
        "format": output_format,
        "word_count": _count_words(report),
        "section_count": len(sections),
    }
