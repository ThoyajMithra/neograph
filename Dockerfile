FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY app/ ./app/
COPY engine/ ./engine/
COPY storage/ ./storage/

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--no-sync", "uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
