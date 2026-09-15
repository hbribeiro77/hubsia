# Hubsia — comparador de agregadores de IA

Site pessoal: várias tabelas, cada uma com uma geração de referência (ex.: Wan 3, 10s, 480p). Você informa preço do plano, créditos do mês e créditos da geração; o site calcula créditos/US$, gerações/US$ e gerações no mês.

## EasyPanel / Coolify

Padrão igual ao youtubeplaylist / Tina: Dockerfile na raiz, `PORT` lido do ambiente, health em `/health`.

No painel do app, configure:

| Campo | Valor |
|-------|-------|
| **Fonte** | GitHub → `hbribeiro77/hubsia` |
| **Build** | Dockerfile na raiz |
| **Porta interna** | `3000` (ou deixe o EasyPanel injetar `PORT` — o app lê essa variável) |
| **Health check** | HTTP `GET /health` |
| **Domínio** | o subdomínio gerado (ex.: `apps-hubsia....easypanel.host`) |

Variáveis de ambiente:

```env
HUBSIA_SECRET=troque-isto
HUBSIA_HTTPS=true
HUBSIA_DB_PATH=/data/hubsia.db
```

`HUBSIA_SECRET` é obrigatória: sem ela o container **nem sobe**.

#### Persistir o banco entre deploys

1. Abra o app no EasyPanel → aba **Storage** (ou **Mounts**)
2. Adicione um **Volume Mount**:
   - **Name:** `app-data`
   - **Mount path:** `/data`
3. Salve e faça **redeploy** (rebuild, não só restart)

Se aparecer **"Service is not reachable"**, confira nos logs se o uvicorn subiu e se a **porta do painel** bate com `PORT` (padrão `3000`, igual Tina / Planning / Smarttask). Falta de `HUBSIA_SECRET` também derruba o container na largada.

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
