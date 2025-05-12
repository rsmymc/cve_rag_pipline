FROM python:3.11-slim

WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for documentation/local use (optional)
EXPOSE 5000

# Flush logs immediately
ENV PYTHONUNBUFFERED=1

# Run the Flask app
CMD ["python", "server.py"]