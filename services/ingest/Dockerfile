# syntax=docker/dockerfile:1

# Stage 1: Build virtual environment using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install project dependencies into virtual environment
COPY pyproject.toml ./
RUN uv venv /opt/venv && uv pip install -r pyproject.toml --python /opt/venv/bin/python

# Stage 2: Minimal runtime image
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Create unprivileged application user
RUN groupadd -r platina && useradd -r -g platina -d /app -s /sbin/nologin platina

# Copy pre-built virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy service source code
COPY src/ ./src/
RUN chown -R platina:platina /app

USER platina

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
