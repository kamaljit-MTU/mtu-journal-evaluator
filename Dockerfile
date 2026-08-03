FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY data/ ./data/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with Gunicorn + Uvicorn workers for FastAPI/ASGI
# Render provides $PORT; default to 8000 for local dev
CMD ["sh", "-c", "gunicorn src.api_v2:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120"]
