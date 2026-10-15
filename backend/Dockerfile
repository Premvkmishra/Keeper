FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package sources before installation so the explicit package layout is buildable.
COPY pyproject.toml .
COPY __init__.py .
COPY app/ app/
COPY mock_bank/ mock_bank/
COPY witness/ witness/
COPY render-start.sh .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY armoriq/ armoriq/

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

CMD ["sh", "render-start.sh"]
