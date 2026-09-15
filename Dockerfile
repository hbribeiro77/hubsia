FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUBSIA_DB_PATH=/data/hubsia.db \
    HUBSIA_HTTPS=true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 hubsia \
    && mkdir -p /data \
    && chown hubsia:hubsia /data

COPY --chown=hubsia:hubsia aplicacao_fastapi_comparador_agregadores.py \
    banco_sqlite_comparacoes_e_servicos.py \
    calculos_creditos_e_geracoes_por_dolar.py \
    ./
COPY --chown=hubsia:hubsia templates ./templates
COPY --chown=hubsia:hubsia static ./static

USER hubsia
EXPOSE 8000

CMD ["sh", "-c", "uvicorn aplicacao_fastapi_comparador_agregadores:app --host 0.0.0.0 --port ${PORT:-8000}"]
