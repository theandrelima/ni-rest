FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better Docker cache
COPY pyproject.toml uv.lock ./

# Install uv for faster dependency management (use latest available version)
RUN pip install --no-cache-dir uv==0.7.20

# Install the project and dependencies using uv
RUN uv sync --frozen

# Copy the rest of the project files
COPY . .

RUN uv pip install -e ".[postgres]"

# Ensure the virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["ni-rest", "start", "--host", "0.0.0.0", "--port", "8000"]