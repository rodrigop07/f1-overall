FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    F1_DATA_DIR=/data \
    F1_DB_PATH=/data/f1_overall.sqlite \
    AUTO_BOOTSTRAP=true

RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g 1000 -m -d /tmp appuser && \
    mkdir -p /data /app /tmp/matplotlib && \
    chown -R 1000:1000 /data /app /tmp/matplotlib

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown -R 1000:1000 /app

USER 1000:1000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
