# Multi-stage Dockerfile for Drake AI Trading
# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production
FROM python:3.12-slim AS production
LABEL org.drake.trading.version="1.0.0"
LABEL org.drake.trading.component="backend"

# Non-root user
RUN groupadd -r drake && useradd -r -g drake -s /bin/false drake

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/drake/.local
ENV PATH=/home/drake/.local/bin:$PATH

# Copy application
COPY . .

# Create directories
RUN mkdir -p /var/log/drake /var/lib/drake/data && \
    chown -R drake:drake /app /var/log/drake /var/lib/drake/data

USER drake

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
