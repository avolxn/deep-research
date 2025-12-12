# 📡 API Reference

Deep Research API предоставляет REST эндпоинты для управления исследовательскими сессиями с поддержкой real-time стриминга через SSE.

## Base URL

```
http://localhost:8000
```

## Аутентификация

API не требует аутентификации (открытый доступ).

---

## Эндпоинты

### `GET /`

Информация о сервисе.

**Response:**

```json
{
  "title": "Deep Research API",
  "description": "API для глубокого исследования",
  "version": "1.0.0"
}
```

---

### `POST /research`

Создаёт новую сессию исследования.

**Request Body:**

```json
{
  "query": "Сравни подходы OpenAI и Anthropic к безопасности ИИ"
}
```

**Response (201):**

```json
{
  "id": 1,
  "status": "pending",
  "messages": [
    {"role": "user", "content": "Сравни подходы OpenAI и Anthropic к безопасности ИИ"}
  ],
  "research_task": null,
  "final_report": null
}
```

---

### `GET /research/{id}/stream`

Запускает исследование и стримит прогресс через SSE.

**Path Parameters:**

- `id` (int) — ID сессии исследования

**Response:** `text/event-stream`

**SSE Events:**

| Event               | Описание                                | Data                                                           |
| ------------------- | ----------------------------------------------- | -------------------------------------------------------------- |
| `status`          | Изменение статуса               | `{"status": "in_progress", "message": "..."}` или `{"status": "in_progress", "research_task": "..."}` |
| `clarification`   | Уточняющий вопрос               | `{"content": "..."}`                                         |
| `research_result` | Промежуточные результаты | `{"note": "..."}` или `{"compressed_research": "..."}`  |
| `report`          | Финальный отчёт                   | `{"final_report": "..."}`                                    |
| `done`            | Завершение                            | `{"message": "Исследование завершено"}` |
| `error`           | Ошибка                                    | `{"error": "..."}`                                           |

### `GET /research/{id}`

Получает данные сессии по ID.

**Response (200):**

```json
{
  "id": 1,
  "status": "completed",
  "messages": [...],
  "research_task": "Исследовательское задание...",
  "final_report": "# Отчёт\n\n..."
}
```

**Response (404):**

```json
{
  "detail": "Сессия исследования не найдена"
}
```

---

### `POST /research/{id}/continue`

Продолжает исследование после ответа на уточняющие вопросы (синхронно).

**Request Body:**

```json
{
  "response": "Меня интересует период 2023-2024 года"
}
```

**Response (200):** Аналогично `GET /research/{id}`

**Response (400):**

```json
{
  "detail": "Сессия не ожидает уточнения. Текущий статус: completed"
}
```

---

### `POST /research/{id}/continue/stream`

Продолжает исследование со стримингом (SSE).

**Request Body:**

```json
{
  "response": "Меня интересует период 2023-2024 года"
}
```

**Response:** `text/event-stream` (аналогично `/research/{id}/stream`)

---

### `GET /research`

Список всех исследований.

**Response (200):**

```json
[
  {
    "id": 2,
    "status": "completed",
    "messages": [...],
    "research_task": "...",
    "final_report": "..."
  },
  {
    "id": 1,
    "status": "awaiting_clarification",
    "messages": [...],
    "research_task": null,
    "final_report": null
  }
]
```

---

## Статусы сессии

| Статус               | Описание                                                                |
| -------------------------- | ------------------------------------------------------------------------------- |
| `pending`                | Сессия создана, исследование не начато         |
| `awaiting_clarification` | Агент ожидает ответа на уточняющие вопросы |
| `in_progress`            | Исследование выполняется                                 |
| `completed`              | Исследование завершено, отчёт готов              |

---

## Swagger UI

Интерактивная документация доступна по адресу:

```
http://localhost:8000/docs
```
