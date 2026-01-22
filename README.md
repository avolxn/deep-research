# 🔬 Deep Research

Multi-agent research system with real-time streaming, adaptive planning, and interactive steering.

## 🎯 Key Features

- **🔍 Interactive Clarification** — Analyzes queries, asks clarifying questions via SSE stream
- **📋 Adaptive Planning** — TODO manager with LLM-driven planning: query decomposition, prioritization, automatic task updates
- **🔄 Iterative Reflection** — Dynamic plan updates after each iteration with task addition/cancellation
- **💬 Real-time Steering** — Guide ongoing research by sending messages during execution
- **🌐 Parallel Research** — Concurrent search and analysis across multiple sources
- **📊 Structured Reports** — Final report generation with source citations
- **⚡ Real-time Streaming** — Progress tracking via Server-Sent Events

## 🏗️ Architecture

### Multi-Agent Graph

**Phase 1: Clarification and Planning**
- `clarify_with_user` — Query analysis, asks clarifying questions if needed
- `write_research_brief` — Creates research brief and initializes TODO manager

**Phase 2: Iterative Research Loop**
1. `plan_research` — Selects tasks from TODO for execution
2. `execute_tasks` — Parallel execution of research tasks
3. `process_results` — Analyzes results, checks completion conditions
4. `reflect_on_tasks` — Reflects on findings, updates plan (add/cancel tasks)

Loop continues while there are pending tasks or until iteration limit reached.

**Phase 3: Finalization**
- `generate_report` — Creates final report with citations

### Key Components

- **TODO Manager** — LLM-driven task planning with automatic updates based on findings
- **Research Subgraph** — Parallel web search via Tavily + content summarization
- **Reflection Mechanism** — Analyzes findings and adjusts research direction
- **Steering System** — User can guide research in real-time via messages

## ⚡ Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/deep-research.git
cd deep-research
cp example.env .env

# Configure API keys in .env (see Configuration below)
# Install and run
pip install -e .
python main.py
```

**API Documentation:** http://localhost:8000/docs

## 🔑 Configuration

Edit `.env` with your API keys:

**Required:**
- `YANDEX_GPT_API_KEY`, `YANDEX_GPT_FOLDER_ID` - Get from [Yandex Cloud Console](https://console.yandex.cloud/)
- `TAVILY_API_KEY` - Get from [Tavily](https://tavily.com/)

**Optional:**
- `LANGSMITH_API_KEY` - Get from [LangSmith](https://smith.langchain.com/) for LLM call tracing 
- `LANGSMITH_PROJECT` - Project name (default: `deep-research`)

<details>
<summary>📝 Example .env file</summary>

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
</details>

## 💻 API

**Base URL:** `http://localhost:8000`  
**Interactive Docs:** http://localhost:8000/docs

### Main Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Start new research session |
| `GET` | `/stream/{session_id}` | SSE stream for real-time updates |
| `POST` | `/message` | Send steering message or answer clarification |
| `GET` | `/plan/{session_id}` | Get current research plan (TODO list) |
| `GET` | `/status/{session_id}` | Get research status and progress |

### Configuration

Edit `src/deep_research/ml/config.py`:
- `MAX_RESEARCHER_ITERATIONS = 6` — Maximum research iterations
- `MAX_TASKS_PER_ITERATION = 5` — Tasks per iteration
- `MAX_CONCURRENT_RESEARCH_UNITS = 3` — Parallel tasks
- `MIN_CONTENT_LENGTH = 100` — Minimum content length for acceptance

## 📊 Benchmarking

Evaluate on [deep_research_bench](https://github.com/Ayanami0730/deep_research_bench):

```bash
# Setup (one time)
git clone https://github.com/Ayanami0730/deep_research_bench.git

# Run evaluation
cd evaluation && ./run.sh

# Test on 10 queries
./run.sh --limit 10

# Use custom evaluator
./run.sh --evaluator gpt-oss-120b

# Resume after crash
./run.sh --resume
```

**Manual steps:**
```bash
# 1. Generate research
python run_benchmark.py --limit 10

# 2. Convert format
python process_results.py --input results/deep_research_results.jsonl

# 3. Evaluate
python evaluate_benchmark.py --evaluator gpt-oss-120b
```

Results: `deep_research_bench/results/race/deep-research/`

## 🛠️ Development

```bash
# Run with auto-reload
python main.py

# View logs
tail -f backend_logs.txt

# Enable LangSmith tracing
export LANGSMITH_TRACING=true
```

## 📄 License

MIT — see [LICENSE](LICENSE)