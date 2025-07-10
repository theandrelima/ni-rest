FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY . .

# Install the project and dependencies using uv
RUN uv sync --frozen

RUN uv pip install -e ".[postgres]"

# Ensure the virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["ni-rest", "start", "--host", "0.0.0.0", "--port", "8000"]