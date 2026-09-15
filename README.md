# Hubsia — comparador de agregadores de IA

Site pessoal: várias tabelas, cada uma com uma geração de referência (ex.: Wan 3, 10s, 480p). Você informa preço do plano, créditos do mês e créditos da geração; o site calcula créditos/US$, gerações/US$ e gerações no mês.

## Coolify

No serviço, escolha **Dockerfile**. O Coolify faz o proxy HTTPS; o container escuta `0.0.0.0:8000`.

Variáveis:

| Variável | Valor |
|---|---|
| `HUBSIA_SECRET` | senha de acesso (obrigatória) |
| `HUBSIA_HTTPS` | `true` |
| `HUBSIA_DB_PATH` | `/data/hubsia.db` |

Persistent Storage: monte um volume em `/data` (senão o SQLite some a cada deploy). Porta do container: `8000`.

## Rodar local

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
| `HUBSIA_DB_PATH` | não | Default `data/hubsia.db` no código; no Docker, `/data/hubsia.db`. |
| `HUBSIA_HTTPS` | não | `true` atrás de HTTPS (cookie `Secure`). |

## Testes

```powershell
pytest tests -v
```
