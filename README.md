# MCP Agent Mesh — AI-Powered Business Analyst

A production-grade multi-agent system where 5 specialized AI agents collaborate through MCP (Model Context Protocol) servers to transform raw data into actionable business insights — with full observability, guardrails, and human-in-the-loop governance.

## 30-Second Summary

Submit a business question. The **Orchestrator** plans the workflow. **Specialist agents** (Data Ingestion, Analytics, Insight Generator, Presentation) execute via MCP tool calls. The **Guardian Agent** validates every output for accuracy, PII, and bias. You get a polished report — all visible in real-time through an interactive dashboard.

```
User Question -> Orchestrator -> Data Agent -> Analytics Agent -> Guardian -> Insights -> Report
                    ^                                              |
                    +------------ Replan / Escalate ---------------+
```

## Architecture

```
+----------------------------------------------------------+
|                  Streamlit Dashboard                      |
|   Task Monitor | Agent Health | Cost | HITL Approvals     |
+--------------------------+-------------------------------+
                           | REST + WebSocket
                           v
+----------------------------------------------------------+
|                  FastAPI Gateway                          |
|   JWT Auth | Rate Limiting | Task Router | WebSocket      |
+--------------------------+-------------------------------+
                           |
+--------------------------+-------------------------------+
|               Orchestrator (LangGraph)                    |
|   Task Planner | Agent Registry | Workflow Engine          |
|                                                           |
|   +----------+ +----------+ +----------+ +----------+    |
|   |  Data    | |Analytics | | Insight  | |Present-  |    |
|   | Ingest   | |  Agent   | |Generator | |ation     |    |
|   +----+-----+ +----+-----+ +----+-----+ +----+-----+    |
|        |            |            |            |           |
|   +----+-----+ +----+-----+ +----+-----+ +----+-----+    |
|   |MCP:Data  | |MCP:Comp- | |MCP:Know- | |MCP:Rend- |    |
|   |Access    | |ute       | |ledge     | |ering     |    |
|   +----------+ +----------+ +----------+ +----------+    |
|                                                           |
|   +---------------------------------------------------+  |
|   |          Guardian Agent + MCP:Eval Guards          |  |
|   |  Data Integrity | Hallucination | PII | Bias       |  |
|   +---------------------------------------------------+  |
+----------------------------------------------------------+
                           |
+--------------------------+-------------------------------+
|                    Infrastructure                         |
|  Azure Cosmos DB | Redis Cache | Qdrant | Azure OpenAI    |
|  Blob Storage | Key Vault | Langfuse | AKS               |
+----------------------------------------------------------+
```

## Key Metrics

| Metric | Target |
|--------|--------|
| End-to-end task completion | < 60s |
| Average cost per task | < $0.05 |
| Guardian auto-approval rate | > 85% |
| Agent uptime | 99.5%+ |
| Concurrent task capacity | 50+ |

## Agents

| Agent | Role | Model | MCP Server |
|-------|------|-------|------------|
| **Orchestrator** | Decomposes tasks, delegates to agents, manages workflow | GPT-4o | -- |
| **Data Ingestion** | Connects to DBs, files, APIs; cleans and profiles data | GPT-4o-mini | `data-access-server` |
| **Analytics** | Statistical analysis, anomaly detection, trend analysis, forecasting | GPT-4o | `compute-engine-server` |
| **Insight Generator** | Transforms findings into business narratives with RAG | GPT-4o | `knowledge-base-server` |
| **Presentation** | Creates charts, compiles reports, generates dashboards | GPT-4o-mini | `rendering-engine-server` |
| **Guardian** | Validates outputs for quality, accuracy, PII, and bias | GPT-4o | `eval-guards-server` |

## MCP Tools

### Data Access Server
| Tool | Description |
|------|-------------|
| `query_database` | Execute SQL against configured databases |
| `fetch_csv` | Load CSV/Excel files |
| `profile_data` | Generate data quality reports |
| `clean_data` | Dedup, impute, normalize |
| `transform_data` | Filter, aggregate, sort, select |

### Compute Engine Server
| Tool | Description |
|------|-------------|
| `run_statistics` | Descriptive stats, correlations |
| `detect_anomalies` | Z-score, IQR, Isolation Forest |
| `analyze_trends` | Moving averages, seasonality |
| `run_regression` | Linear/logistic regression |
| `cluster_analysis` | K-means, DBSCAN clustering |
| `forecast` | Trend + seasonal forecasting |

### Knowledge Base Server
| Tool | Description |
|------|-------------|
| `retrieve_context` | RAG retrieval from vector DB |
| `search_benchmarks` | Industry benchmark comparison |
| `generate_narrative` | Structure findings into reports |

### Rendering Engine Server
| Tool | Description |
|------|-------------|
| `generate_chart` | Plotly charts (bar, line, scatter, etc.) |
| `compile_report` | Assemble reports in Markdown/HTML |
| `create_dashboard` | Interactive HTML dashboards |

### Eval Guards Server
| Tool | Description |
|------|-------------|
| `check_data_integrity` | Completeness, consistency, freshness |
| `detect_hallucination` | Cross-reference claims against source data |
| `check_pii` | Scan for emails, phone numbers, SSNs |
| `validate_statistics` | Verify statistical claims are correct |
| `score_quality` | Aggregate quality score with verdict |
| `check_bias` | Detect one-sided language and absolutes |

## Features

- **Dynamic Orchestration** -- LangGraph state machine with adaptive replanning, retries, and timeout management
- **Agent Discovery** -- Agents self-register with capabilities; orchestrator dynamically discovers available agents
- **YAML Workflows** -- Define custom analysis pipelines in YAML with dependencies, approval gates, and notifications
- **Guardian Validation** -- Every output passes through multi-check validation before delivery
- **Human-in-the-Loop** -- Configurable approval gates for low-confidence outputs, budget overruns, and PII detection
- **Cost Tracking** -- Per-agent, per-task token usage and cost tracking with budget enforcement
- **Real-Time Dashboard** -- Live agent activity feed, task timeline, cost analytics, and approval queue
- **Observability** -- Full LLM tracing via Langfuse, structured logging, Azure Monitor integration

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph |
| LLM Provider | Azure OpenAI (GPT-4o, GPT-4o-mini) |
| MCP Servers | Python + MCP SDK |
| API Gateway | FastAPI |
| Vector DB | Qdrant |
| Document DB | Azure Cosmos DB |
| Cache / PubSub | Azure Redis Cache |
| Object Storage | Azure Blob Storage |
| Dashboard | Streamlit + Plotly |
| LLM Observability | Langfuse |
| Container Orchestration | Azure Kubernetes Service |
| Infrastructure as Code | Terraform |
| CI/CD | GitHub Actions |
| Monitoring | Azure Monitor + Prometheus |
| Security | Azure Key Vault + Managed Identity |

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Azure OpenAI API key (or compatible endpoint)

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-agent-mesh.git
cd mcp-agent-mesh

# Copy environment template
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Option 1: Docker Compose (recommended)
docker compose up -d

# Option 2: Local setup
chmod +x scripts/setup_local.sh
./scripts/setup_local.sh

# Seed sample data
python scripts/seed_data.py

# Access the services
# API:       http://localhost:8000
# Dashboard: http://localhost:8501
# API Docs:  http://localhost:8000/docs
```

### Submit Your First Task

```bash
# Get an auth token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst","password":"analyst123"}' | jq -r '.access_token')

# Submit an analysis task
curl -X POST http://localhost:8000/tasks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze Q4 2025 sales data, identify trends and anomalies, generate an executive report",
    "workflow": "sales_analysis",
    "budget_limit_usd": 0.50
  }'
```

## Azure Deployment

### Infrastructure

```bash
cd terraform

# Initialize and plan
terraform init
terraform plan -var-file=environments/prod.tfvars

# Deploy
terraform apply -var-file=environments/prod.tfvars

# Configure kubectl
az aks get-credentials --resource-group rg-mcp-agent-mesh-prod --name aks-agent-mesh
```

### Deploy Services

```bash
# Build and push images
docker compose build
az acr login --name acrmcpagentmesh
docker compose push

# Deploy to AKS
kubectl apply -k k8s/
```

### Estimated Monthly Costs

| Service | Estimated Cost |
|---------|---------------|
| AKS (3 nodes, Standard_D4s_v5) | ~$390 |
| Azure OpenAI (usage-based) | ~$50-150 |
| Cosmos DB (Serverless) | ~$25 |
| Redis Cache (C1 Standard) | ~$80 |
| Blob Storage + ACR | ~$10 |
| Monitoring + Key Vault | ~$25 |
| **Total** | **~$580-680/month** |

## Workflow Definition

Define custom analysis pipelines in YAML:

```yaml
name: "Q4 Sales Analysis"
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

approval_gates:
  - after: analyze
    condition: "cost_so_far > 0.25"
  - after: final_review
    condition: "quality_score < 0.85"
```

## Adding New Agents

The system is designed for extensibility. To add a new agent:

1. **Create the MCP server** in `src/mcp_servers/your_server/` with tools
2. **Create the agent** in `src/agents/your_agent/` extending `BaseAgent`
3. **Register** the agent -- it self-registers via the Agent Registry on startup
4. **Update workflows** to include your agent in the pipeline

```python
from src.agents.base_agent import BaseAgent

class YourAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="your-agent-v1",
            name="Your Agent",
            description="What it does",
            capabilities=["capability_1", "capability_2"],
            mcp_server="your-mcp-server",
        )

    def get_system_prompt(self) -> str:
        return "Your system prompt here"

    async def execute(self, task: dict, context: dict) -> dict:
        result = await self.call_mcp_tool("your_tool", {"param": "value"})
        return {"output": result}
```

## Security

- **JWT authentication** with role-based access control (admin, analyst, viewer)
- **PII detection** and redaction by the Guardian Agent before delivery
- **Input validation** with SQL injection prevention
- **Secrets management** via Azure Key Vault with Managed Identity
- **Network isolation** via Azure VNet with Private Endpoints
- **Audit trail** for every agent action stored immutably in Cosmos DB
- **Rate limiting** and circuit breakers per agent

## Project Structure

```
mcp-agent-mesh/
├── src/
│   ├── core/                    # Config, models, registry, ledger, cost tracking
│   ├── agents/                  # 6 AI agents (orchestrator, data, analytics, etc.)
│   ├── mcp_servers/             # 5 MCP servers with 25+ tools
│   ├── api/                     # FastAPI gateway with auth, routes, websocket
│   └── dashboard/               # Streamlit dashboard with 5 pages
├── workflows/                   # YAML workflow definitions
├── data/sample/                 # Sample datasets for demo
├── tests/                       # Unit, integration, and e2e tests
├── terraform/                   # Azure infrastructure as code
├── k8s/                         # Kubernetes manifests
├── scripts/                     # Setup, seeding, demo, load testing
├── docker-compose.yaml          # Local development stack
└── .github/workflows/           # CI/CD pipelines
```

## Demo Scenarios

**Sales Performance Analysis**
> "Analyze Q4 2025 sales data, compare with Q3, find anomalies, and create an executive report"

**Market Research Summary**
> "Research the AI agent market, analyze competitor pricing, and generate a competitive landscape report"

**Financial Health Check**
> "Review monthly expenses, detect unusual spending patterns, and forecast next quarter's budget"

**Guardian Rejection Demo**
> Submit intentionally inconsistent data to see the Guardian flag issues and trigger human review

## License

MIT
