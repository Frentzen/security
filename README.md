# Security Research Agent

An autonomous research agent that generates practical security implementation guides for developers and DevOps engineers. The agent uses LangGraph for orchestration, Claude (Anthropic) as the LLM, and Tavily for web search.

## Features

- Generates comprehensive, copy-paste ready security implementation guides
- Adapts to different project types (API-only, full-stack, microservices, OSS projects)
- Automatically discovers tech stacks from repository analysis
- Cites authoritative sources (OWASP, RFCs, official documentation)
- Self-improves through LLM-based critique loops
- Supports multiple frameworks and deployment targets

## Installation

1. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and configure your API keys:

```bash
cp .env.example .env
```

3. Set your API keys in `.env`:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

## Usage

### Command Line

```bash
# Using a JSON input file
python -m src.main -i examples/simple_api.json -o output/jwt_guide.md

# Using command line arguments
python -m src.main \
  --topic "JWT Authentication" \
  --backend "FastAPI" \
  --database "PostgreSQL" \
  --deployment "Docker" \
  --project-type "api_only" \
  -o output/jwt_fastapi.md

# Full-stack example
python -m src.main \
  --topic "OAuth2 Implementation" \
  --backend "Django" \
  --frontend "React" \
  --database "PostgreSQL" \
  --deployment "Kubernetes" \
  --project-type "fullstack_app"

# OSS project analysis
python -m src.main \
  --topic "API Rate Limiting" \
  --project-url "https://github.com/apache/fineract" \
  --project-name "Apache Fineract" \
  --project-type "opensource_project"
```

### Programmatic Usage

```python
from src.agent.graph import run_agent

context = {
    "project_type": "api_only",
    "tech_stack": {
        "backend": "FastAPI",
        "database": "PostgreSQL",
        "deployment": "Docker"
    },
    "security_topic": "JWT Authentication"
}

report = run_agent(context)
print(report)
```

## Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_type` | string | Yes | One of: `api_only`, `fullstack_app`, `opensource_project`, `microservice` |
| `project_name` | string | No | Project name (for OSS projects) |
| `project_url` | string | No | GitHub/GitLab URL for analysis |
| `tech_stack.backend` | string | No | Backend framework (e.g., "FastAPI", "Django") |
| `tech_stack.frontend` | string | No | Frontend framework (e.g., "React", "Vue") |
| `tech_stack.database` | string | No | Database (e.g., "PostgreSQL", "MongoDB") |
| `tech_stack.deployment` | string | No | Deployment target (e.g., "Docker", "Kubernetes") |
| `security_topic` | string | Yes | Security topic to research |
| `requirements` | object | No | Additional constraints |

## Output

The agent generates a comprehensive markdown document with:

1. **Overview** - Brief summary of the implementation
2. **Prerequisites** - Required dependencies and setup
3. **Implementation Guide** - Step-by-step instructions with code examples
4. **Deployment** - Docker/Kubernetes configurations
5. **Common Issues** - Troubleshooting guide
6. **Security Notes** - Key security considerations
7. **References** - All cited sources with URLs

## Architecture

```
┌─────────────────┐
│ Context Analyzer│
└────────┬────────┘
         │
    ┌────▼────┐
    │Discovery│ (conditional)
    │  Flow   │
    └────┬────┘
         │
┌────────▼────────┐
│     Planner     │
└────────┬────────┘
         │
┌────────▼────────┐
│   Researcher    │
└────────┬────────┘
         │
┌────────▼────────┐
│   Synthesizer   │
└────────┬────────┘
         │
┌────────▼────────┐
│    Architect    │
└────────┬────────┘
         │
┌────────▼────────┐
│    Validator    │◄──────┐
└────────┬────────┘       │
         │                │
    ┌────▼────┐      ┌────┴────┐
    │  Pass   │      │ Revision│
    └────┬────┘      └─────────┘
         │
┌────────▼────────┐
│Report Generator │
└─────────────────┘
```

## Example Topics

- JWT Authentication
- API Rate Limiting
- OAuth2 Implementation
- CSRF Protection
- SQL Injection Prevention
- XSS Prevention
- Input Validation
- Secrets Management
- TLS/SSL Configuration
- Container Security

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | - | Anthropic API key (required) |
| `TAVILY_API_KEY` | - | Tavily API key (required) |
| `LOG_LEVEL` | INFO | Logging level |
| `MAX_ITERATIONS` | 3 | Max revision iterations |

## Project Structure

```
security/
├── src/
│   ├── agent/
│   │   ├── state.py      # State definition
│   │   ├── nodes.py      # Node implementations
│   │   ├── edges.py      # Conditional routing
│   │   └── graph.py      # LangGraph workflow
│   ├── services/
│   │   ├── claude_client.py   # Claude API wrapper
│   │   └── tavily_client.py   # Tavily API wrapper
│   ├── utils/
│   │   └── helpers.py    # Utility functions
│   └── main.py           # Entry point
├── examples/             # Example input files
├── tests/                # Test files
├── config.py             # Configuration
└── requirements.txt      # Dependencies
```

## License

MIT
