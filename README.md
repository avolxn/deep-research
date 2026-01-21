# 🔬 Deep Research

**Deep Research** — A multi-agent system for conducting deep research with real-time streaming and adaptive planning. Uses YandexGPT and Tavily Search for information analysis and structuring.

## 🚀 Key Features

- **🔍 Interactive Clarification** — Analyzes queries, asks clarifying questions via SSE stream
- **📋 Adaptive Planning** — TODO manager with LLM-driven planning: query decomposition, prioritization, automatic task updates based on findings
- **🔄 Iterative Reflection** — Dynamic plan updates after each iteration with task addition/cancellation
- **💬 Bidirectional Communication** — Real-time research steering by user (clarification/steering)
- **🌐 Parallel Web Research** — Concurrent search and analysis of multiple sources
- **📊 Structured Reporting** — Final report generation with source citations
- **⚡ Real-time Streaming** — Progress tracking in real-time via Server-Sent Events

## 📦 Installation

### Prerequisites

- **Python 3.11+**
- **Poetry** for dependency management

```bash
git clone https://github.com/yourusername/deep-research.git
cd deep-research
cp example.env .env
```

### Configure `.env`

```env
# YandexGPT
YANDEX_GPT_API_KEY=your_api_key
YANDEX_GPT_FOLDER_ID=your_folder_id

# Tavily Search
TAVILY_API_KEY=your_tavily_key

# LangSmith Tracing (optional)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=deep-research
```

## 🔑 Getting API Keys

### YandexGPT

1. Create a service account in [Yandex Cloud Console](https://console.yandex.cloud/)
2. Get API key and Folder ID
3. Add to `.env`

### Tavily API

1. Sign up at [Tavily](https://tavily.com/)
2. Get API key from your dashboard

### LangSmith (optional)

1. Sign up at [LangSmith](https://smith.langchain.com/)
2. Create a project and get API key
3. Add to `.env` for LLM call tracing

## ▶️ Running

### Installation

```bash
pip install -e .
```

### Start Server

```bash
python main.py
```

## 💻 API

- **Base URL:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`

### Endpoints

| Method   | Path                     | Description                                                      |
| -------- | ------------------------ | ---------------------------------------------------------------- |
| `POST` | `/research`            | Create new research session                                      |
| `GET`  | `/stream/{session_id}` | SSE stream for real-time updates                                 |
| `POST` | `/message`             | Send message to active session (clarification/steering response) |
| `POST` | `/cancel/{session_id}` | Cancel active research                                           |
| `GET`  | `/sessions`            | List all active sessions                                         |
| `GET`  | `/plan/{session_id}`   | Get current research plan (TODO list)                            |
| `GET`  | `/status/{session_id}` | Get research status and progress                                 |

### Usage Example

```bash
# Create research
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "research AI applications in medicine"}'

# Connect to stream
curl -N http://localhost:8000/stream/{session_id}

# Send clarification response
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "message": "Focus on diagnostics and drug development"}'

# Get research plan
curl http://localhost:8000/plan/{session_id}
```

## 📡 SSE Events

Stream sends the following event types:

- `connected` - connection established
- `research_started` - research started
- `clarification_needed` - user clarification required
- `research_continued` - research continued after clarification
- `node_started` - graph node execution started
- `node_completed` - node completed
- `research_brief_created` - research brief created
- `task_results` - task execution results
- `research_progress` - research progress (pending/completed tasks)
- `research_complete` - research completed with final report
- `error` - error occurred
- `heartbeat` - keepalive message (every 5 seconds)

## 🏗️ Architecture

### Multi-Agent Graph

**Phase 1: Clarification and Planning**

- `clarify_with_user` — Query analysis, clarifying questions (if needed → END, waits for response)
- `write_research_brief` — Create research brief and initialize TODO manager

**Phase 2: Iterative Research**

Loop with reflection and dynamic plan updates:

1. `plan_research` — Select tasks from TODO for execution
2. `execute_tasks` — Parallel execution of research tasks
3. `process_results` — Analyze results, check completion conditions
4. `reflect_on_tasks` — Reflection, plan update (add/cancel tasks), return to step 1

Loop continues while there are pending tasks or iteration limit not reached.

**Phase 3: Finalization**

- `generate_report` — Create final report with citations

### TODO Manager with LLM Planning

**Capabilities:**

- Query decomposition — automatic breakdown into subtasks
- Prioritization — task ranking by importance
- Dynamic updates — add/cancel tasks based on findings
- Task types: `focus`, `exclude`, `prioritize`, `stop_searching`, `guidance`

### Research Subgraph

**Components:**

- Web search via Tavily API
- Content summarization with content filter error handling
- Reasoning for analysis and information structuring

### Multi-Level Processing Pipeline

```
Parallel Search → Deduplication → Compression → Report with Citations
```

### Configuration

- `MAX_RESEARCHER_ITERATIONS = 6` - maximum research iterations
- `MAX_TASKS_PER_ITERATION = 5` - tasks per iteration
- `MAX_CONCURRENT_RESEARCH_UNITS = 3` - parallel tasks
- `MIN_CONTENT_LENGTH = 100` - minimum content length for acceptance

## 🛠️ Tech Stack

| Category          | Technologies                                       |
| ----------------- | -------------------------------------------------- |
| **ML**      | LangGraph, LangChain, YandexGPT, Tavily, LangSmith |
| **Backend** | FastAPI, Pydantic, asyncio, SSE                    |

## 🏗️ Project Structure

```
deep-research/
├── src/deep_research/
│   ├── api/
│   │   ├── app.py              # FastAPI application
│   │   ├── router.py           # API endpoints
│   │   ├── service.py          # Business logic and session management
│   │   └── schemas.py          # Pydantic schemas
│   └── ml/
│       ├── graph.py            # Main LangGraph graph
│       ├── researcher_subgraph.py  # Research subgraph
│       ├── state.py            # State definition
│       ├── tools.py            # Tools (web search, think)
│       ├── prompts.py          # LLM prompts
│       ├── config.py           # Configuration
│       ├── todo_manager.py     # Task management
│       └── utils.py            # Utilities
├── tests/
├── .env
├── example.env
├── pyproject.toml
└── README.md
```

## 🔧 Development

### Run

```bash
python main.py
```

### View logs

Logs are saved to `backend_logs.txt`

### LangSmith tracing

With `LANGSMITH_TRACING=true` enabled, all LLM calls and graph operations will be tracked in [LangSmith UI](https://smith.langchain.com/)

## 📄 License

MIT — see [LICENSE](LICENSE)
