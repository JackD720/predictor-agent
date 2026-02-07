FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY *.py ./

# Cloud Run uses PORT env var (default 8080)
ENV PORT=8080
ENV TRADER_MODE=live

EXPOSE 8080

# Start as HTTP server for Cloud Scheduler
CMD ["python", "live_trader.py", "--serve", "--port", "8080"]