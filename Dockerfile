ARG PYTHON_VERSION=3.12-slim
FROM python:${PYTHON_VERSION}

# tzdata: para que "hace 14 días" y las horas se calculen en hora de Chile
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Santiago \
    PYTHONUNBUFFERED=1 \
    JT_DB=/datos/ofertas.db \
    JT_HOST=0.0.0.0 \
    JT_PUERTO=8765

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Chromium sin ventana para Laborum (laborum.py), con sus librerías del sistema
RUN python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

COPY *.py ./
COPY web/ ./web/
# UID/GID fijos 1000 (no de sistema): coinciden con la migración del volumen (chown -R 1000:1000 /datos, NOTAS.md)
RUN mkdir -p /datos /respaldos && \
    groupadd --gid 1000 jt && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin jt && \
    chown -R jt:jt /app /datos /respaldos
    
VOLUME ["/datos", "/respaldos"]
EXPOSE 8765

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/estado', timeout=4)"

USER jt
CMD ["python", "servidor.py", "--no-abrir"]
