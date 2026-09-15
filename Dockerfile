# Mesmo padrão do youtubeplaylist (FastAPI + SQLite no EasyPanel):
# PORT injetável pelo painel, health em /health, volume para o banco.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=3000 \
    HUBSIA_DB_PATH=/data/hubsia.db \
    HUBSIA_HTTPS=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /data

COPY aplicacao_fastapi_comparador_agregadores.py \
    banco_sqlite_comparacoes_e_servicos.py \
    calculos_creditos_e_geracoes_por_dolar.py \
    entrypoint_container_hubsia.sh \
    ./
COPY templates ./templates
COPY static ./static

RUN chmod +x /app/entrypoint_container_hubsia.sh

VOLUME ["/data"]

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"3000\")}/health')" || exit 1

ENTRYPOINT ["/app/entrypoint_container_hubsia.sh"]
