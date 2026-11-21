FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIOMETEO_DB_PATH=/tmp/mediometeo.sqlite

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app /tmp
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8080'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=3)"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
