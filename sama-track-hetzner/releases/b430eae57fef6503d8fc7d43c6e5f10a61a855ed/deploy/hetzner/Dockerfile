FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Run as a non-root service user. /data is the only persistent writable area.
RUN groupadd --gid 10001 sama \
    && useradd --uid 10001 --gid sama --create-home --shell /usr/sbin/nologin sama \
    && mkdir -p /data \
    && chown -R sama:sama /app /data

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=sama:sama . /app

USER sama

EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=3).read()" || exit 1

CMD ["sh", "-c", "exec uvicorn accounting_runtime:app --host 0.0.0.0 --port ${PORT:-8080}"]
