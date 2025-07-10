FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management (pinned version)
RUN pip install --no-cache-dir uv==0.7.20

# Copy project files
COPY . .

# Install the project and dependencies using uv
RUN uv sync --frozen

RUN uv pip install -e ".[postgres]"

# Ensure the virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["ni-rest", "start", "--host", "0.0.0.0", "--port", "8000"]