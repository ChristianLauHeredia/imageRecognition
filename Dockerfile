FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Pillow (image processing)
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Environment variable for port (compatible with platforms like Render, Railway)
ENV PORT=8000

# Command to run the application
# Use PORT environment variable if set, otherwise default to 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

