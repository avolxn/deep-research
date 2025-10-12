FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src/

RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main

EXPOSE 8000

CMD ["python", "-m", "deep_research.main"]