# Hubsia — comparador de agregadores de IA

Site pessoal: várias tabelas, cada uma com uma geração de referência (ex.: Wan 3, 10s, 480p). Você informa preço do plano, créditos do mês e créditos da geração; o site calcula créditos/US$, gerações/US$ e gerações no mês.

## Rodar

Python 3.12+. Na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HUBSIA_SECRET = "troque-isto"
$env:HUBSIA_DB_PATH = "data/hubsia.db"
$env:HUBSIA_HTTPS = "false"
uvicorn aplicacao_fastapi_comparador_agregadores:app --host 127.0.0.1 --port 8000
```

Abra `http://127.0.0.1:8000`, digite o secret.

## Variáveis

| Variável | Obrigatória | Significado |
|---|---|---|
| `HUBSIA_SECRET` | sim | Senha de acesso; também assina cookies. Não coloque no HTML. |
| `HUBSIA_DB_PATH` | não | Default `data/hubsia.db` (relativo ao módulo). |
| `HUBSIA_HTTPS` | não | `true` na VPS atrás de HTTPS (cookie `Secure`). |

## VPS

Uvicorn só em `127.0.0.1:8000`. Nginx/Caddy escuta 443 e faz proxy. Exemplo Nginx:

```
server {
    listen 443 ssl;
    server_name seu-dominio;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Na VPS: `HUBSIA_HTTPS=true` e o mesmo `HUBSIA_SECRET`. Backup = copiar o arquivo SQLite.

## Testes

```powershell
pytest tests -v
```
