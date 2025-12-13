# 🏗️ Архитектура

Deep Research — мультиагентная система на базе LangGraph для проведения глубоких исследований.

## Обзор системы

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │ Router  │→ │ Service │→ │ LangGraph│→ │ PostgreSQL      │   │
│  │         │  │         │  │ Agent    │  │ (sessions)      │   │
│  └─────────┘  └─────────┘  └──────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. API Layer (`app.py`, `router.py`)

- FastAPI приложение с CORS middleware
- REST эндпоинты для управления исследованиями
- Lifespan management для БД

### 2. Service Layer (`service.py`)

- `DeepResearchService` — бизнес-логика
- Управление сессиями исследований
- Синхронизация состояния с БД

### 3. Agent Layer (`agent/`)

Мультиагентный граф LangGraph:

```
START
  │
  ▼
┌─────────────────────┐
│  clarify_with_user  │ ←── Уточняющие вопросы
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ write_research_task │ ←── Формирование задания
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ research_supervisor │ ←── Подграф супервизора
│  ┌───────────────┐  │
│  │  supervisor   │  │     Планирование и делегирование
│  └───────────────┘  │
│         │           │
│         ▼           │
│  ┌───────────────┐  │
│  │supervisor_tools│ │     Вызов под-агентов
│  │  ┌─────────┐  │  │
│  │  │researcher│  │  │    Параллельные исследования
│  │  │subgraph │  │  │
│  │  └─────────┘  │  │
│  └───────────────┘  │
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│   generate_report   │ ←── Финальный отчёт
└─────────────────────┘
  │
  ▼
 END
```

### 4. Data Layer (`database.py`, `models.py`)

- SQLAlchemy async с asyncpg
- Модель `ResearchSession` для хранения состояния
- Автоматическое создание таблиц при старте

---

## Агентная архитектура

### Основной граф (`graph.py`)

| Node | Функция |
|------|---------|
| `clarify_with_user` | Анализирует запрос, задаёт уточняющие вопросы |
| `write_research_task` | Преобразует диалог в структурированное исследовательское задание |
| `research_supervisor` | Подграф управления исследованием |
| `generate_report` | Генерация финального Markdown отчёта |

### Подграф супервизора (`supervisor_subgraph.py`)

Управляет исследовательскими задачами:

- **supervisor** — планирует стратегию, вызывает инструменты
- **supervisor_tools** — выполняет делегирование, запускает под-агентов

**Инструменты супервизора:**
- `think_tool` — рефлексия и планирование
- `conduct_research_tool` — делегирование исследования
- `research_complete_tool` — завершение исследования

### Подграф исследователя (`researcher_subgraph.py`)

Выполняет конкретные исследовательские задачи:

- **researcher** — проводит веб-поиск
- **tools** — ToolNode для web_search_tool
- **compress_research** — сжатие результатов

**Инструменты исследователя:**
- `web_search_tool` — поиск через Tavily API
- `think_tool` — рефлексия над результатами

---

## Состояния (State)

### `DeepResearchState`
```python
messages: list[AnyMessage]           # История диалога
supervisor_messages: list[AnyMessage] # Сообщения супервизора
research_task: str                    # Исследовательское задание
raw_notes: list[str]                  # Сырые заметки
notes: list[str]                      # Обработанные заметки
final_report: str                     # Финальный отчёт
```

### `SupervisorState`
```python
supervisor_messages: list[AnyMessage]
research_task: str
notes: list[str]
raw_notes: list[str]
research_iterations: int
```

### `ResearcherState`
```python
researcher_messages: list[AnyMessage]
research_topic: str
compressed_research: str
raw_notes: list[str]
```

---

## Конфигурация моделей

| Модель | Назначение | Параметры |
|--------|------------|-----------|
| `research_model` | Основные рассуждения | gpt-oss-120b, temp=0.5 |
| `compression_model` | Сжатие результатов | gpt-oss-120b, temp=0.1 |
| `summarization_model` | Суммаризация веб-страниц | gpt-oss-20b, temp=0.3 |
| `report_model` | Генерация отчёта | gpt-oss-120b, temp=0.5 |

---

## Лимиты

| Параметр | Значение |
|----------|----------|
| `MAX_RESEARCHER_ITERATIONS` | 6 |
| `MAX_CONCURRENT_RESEARCH_UNITS` | 5 |

---

## Поток данных

1. **Запрос** → `POST /research` создаёт сессию
2. **Уточнение** → Если нужно, агент запрашивает уточнение
3. **Продолжение** → `POST /research/{id}/continue` с ответом пользователя
4. **Исследование** → Супервизор делегирует задачи исследователям
5. **Отчёт** → Финальный Markdown отчёт
6. **Завершение** → Статус `completed`, результат в `GET /research/{id}`
