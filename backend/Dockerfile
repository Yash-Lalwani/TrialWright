FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY data/ /app/data/
RUN uv sync --frozen --no-dev
ENV DATABASE_URL=sqlite:////app/var/preflight.db LLM_CACHE_DIR=/app/data/llm_cache
RUN mkdir -p /app/var
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn preflight.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
