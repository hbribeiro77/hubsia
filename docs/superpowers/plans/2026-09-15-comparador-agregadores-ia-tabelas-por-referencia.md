# Comparador de agregadores de IA (Hubsia) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Site pessoal (FastAPI + SQLite + HTML) em que, com um secret, o usuário cria várias tabelas de comparação — cada uma com uma geração de referência — e vê créditos/US$, gerações/US$ e gerações mensais calculados no servidor.

**Architecture:** Um processo FastAPI serve HTML (Jinja2) e POSTs com Post/Redirect/Get. SQLite guarda `comparacoes` e `servicos`. Cálculos ficam num módulo puro. Sessão é um cookie assinado com `HUBSIA_SECRET`. Uvicorn escuta em `127.0.0.1`; o proxy da VPS faz HTTPS.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, Jinja2, python-multipart, itsdangerous, SQLite, pytest, httpx, HTML/CSS.

## Global Constraints

- Python 3.12+; UI em português do Brasil; sem SPA e sem JSON no v1.
- Secret único `HUBSIA_SECRET` (nunca no HTML); cookie `hubsia_session`, `HttpOnly`, `SameSite=Lax`, `Secure` só se `HUBSIA_HTTPS=true`; 30 dias.
- SQLite em `HUBSIA_DB_PATH` (default `data/hubsia.db`); `PRAGMA foreign_keys = ON`; `ON DELETE CASCADE` em `servicos.comparacao_id`.
- Nomes de arquivo exatamente os da spec; arquivos na raiz do projeto (sem pacote `app/`).
- Números: `Decimal`; vírgula ou ponto na entrada; exibição pt-BR; inteiro sem casas; senão `ROUND_HALF_UP` em 2 casas.
- Validação inválida: HTTP 422 re-renderizando o form (sem gravar). Recurso ausente: 404 HTML. Sem sessão: 302 para `/login`.
- Fora de escopo: contas, catálogo compartilhado de planos, destaque do melhor custo, Docker, CSRF token.
- Ambiente: Windows PowerShell; comandos abaixo são para PowerShell. Commits com `git commit -m "..."` (sem heredoc bash).

## File map

| Arquivo | Responsabilidade |
|---|---|
| `calculos_creditos_e_geracoes_por_dolar.py` | Parse, validação numérica, fórmulas, formatação pt-BR |
| `banco_sqlite_comparacoes_e_servicos.py` | Schema e CRUD SQLite |
| `aplicacao_fastapi_comparador_agregadores.py` | Factory FastAPI, sessão, rotas HTML |
| `templates/pagina_base_hubsia.html` | Chrome autenticado (nav + flash) |
| `templates/pagina_login_secret.html` | Tela do secret |
| `templates/pagina_lista_comparacoes.html` | Lista de tabelas |
| `templates/pagina_formulario_nova_comparacao.html` | Criar comparação |
| `templates/pagina_tabela_comparacao_servicos.html` | Metadados + form serviço + tabela 7 colunas |
| `templates/pagina_nao_encontrada.html` | 404 (necessário; spec descreve a tela e não listou o arquivo) |
| `static/estilos_comparador_agregadores.css` | Layout mobile/desktop |
| `tests/test_calculos_creditos_e_geracoes_por_dolar.py` | Unidade das contas |
| `tests/test_rotas_autenticacao_e_crud_comparacoes.py` | Rotas com TestClient |
| `tests/conftest.py` | App/client com secret e SQLite temporários |
| `requirements.txt`, `pytest.ini`, `.gitignore`, `README.md` | Runtime, testes, deploy |

---

### Task 1: Módulo de cálculos

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `calculos_creditos_e_geracoes_por_dolar.py`
- Create: `tests/test_calculos_creditos_e_geracoes_por_dolar.py`

**Interfaces:**
- Consumes: nada (primeiro módulo)
- Produces:
  - `class EntradaInvalidaCalculo(ValueError)`
  - `@dataclass(frozen=True) class ResultadoCalculoAgregador` com `creditos_por_dolar: Decimal`, `geracoes_mensais: Decimal`, `geracoes_por_dolar: Decimal`
  - `calcular_creditos_e_geracoes(custo_mensal_usd: Decimal, creditos_mes: Decimal, custo_referencia_creditos: Decimal) -> ResultadoCalculoAgregador`
  - `parsear_decimal_entrada(texto: str) -> Decimal` (vírgula ou ponto; levanta `EntradaInvalidaCalculo` se vazio, não-finito ou ≤ 0)
  - `formatar_numero_pt_br(valor: Decimal) -> str`

- [ ] **Step 1: Scaffold de teste**

Crie `requirements.txt`:

```
fastapi
uvicorn[standard]
jinja2
python-multipart
itsdangerous
pytest
httpx
```

Crie `pytest.ini`:

```
[pytest]
pythonpath = .
```

Crie `.gitignore`:

```
.venv/
__pycache__/
.pytest_cache/
data/
.env
*.pyc
```

Crie `tests/test_calculos_creditos_e_geracoes_por_dolar.py`:

```python
from decimal import Decimal

import pytest

from calculos_creditos_e_geracoes_por_dolar import (
    EntradaInvalidaCalculo,
    calcular_creditos_e_geracoes,
    formatar_numero_pt_br,
    parsear_decimal_entrada,
)


def test_higgsfield_30_1200_10():
    resultado = calcular_creditos_e_geracoes(
        Decimal("30"), Decimal("1200"), Decimal("10")
    )
    assert resultado.creditos_por_dolar == Decimal("40")
    assert resultado.geracoes_mensais == Decimal("120")
    assert resultado.geracoes_por_dolar == Decimal("4")


def test_geracoes_por_dolar_equivale_creditos_por_dolar_sobre_referencia():
    resultado = calcular_creditos_e_geracoes(
        Decimal("30"), Decimal("1200"), Decimal("10")
    )
    assert resultado.geracoes_por_dolar == (
        resultado.creditos_por_dolar / Decimal("10")
    )


@pytest.mark.parametrize(
    "custo_mensal, creditos, referencia",
    [
        (Decimal("0"), Decimal("1200"), Decimal("10")),
        (Decimal("-1"), Decimal("1200"), Decimal("10")),
        (Decimal("30"), Decimal("0"), Decimal("10")),
        (Decimal("30"), Decimal("-5"), Decimal("10")),
        (Decimal("30"), Decimal("1200"), Decimal("0")),
        (Decimal("30"), Decimal("1200"), Decimal("-10")),
    ],
)
def test_rejeita_zero_ou_negativo(custo_mensal, creditos, referencia):
    with pytest.raises(EntradaInvalidaCalculo):
        calcular_creditos_e_geracoes(custo_mensal, creditos, referencia)


def test_formatar_inteiro_sem_casas():
    assert formatar_numero_pt_br(Decimal("40")) == "40"
    assert formatar_numero_pt_br(Decimal("1200")) == "1200"
    assert formatar_numero_pt_br(Decimal("4.00")) == "4"


def test_formatar_arredonda_half_up_duas_casas():
    assert formatar_numero_pt_br(Decimal("3.333")) == "3,33"
    assert formatar_numero_pt_br(Decimal("3.335")) == "3,34"


def test_parsear_aceita_virgula_e_ponto():
    assert parsear_decimal_entrada("30,5") == Decimal("30.5")
    assert parsear_decimal_entrada("30.5") == Decimal("30.5")


def test_parsear_rejeita_vazio_e_nao_positivo():
    with pytest.raises(EntradaInvalidaCalculo):
        parsear_decimal_entrada("")
    with pytest.raises(EntradaInvalidaCalculo):
        parsear_decimal_entrada("0")
    with pytest.raises(EntradaInvalidaCalculo):
        parsear_decimal_entrada("-2")
    with pytest.raises(EntradaInvalidaCalculo):
        parsear_decimal_entrada("abc")
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest tests/test_calculos_creditos_e_geracoes_por_dolar.py::test_higgsfield_30_1200_10 -v
```

Expected: FAIL (`ModuleNotFoundError: calculos_creditos_e_geracoes_por_dolar`).

- [ ] **Step 3: Implementação mínima**

Crie `calculos_creditos_e_geracoes_por_dolar.py`:

```python
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class EntradaInvalidaCalculo(ValueError):
    pass


@dataclass(frozen=True)
class ResultadoCalculoAgregador:
    creditos_por_dolar: Decimal
    geracoes_mensais: Decimal
    geracoes_por_dolar: Decimal


def parsear_decimal_entrada(texto: str) -> Decimal:
    bruto = (texto or "").strip().replace(",", ".")
    try:
        valor = Decimal(bruto)
    except InvalidOperation as exc:
        raise EntradaInvalidaCalculo("número inválido") from exc
    if not valor.is_finite() or valor <= 0:
        raise EntradaInvalidaCalculo("número inválido")
    return valor


def calcular_creditos_e_geracoes(
    custo_mensal_usd: Decimal,
    creditos_mes: Decimal,
    custo_referencia_creditos: Decimal,
) -> ResultadoCalculoAgregador:
    for valor in (custo_mensal_usd, creditos_mes, custo_referencia_creditos):
        if not valor.is_finite() or valor <= 0:
            raise EntradaInvalidaCalculo("número inválido")
    creditos_por_dolar = creditos_mes / custo_mensal_usd
    geracoes_mensais = creditos_mes / custo_referencia_creditos
    geracoes_por_dolar = geracoes_mensais / custo_mensal_usd
    return ResultadoCalculoAgregador(
        creditos_por_dolar=creditos_por_dolar,
        geracoes_mensais=geracoes_mensais,
        geracoes_por_dolar=geracoes_por_dolar,
    )


def formatar_numero_pt_br(valor: Decimal) -> str:
    quantizado = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantizado == quantizado.to_integral_value():
        return str(int(quantizado))
    return f"{quantizado:.2f}".replace(".", ",")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests/test_calculos_creditos_e_geracoes_por_dolar.py -v
```

Expected: PASS (todos os testes do arquivo).

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt pytest.ini .gitignore calculos_creditos_e_geracoes_por_dolar.py tests/test_calculos_creditos_e_geracoes_por_dolar.py
git commit -m "feat: calcula creditos e geracoes por dolar da referencia"
```

Se o diretório ainda não for repositório git: `git init` antes do `git add`. Não altere `git config`.

---

### Task 2: Persistência SQLite

**Files:**
- Create: `banco_sqlite_comparacoes_e_servicos.py`
- Create: `tests/test_banco_sqlite_comparacoes_e_servicos.py`

**Interfaces:**
- Consumes: `Decimal` da stdlib
- Produces:
  - `@dataclass class Comparacao` com `id: int`, `nome: str`, `referencia: str`, `criado_em: str`, `atualizado_em: str`
  - `@dataclass class Servico` com `id: int`, `comparacao_id: int`, `nome: str`, `custo_mensal_usd: Decimal`, `creditos_mes: Decimal`, `custo_referencia_creditos: Decimal`
  - `class BancoComparacoes`:
    - `__init__(self, caminho: str) -> None`
    - `inicializar(self) -> None`
    - `criar_comparacao(self, nome: str, referencia: str) -> Comparacao`
    - `listar_comparacoes(self) -> list[Comparacao]` (mais recentes primeiro, por `id` desc)
    - `obter_comparacao(self, comparacao_id: int) -> Comparacao | None`
    - `atualizar_comparacao(self, comparacao_id: int, nome: str, referencia: str) -> Comparacao | None`
    - `excluir_comparacao(self, comparacao_id: int) -> bool`
    - `criar_servico(self, comparacao_id: int, nome: str, custo_mensal_usd: Decimal, creditos_mes: Decimal, custo_referencia_creditos: Decimal) -> Servico`
    - `listar_servicos(self, comparacao_id: int) -> list[Servico]` (`id` asc)
    - `obter_servico(self, servico_id: int) -> Servico | None`
    - `atualizar_servico(self, servico_id: int, nome: str, custo_mensal_usd: Decimal, creditos_mes: Decimal, custo_referencia_creditos: Decimal) -> Servico | None`
    - `excluir_servico(self, servico_id: int) -> bool`

- [ ] **Step 1: Teste que falha**

Crie `tests/test_banco_sqlite_comparacoes_e_servicos.py`:

```python
from decimal import Decimal

from banco_sqlite_comparacoes_e_servicos import BancoComparacoes


def test_criar_listar_e_apagar_comparacao_em_cascata(tmp_path):
    banco = BancoComparacoes(str(tmp_path / "hubsia.db"))
    banco.inicializar()
    comparacao = banco.criar_comparacao("Wan 3 480p", "Wan 3, 10s, 480p")
    assert comparacao.id >= 1
    assert comparacao.nome == "Wan 3 480p"
    assert banco.obter_comparacao(comparacao.id) is not None
    banco.criar_servico(
        comparacao.id,
        "Higgsfield",
        Decimal("30"),
        Decimal("1200"),
        Decimal("10"),
    )
    assert len(banco.listar_servicos(comparacao.id)) == 1
    assert banco.excluir_comparacao(comparacao.id) is True
    assert banco.obter_comparacao(comparacao.id) is None
    assert banco.listar_servicos(comparacao.id) == []


def test_nomes_de_servico_podem_repetir(tmp_path):
    banco = BancoComparacoes(str(tmp_path / "hubsia.db"))
    banco.inicializar()
    comparacao = banco.criar_comparacao("A", "ref A")
    banco.criar_servico(comparacao.id, "Higgsfield", Decimal("30"), Decimal("1200"), Decimal("10"))
    banco.criar_servico(comparacao.id, "Higgsfield", Decimal("60"), Decimal("3000"), Decimal("10"))
    assert len(banco.listar_servicos(comparacao.id)) == 2


def test_obter_inexistente_retorna_none(tmp_path):
    banco = BancoComparacoes(str(tmp_path / "hubsia.db"))
    banco.inicializar()
    assert banco.obter_comparacao(999) is None
    assert banco.obter_servico(999) is None
    assert banco.excluir_comparacao(999) is False
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```powershell
pytest tests/test_banco_sqlite_comparacoes_e_servicos.py::test_criar_listar_e_apagar_comparacao_em_cascata -v
```

Expected: FAIL (`ModuleNotFoundError: banco_sqlite_comparacoes_e_servicos`).

- [ ] **Step 3: Implementação mínima**

Crie `banco_sqlite_comparacoes_e_servicos.py`:

```python
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Comparacao:
    id: int
    nome: str
    referencia: str
    criado_em: str
    atualizado_em: str


@dataclass
class Servico:
    id: int
    comparacao_id: int
    nome: str
    custo_mensal_usd: Decimal
    creditos_mes: Decimal
    custo_referencia_creditos: Decimal


class BancoComparacoes:
    def __init__(self, caminho: str) -> None:
        self.caminho = caminho

    def _conectar(self) -> sqlite3.Connection:
        Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        return conexao

    def inicializar(self) -> None:
        with self._conectar() as conexao:
            conexao.executescript(
                """
                CREATE TABLE IF NOT EXISTS comparacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    referencia TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS servicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comparacao_id INTEGER NOT NULL,
                    nome TEXT NOT NULL,
                    custo_mensal_usd REAL NOT NULL,
                    creditos_mes REAL NOT NULL,
                    custo_referencia_creditos REAL NOT NULL,
                    FOREIGN KEY (comparacao_id) REFERENCES comparacoes(id) ON DELETE CASCADE
                );
                """
            )

    def criar_comparacao(self, nome: str, referencia: str) -> Comparacao:
        agora = _agora_iso()
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "INSERT INTO comparacoes (nome, referencia, criado_em, atualizado_em) VALUES (?, ?, ?, ?)",
                (nome, referencia, agora, agora),
            )
            return self._comparacao_por_id(conexao, cursor.lastrowid)

    def listar_comparacoes(self) -> list[Comparacao]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT * FROM comparacoes ORDER BY id DESC"
            ).fetchall()
            return [self._row_comparacao(linha) for linha in linhas]

    def obter_comparacao(self, comparacao_id: int) -> Comparacao | None:
        with self._conectar() as conexao:
            return self._comparacao_por_id(conexao, comparacao_id)

    def atualizar_comparacao(
        self, comparacao_id: int, nome: str, referencia: str
    ) -> Comparacao | None:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "UPDATE comparacoes SET nome = ?, referencia = ?, atualizado_em = ? WHERE id = ?",
                (nome, referencia, _agora_iso(), comparacao_id),
            )
            if cursor.rowcount == 0:
                return None
            return self._comparacao_por_id(conexao, comparacao_id)

    def excluir_comparacao(self, comparacao_id: int) -> bool:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "DELETE FROM comparacoes WHERE id = ?", (comparacao_id,)
            )
            return cursor.rowcount > 0

    def criar_servico(
        self,
        comparacao_id: int,
        nome: str,
        custo_mensal_usd: Decimal,
        creditos_mes: Decimal,
        custo_referencia_creditos: Decimal,
    ) -> Servico:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                """
                INSERT INTO servicos (
                    comparacao_id, nome, custo_mensal_usd, creditos_mes, custo_referencia_creditos
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    comparacao_id,
                    nome,
                    float(custo_mensal_usd),
                    float(creditos_mes),
                    float(custo_referencia_creditos),
                ),
            )
            return self._servico_por_id(conexao, cursor.lastrowid)

    def listar_servicos(self, comparacao_id: int) -> list[Servico]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT * FROM servicos WHERE comparacao_id = ? ORDER BY id ASC",
                (comparacao_id,),
            ).fetchall()
            return [self._row_servico(linha) for linha in linhas]

    def obter_servico(self, servico_id: int) -> Servico | None:
        with self._conectar() as conexao:
            return self._servico_por_id(conexao, servico_id)

    def atualizar_servico(
        self,
        servico_id: int,
        nome: str,
        custo_mensal_usd: Decimal,
        creditos_mes: Decimal,
        custo_referencia_creditos: Decimal,
    ) -> Servico | None:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                """
                UPDATE servicos
                SET nome = ?, custo_mensal_usd = ?, creditos_mes = ?, custo_referencia_creditos = ?
                WHERE id = ?
                """,
                (
                    nome,
                    float(custo_mensal_usd),
                    float(creditos_mes),
                    float(custo_referencia_creditos),
                    servico_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
            return self._servico_por_id(conexao, servico_id)

    def excluir_servico(self, servico_id: int) -> bool:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "DELETE FROM servicos WHERE id = ?", (servico_id,)
            )
            return cursor.rowcount > 0

    def _comparacao_por_id(
        self, conexao: sqlite3.Connection, comparacao_id: int | None
    ) -> Comparacao | None:
        if comparacao_id is None:
            return None
        linha = conexao.execute(
            "SELECT * FROM comparacoes WHERE id = ?", (comparacao_id,)
        ).fetchone()
        return None if linha is None else self._row_comparacao(linha)

    def _servico_por_id(
        self, conexao: sqlite3.Connection, servico_id: int | None
    ) -> Servico | None:
        if servico_id is None:
            return None
        linha = conexao.execute(
            "SELECT * FROM servicos WHERE id = ?", (servico_id,)
        ).fetchone()
        return None if linha is None else self._row_servico(linha)

    def _row_comparacao(self, linha: sqlite3.Row) -> Comparacao:
        return Comparacao(
            id=linha["id"],
            nome=linha["nome"],
            referencia=linha["referencia"],
            criado_em=linha["criado_em"],
            atualizado_em=linha["atualizado_em"],
        )

    def _row_servico(self, linha: sqlite3.Row) -> Servico:
        return Servico(
            id=linha["id"],
            comparacao_id=linha["comparacao_id"],
            nome=linha["nome"],
            custo_mensal_usd=Decimal(str(linha["custo_mensal_usd"])),
            creditos_mes=Decimal(str(linha["creditos_mes"])),
            custo_referencia_creditos=Decimal(str(linha["custo_referencia_creditos"])),
        )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests/test_banco_sqlite_comparacoes_e_servicos.py tests/test_calculos_creditos_e_geracoes_por_dolar.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add banco_sqlite_comparacoes_e_servicos.py tests/test_banco_sqlite_comparacoes_e_servicos.py
git commit -m "feat: persiste comparacoes e servicos no sqlite"
```

---

### Task 3: Factory FastAPI, sessão e login

**Files:**
- Create: `aplicacao_fastapi_comparador_agregadores.py`
- Create: `templates/pagina_base_hubsia.html`
- Create: `templates/pagina_login_secret.html`
- Create: `templates/pagina_lista_comparacoes.html` (lista vazia autenticada; CRUD entra na Task 4)
- Create: `static/estilos_comparador_agregadores.css` (mínimo: só para o login não nascer sem CSS; o layout mobile fecha na Task 6)
- Create: `tests/conftest.py`
- Create: `tests/test_rotas_autenticacao_e_crud_comparacoes.py`

**Interfaces:**
- Consumes: `BancoComparacoes.inicializar`; `HUBSIA_SECRET` só via parâmetro `secret` de `criar_app` (testes nunca leem o secret da VPS)
- Produces:
  - `COOKIE_SESSAO = "hubsia_session"`
  - `COOKIE_FLASH = "hubsia_flash"`
  - `SESSAO_MAX_AGE = 30 * 24 * 60 * 60`
  - `criar_app(*, secret: str, db_path: str, https: bool = False) -> FastAPI`
  - `criar_app_de_ambiente() -> FastAPI` (lê `HUBSIA_SECRET`, `HUBSIA_DB_PATH` default `data/hubsia.db`, `HUBSIA_HTTPS=true`)
  - `__getattr__(name)` devolve `criar_app_de_ambiente()` quando `name == "app"` (para `uvicorn aplicacao_fastapi_comparador_agregadores:app` sem executar o env na importação dos testes)
  - Rotas nesta task: `GET/POST /login`, `POST /logout`, `GET /` (exige sessão; HTML da lista, ainda pode estar vazia)
  - Cookie de sessão: valor assinado com `itsdangerous.URLSafeTimedSerializer(secret, salt="hubsia-sessao")` payload `{"auth": True}`; comparar secret do form com `hmac.compare_digest`
  - `definir_cookie_sessao(response, secret, https)` / `apagar_cookie_sessao(response, https)`
  - Flash helpers: `definir_cookie_flash(response, secret, mensagem, https)` e `ler_e_consumir_flash(request, response, secret)` — usados na Task 6; já podem existir nesta task para o `pagina_base` ter `{% if flash %}`

- [ ] **Step 1: Testes de autenticação que falham**

Crie `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from aplicacao_fastapi_comparador_agregadores import criar_app

SECRET_TESTE = "segredo-teste"


@pytest.fixture
def app(tmp_path):
    return criar_app(
        secret=SECRET_TESTE,
        db_path=str(tmp_path / "hubsia.db"),
        https=False,
    )


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def client_autenticado(client):
    client.post("/login", data={"secret": SECRET_TESTE}, follow_redirects=False)
    return client
```

Crie `tests/test_rotas_autenticacao_e_crud_comparacoes.py` (só auth nesta task):

```python
from tests.conftest import SECRET_TESTE


def test_raiz_sem_sessao_redireciona_login(client):
    resposta = client.get("/", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/login"


def test_login_secret_invalido_permanece_na_tela(client):
    resposta = client.post("/login", data={"secret": "errado"}, follow_redirects=False)
    assert resposta.status_code == 200
    assert "Secret inválido." in resposta.text


def test_login_secret_valido_seta_cookie_e_vai_para_lista(client):
    resposta = client.post(
        "/login", data={"secret": SECRET_TESTE}, follow_redirects=False
    )
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/"
    assert "hubsia_session" in resposta.cookies


def test_login_com_sessao_valida_redireciona_lista(client_autenticado):
    resposta = client_autenticado.get("/login", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/"


def test_logout_apaga_sessao(client_autenticado):
    resposta = client_autenticado.post("/logout", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/login"
    raiz = client_autenticado.get("/", follow_redirects=False)
    assert raiz.status_code == 302
    assert raiz.headers["location"] == "/login"


def test_get_logout_nao_permitido(client_autenticado):
    resposta = client_autenticado.get("/logout")
    assert resposta.status_code == 405
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```powershell
pytest tests/test_rotas_autenticacao_e_crud_comparacoes.py::test_raiz_sem_sessao_redireciona_login -v
```

Expected: FAIL (`ModuleNotFoundError` ou `criar_app` ausente).

- [ ] **Step 3: Implementação mínima**

`templates/pagina_base_hubsia.html`:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}Hubsia{% endblock %}</title>
  <link rel="stylesheet" href="/static/estilos_comparador_agregadores.css">
</head>
<body>
  <header class="topo">
    <a href="/">Comparações</a>
    <form method="post" action="/logout">
      <button type="submit">Sair</button>
    </form>
  </header>
  {% if flash %}
  <p class="aviso" role="status">{{ flash }}</p>
  {% endif %}
  <main>
    {% block conteudo %}{% endblock %}
  </main>
</body>
</html>
```

`templates/pagina_login_secret.html` (não estende a base autenticada):

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hubsia</title>
  <link rel="stylesheet" href="/static/estilos_comparador_agregadores.css">
</head>
<body class="login">
  <main>
    <h1>Hubsia</h1>
    {% if erro %}<p class="erro">{{ erro }}</p>{% endif %}
    <form method="post" action="/login">
      <label>Secret
        <input type="password" name="secret" required autocomplete="current-password">
      </label>
      <button type="submit">Entrar</button>
    </form>
  </main>
</body>
</html>
```

`templates/pagina_lista_comparacoes.html`:

```html
{% extends "pagina_base_hubsia.html" %}
{% block titulo %}Comparações — Hubsia{% endblock %}
{% block conteudo %}
<h1>Comparações</h1>
<p><a href="/comparacoes/nova">Nova comparação</a></p>
{% if not comparacoes %}
<p>Nenhuma comparação ainda.</p>
<p><a href="/comparacoes/nova">Criar a primeira</a></p>
{% else %}
<ul>
  {% for item in comparacoes %}
  <li>
    <a href="/comparacoes/{{ item.id }}">{{ item.nome }}</a>
    <span>{{ item.referencia }}</span>
    <form method="post" action="/comparacoes/{{ item.id }}/excluir" onsubmit="return confirm('Excluir esta comparação e todos os serviços?');">
      <button type="submit">Excluir</button>
    </form>
  </li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}
```

`static/estilos_comparador_agregadores.css` (mínimo):

```css
body { font-family: sans-serif; margin: 0; }
```

`aplicacao_fastapi_comparador_agregadores.py`:

```python
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from banco_sqlite_comparacoes_e_servicos import BancoComparacoes

BASE_DIR = Path(__file__).resolve().parent
COOKIE_SESSAO = "hubsia_session"
COOKIE_FLASH = "hubsia_flash"
SESSAO_MAX_AGE = 30 * 24 * 60 * 60
SALT_SESSAO = "hubsia-sessao"
SALT_FLASH = "hubsia-flash"


def _assinador(secret: str, salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=salt)


def sessao_valida(secret: str, token: str | None) -> bool:
    if not token:
        return False
    try:
        dados = _assinador(secret, SALT_SESSAO).loads(token, max_age=SESSAO_MAX_AGE)
    except (BadSignature, SignatureExpired, TypeError):
        return False
    return dados.get("auth") is True


def definir_cookie_sessao(response: Response, secret: str, https: bool) -> None:
    token = _assinador(secret, SALT_SESSAO).dumps({"auth": True})
    response.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=SESSAO_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=https,
        path="/",
    )


def apagar_cookie_sessao(response: Response, https: bool) -> None:
    response.delete_cookie(COOKIE_SESSAO, path="/", secure=https, httponly=True, samesite="lax")


def definir_cookie_flash(response: Response, secret: str, mensagem: str, https: bool) -> None:
    token = _assinador(secret, SALT_FLASH).dumps({"m": mensagem})
    response.set_cookie(
        COOKIE_FLASH,
        token,
        max_age=120,
        httponly=True,
        samesite="lax",
        secure=https,
        path="/",
    )


def ler_e_consumir_flash(request: Request, response: Response, secret: str, https: bool) -> str | None:
    token = request.cookies.get(COOKIE_FLASH)
    response.delete_cookie(COOKIE_FLASH, path="/", secure=https, httponly=True, samesite="lax")
    if not token:
        return None
    try:
        dados = _assinador(secret, SALT_FLASH).loads(token, max_age=120)
    except (BadSignature, SignatureExpired, TypeError):
        return None
    mensagem = dados.get("m")
    return mensagem if isinstance(mensagem, str) else None


def criar_app(*, secret: str, db_path: str, https: bool = False) -> FastAPI:
    banco = BancoComparacoes(db_path)
    banco.inicializar()
    app = FastAPI()
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    class ExigirSessao(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path.startswith("/static"):
                return await call_next(request)
            if request.url.path == "/login":
                return await call_next(request)
            if sessao_valida(secret, request.cookies.get(COOKIE_SESSAO)):
                return await call_next(request)
            return RedirectResponse(url="/login", status_code=302)

    app.add_middleware(ExigirSessao)

    @app.get("/login", response_class=HTMLResponse)
    async def get_login(request: Request):
        if sessao_valida(secret, request.cookies.get(COOKIE_SESSAO)):
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse(
            request, "pagina_login_secret.html", {"erro": None}
        )

    @app.post("/login", response_class=HTMLResponse)
    async def post_login(request: Request, secret_form: str = Form(..., alias="secret")):
        if hmac.compare_digest(secret_form, secret):
            resposta = RedirectResponse(url="/", status_code=302)
            definir_cookie_sessao(resposta, secret, https)
            return resposta
        return templates.TemplateResponse(
            request,
            "pagina_login_secret.html",
            {"erro": "Secret inválido."},
            status_code=200,
        )

    @app.post("/logout")
    async def post_logout():
        resposta = RedirectResponse(url="/login", status_code=302)
        apagar_cookie_sessao(resposta, https)
        return resposta

    @app.get("/", response_class=HTMLResponse)
    async def get_lista(request: Request):
        resposta_base = Response()
        flash = ler_e_consumir_flash(request, resposta_base, secret, https)
        html = templates.TemplateResponse(
            request,
            "pagina_lista_comparacoes.html",
            {"comparacoes": banco.listar_comparacoes(), "flash": flash},
        )
        if COOKIE_FLASH in request.cookies:
            html.delete_cookie(COOKIE_FLASH, path="/", secure=https, httponly=True, samesite="lax")
        return html

    return app


def criar_app_de_ambiente() -> FastAPI:
    valor_secret = os.environ.get("HUBSIA_SECRET")
    if not valor_secret:
        raise RuntimeError("Defina HUBSIA_SECRET")
    db_path = os.environ.get("HUBSIA_DB_PATH", str(BASE_DIR / "data" / "hubsia.db"))
    https = os.environ.get("HUBSIA_HTTPS", "").lower() == "true"
    return criar_app(secret=valor_secret, db_path=db_path, https=https)


def __getattr__(name: str):
    if name == "app":
        return criar_app_de_ambiente()
    raise AttributeError(name)
```

Nota: `Form(..., alias="secret")` — o parâmetro Python não pode se chamar só `secret` se já existe o `secret` da closure; use o alias `"secret"` no HTML `name="secret"`. Se o FastAPI da versão instalada reclamar do alias, use `secret_digitado: str = Form(..., alias="secret")` (já está assim como `secret_form`).

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests/test_rotas_autenticacao_e_crud_comparacoes.py tests/test_calculos_creditos_e_geracoes_por_dolar.py tests/test_banco_sqlite_comparacoes_e_servicos.py -v
```

Expected: PASS. Se `hmac.compare_digest` falhar por tamanhos diferentes de string, normalize (não use `==`); em 3.12 tamanhos diferentes retornam `False`.

- [ ] **Step 5: Commit**

```powershell
git add aplicacao_fastapi_comparador_agregadores.py templates/pagina_base_hubsia.html templates/pagina_login_secret.html templates/pagina_lista_comparacoes.html static/estilos_comparador_agregadores.css tests/conftest.py tests/test_rotas_autenticacao_e_crud_comparacoes.py
git commit -m "feat: protege o site com secret e sessao em cookie"
```

---

### Task 4: CRUD de comparações

**Files:**
- Create: `templates/pagina_formulario_nova_comparacao.html`
- Create: `templates/pagina_tabela_comparacao_servicos.html` (metadados + estado vazio; serviços na Task 5)
- Create: `templates/pagina_nao_encontrada.html`
- Modify: `aplicacao_fastapi_comparador_agregadores.py` (rotas de comparação)
- Modify: `tests/test_rotas_autenticacao_e_crud_comparacoes.py`

**Interfaces:**
- Consumes: `BancoComparacoes.criar_comparacao`, `listar_comparacoes`, `obter_comparacao`, `atualizar_comparacao`, `excluir_comparacao`
- Produces: rotas `GET /comparacoes/nova`, `POST /comparacoes`, `GET /comparacoes/{id}`, `POST /comparacoes/{id}`, `POST /comparacoes/{id}/excluir`
- Validação de texto: `nome` strip, 1–80 chars; `referencia` strip, 1–200 chars; falha → 422 no mesmo template
- `POST /comparacoes/{id}`: se `referencia` nova != antiga, `definir_cookie_flash` com exatamente `A referência mudou. Atualize o custo em créditos de cada serviço para a nova geração.`; mudar só `nome` não seta flash
- 404: template `pagina_nao_encontrada.html` com link para `/`

- [ ] **Step 1: Acrescentar testes de CRUD de comparação**

No final de `tests/test_rotas_autenticacao_e_crud_comparacoes.py`:

```python
def test_criar_comparacao_e_abrir_tabela_vazia(client_autenticado):
    criada = client_autenticado.post(
        "/comparacoes",
        data={"nome": "Wan 3 480p", "referencia": "Wan 3, 10s, 480p"},
        follow_redirects=False,
    )
    assert criada.status_code == 302
    local = criada.headers["location"]
    assert local.startswith("/comparacoes/")
    pagina = client_autenticado.get(local)
    assert pagina.status_code == 200
    assert "Wan 3 480p" in pagina.text
    assert "Comparando: Wan 3, 10s, 480p" in pagina.text
    assert "Nenhum serviço ainda." in pagina.text


def test_criar_comparacao_nome_vazio_nao_grava(client_autenticado):
    resposta = client_autenticado.post(
        "/comparacoes",
        data={"nome": "  ", "referencia": "Wan 3"},
        follow_redirects=False,
    )
    assert resposta.status_code == 422
    lista = client_autenticado.get("/")
    assert "Wan 3" not in lista.text or "Nenhuma comparação ainda." in lista.text


def test_comparacao_inexistente_404(client_autenticado):
    resposta = client_autenticado.get("/comparacoes/999")
    assert resposta.status_code == 404
    assert "Comparações" in resposta.text or "/" in resposta.text


def test_excluir_comparacao(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "Apagar", "referencia": "ref"},
        follow_redirects=True,
    )
    lista = client_autenticado.get("/")
    assert "Apagar" in lista.text
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    apagada = client_autenticado.post(
        f"/comparacoes/{comparacao_id}/excluir", follow_redirects=False
    )
    assert apagada.status_code == 302
    lista = client_autenticado.get("/")
    assert "Apagar" not in lista.text


def test_aviso_referencia_so_quando_referencia_muda(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "A", "referencia": "Wan 3, 10s, 480p"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    so_nome = client_autenticado.post(
        f"/comparacoes/{comparacao_id}",
        data={"nome": "A2", "referencia": "Wan 3, 10s, 480p"},
        follow_redirects=True,
    )
    assert "A referência mudou." not in so_nome.text
    mudou = client_autenticado.post(
        f"/comparacoes/{comparacao_id}",
        data={"nome": "A2", "referencia": "outro modelo"},
        follow_redirects=True,
    )
    assert (
        "A referência mudou. Atualize o custo em créditos de cada serviço para a nova geração."
        in mudou.text
    )
    de_novo = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "A referência mudou." not in de_novo.text


def _id_primeira_comparacao(client) -> int:
    lista = client.get("/")
    # após criar, o link é /comparacoes/{id}
    import re
    achado = re.search(r"/comparacoes/(\d+)", lista.text)
    assert achado is not None
    return int(achado.group(1))
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```powershell
pytest tests/test_rotas_autenticacao_e_crud_comparacoes.py::test_criar_comparacao_e_abrir_tabela_vazia -v
```

Expected: FAIL (404 ou método ausente em `POST /comparacoes`).

- [ ] **Step 3: Templates e rotas**

`templates/pagina_formulario_nova_comparacao.html`:

```html
{% extends "pagina_base_hubsia.html" %}
{% block titulo %}Nova comparação — Hubsia{% endblock %}
{% block conteudo %}
<h1>Nova comparação</h1>
{% if erro %}<p class="erro">{{ erro }}</p>{% endif %}
<form method="post" action="/comparacoes">
  <label>Nome
    <input type="text" name="nome" required maxlength="80" value="{{ nome or '' }}">
  </label>
  <label>Referência
    <input type="text" name="referencia" required maxlength="200" value="{{ referencia or '' }}" placeholder="Wan 3, 10s, 480p">
  </label>
  <button type="submit">Criar</button>
</form>
{% endblock %}
```

`templates/pagina_nao_encontrada.html`:

```html
{% extends "pagina_base_hubsia.html" %}
{% block titulo %}Não encontrado — Hubsia{% endblock %}
{% block conteudo %}
<h1>Não encontrado</h1>
<p>Essa comparação ou serviço não existe.</p>
<p><a href="/">Voltar às comparações</a></p>
{% endblock %}
```

`templates/pagina_tabela_comparacao_servicos.html`:

```html
{% extends "pagina_base_hubsia.html" %}
{% block titulo %}{{ comparacao.nome }} — Hubsia{% endblock %}
{% block conteudo %}
<h1>{{ comparacao.nome }}</h1>
<p>Comparando: {{ comparacao.referencia }}</p>
{% if erro_meta %}<p class="erro">{{ erro_meta }}</p>{% endif %}
<form method="post" action="/comparacoes/{{ comparacao.id }}">
  <label>Nome
    <input type="text" name="nome" required maxlength="80" value="{{ comparacao.nome }}">
  </label>
  <label>Referência
    <input type="text" name="referencia" required maxlength="200" value="{{ comparacao.referencia }}">
  </label>
  <button type="submit">Salvar referência</button>
</form>

<h2>{% if servico_edicao %}Editar serviço{% else %}Novo serviço{% endif %}</h2>
{% if erro_servico %}<p class="erro">{{ erro_servico }}</p>{% endif %}
<form method="post" action="{% if servico_edicao %}/servicos/{{ servico_edicao.id }}{% else %}/comparacoes/{{ comparacao.id }}/servicos{% endif %}">
  <label>Serviço
    <input type="text" name="nome" required maxlength="80" value="{{ servico_edicao.nome if servico_edicao else '' }}">
  </label>
  <label>Custo mensal (USD)
    <input type="number" name="custo_mensal_usd" step="any" required value="{{ servico_edicao.custo_mensal_usd if servico_edicao else '' }}">
  </label>
  <label>Total de créditos no mês
    <input type="number" name="creditos_mes" step="any" required value="{{ servico_edicao.creditos_mes if servico_edicao else '' }}">
  </label>
  <label>Custo usado como referência
    <input type="number" name="custo_referencia_creditos" step="any" required value="{{ servico_edicao.custo_referencia_creditos if servico_edicao else '' }}">
  </label>
  <button type="submit">{% if servico_edicao %}Salvar serviço{% else %}Adicionar{% endif %}</button>
  {% if servico_edicao %}
  <a href="/comparacoes/{{ comparacao.id }}">Cancelar</a>
  {% endif %}
</form>

<div class="tabela-scroll">
<table>
  <thead>
    <tr>
      <th>Serviço</th>
      <th>Custo mensal (USD)</th>
      <th>Total de créditos no mês</th>
      <th>Créditos por dólar</th>
      <th>Custo usado como referência</th>
      <th>Gerações por dólar</th>
      <th>Gerações mensais no plano</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    {% if not linhas %}
    <tr><td colspan="8">Nenhum serviço ainda.</td></tr>
    {% else %}
    {% for linha in linhas %}
    <tr>
      <td>{{ linha.servico.nome }}</td>
      <td>{{ linha.custo_mensal }}</td>
      <td>{{ linha.creditos_mes }}</td>
      <td>{{ linha.creditos_por_dolar }}</td>
      <td>{{ linha.custo_referencia }}</td>
      <td>{{ linha.geracoes_por_dolar }}</td>
      <td>{{ linha.geracoes_mensais }}</td>
      <td>
        <a href="/comparacoes/{{ comparacao.id }}?editar_servico={{ linha.servico.id }}">Editar</a>
        <form method="post" action="/servicos/{{ linha.servico.id }}/excluir" onsubmit="return confirm('Excluir este serviço?');">
          <button type="submit">Excluir</button>
        </form>
      </td>
    </tr>
    {% endfor %}
    {% endif %}
  </tbody>
</table>
</div>
{% endblock %}
```

Em `criar_app`, acrescente (depois das rotas da Task 3):

```python
    def _validar_texto(valor: str, minimo: int, maximo: int) -> str | None:
        texto = (valor or "").strip()
        if not (minimo <= len(texto) <= maximo):
            return None
        return texto

    def _pagina_404(request: Request):
        return templates.TemplateResponse(
            request, "pagina_nao_encontrada.html", {"flash": None}, status_code=404
        )

    def _consumir_flash(request: Request) -> tuple[str | None, dict[str, str]]:
        """Devolve (mensagem, headers extras com Set-Cookie de delete)."""
        token = request.cookies.get(COOKIE_FLASH)
        if not token:
            return None, {}
        dummy = RedirectResponse(url="/", status_code=302)
        dummy.delete_cookie(
            COOKIE_FLASH, path="/", secure=https, httponly=True, samesite="lax"
        )
        try:
            dados = _assinador(secret, SALT_FLASH).loads(token, max_age=120)
            mensagem = dados.get("m") if isinstance(dados.get("m"), str) else None
        except (BadSignature, SignatureExpired, TypeError):
            mensagem = None
        return mensagem, dict(dummy.headers)

    def _resposta_tabela(request: Request, comparacao, **extra):
        flash, headers_flash = _consumir_flash(request)
        status = extra.pop("status_code", 200)
        contexto = {
            "comparacao": comparacao,
            "linhas": extra.get("linhas", []),
            "erro_meta": extra.get("erro_meta"),
            "erro_servico": extra.get("erro_servico"),
            "servico_edicao": extra.get("servico_edicao"),
            "flash": flash,
        }
        return templates.TemplateResponse(
            request,
            "pagina_tabela_comparacao_servicos.html",
            contexto,
            status_code=status,
            headers=headers_flash,
        )

    @app.get("/comparacoes/nova", response_class=HTMLResponse)
    async def get_nova(request: Request):
        return templates.TemplateResponse(
            request,
            "pagina_formulario_nova_comparacao.html",
            {"erro": None, "nome": "", "referencia": "", "flash": None},
        )

    @app.post("/comparacoes", response_class=HTMLResponse)
    async def post_nova(request: Request, nome: str = Form(""), referencia: str = Form("")):
        nome_ok = _validar_texto(nome, 1, 80)
        ref_ok = _validar_texto(referencia, 1, 200)
        if nome_ok is None or ref_ok is None:
            return templates.TemplateResponse(
                request,
                "pagina_formulario_nova_comparacao.html",
                {
                    "erro": "Nome (1 a 80) e referência (1 a 200) são obrigatórios.",
                    "nome": nome,
                    "referencia": referencia,
                    "flash": None,
                },
                status_code=422,
            )
        criada = banco.criar_comparacao(nome_ok, ref_ok)
        return RedirectResponse(url=f"/comparacoes/{criada.id}", status_code=302)

    @app.get("/comparacoes/{comparacao_id}", response_class=HTMLResponse)
    async def get_tabela(request: Request, comparacao_id: int):
        comparacao = banco.obter_comparacao(comparacao_id)
        if comparacao is None:
            return _pagina_404(request)
        return _resposta_tabela(request, comparacao, linhas=[])

    @app.post("/comparacoes/{comparacao_id}", response_class=HTMLResponse)
    async def post_meta(
        request: Request,
        comparacao_id: int,
        nome: str = Form(""),
        referencia: str = Form(""),
    ):
        comparacao = banco.obter_comparacao(comparacao_id)
        if comparacao is None:
            return _pagina_404(request)
        nome_ok = _validar_texto(nome, 1, 80)
        ref_ok = _validar_texto(referencia, 1, 200)
        if nome_ok is None or ref_ok is None:
            return _resposta_tabela(
                request,
                comparacao,
                erro_meta="Nome (1 a 80) e referência (1 a 200) são obrigatórios.",
                status_code=422,
            )
        referencia_mudou = ref_ok != comparacao.referencia
        banco.atualizar_comparacao(comparacao_id, nome_ok, ref_ok)
        resposta = RedirectResponse(url=f"/comparacoes/{comparacao_id}", status_code=302)
        if referencia_mudou:
            definir_cookie_flash(
                resposta,
                secret,
                "A referência mudou. Atualize o custo em créditos de cada serviço para a nova geração.",
                https,
            )
        return resposta

    @app.post("/comparacoes/{comparacao_id}/excluir")
    async def post_excluir_comparacao(comparacao_id: int):
        banco.excluir_comparacao(comparacao_id)
        return RedirectResponse(url="/", status_code=302)
```

`_resposta_tabela` é o único jeito de renderizar a página da tabela. Na Task 5 você só passa `linhas=...` e `servico_edicao=...` para essa mesma função — não crie um segundo `get_tabela`.

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests/test_rotas_autenticacao_e_crud_comparacoes.py -v
```

Expected: PASS nos testes de auth + comparações. Testes de serviço ainda não existem.

- [ ] **Step 5: Commit**

```powershell
git add aplicacao_fastapi_comparador_agregadores.py templates/pagina_formulario_nova_comparacao.html templates/pagina_tabela_comparacao_servicos.html templates/pagina_nao_encontrada.html tests/test_rotas_autenticacao_e_crud_comparacoes.py
git commit -m "feat: cria, edita e exclui tabelas de comparacao"
```

---

### Task 5: CRUD de serviços e colunas calculadas

**Files:**
- Modify: `aplicacao_fastapi_comparador_agregadores.py`
- Modify: `tests/test_rotas_autenticacao_e_crud_comparacoes.py`

**Interfaces:**
- Consumes: `calcular_creditos_e_geracoes`, `parsear_decimal_entrada`, `formatar_numero_pt_br`, `EntradaInvalidaCalculo`; `BancoComparacoes.criar_servico`, `listar_servicos`, `obter_servico`, `atualizar_servico`, `excluir_servico`
- Produces: `POST /comparacoes/{id}/servicos`, `POST /servicos/{id}`, `POST /servicos/{id}/excluir`; `GET /comparacoes/{id}?editar_servico={id}` preenche o form; serviço de outra comparação → 404
- Cada item de `linhas` é um dict: `servico`, `custo_mensal`, `creditos_mes`, `custo_referencia`, `creditos_por_dolar`, `geracoes_por_dolar`, `geracoes_mensais` (strings já formatadas com `formatar_numero_pt_br`)
- `EntradaInvalidaCalculo` ou texto de nome inválido → 422, não grava

- [ ] **Step 1: Testes de serviço**

Acrescente:

```python
def test_servico_higgsfield_mostra_contas_na_tabela(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "Wan 3 480p", "referencia": "Wan 3, 10s, 480p"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    criada = client_autenticado.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "Higgsfield",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
        follow_redirects=False,
    )
    assert criada.status_code == 302
    pagina = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "Higgsfield" in pagina.text
    assert ">40<" in pagina.text or ">40</td>" in pagina.text
    assert ">120<" in pagina.text or ">120</td>" in pagina.text
    assert ">4<" in pagina.text or ">4</td>" in pagina.text


def test_servico_custo_zero_nao_grava(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "A", "referencia": "ref"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    resposta = client_autenticado.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "X",
            "custo_mensal_usd": "0",
            "creditos_mes": "100",
            "custo_referencia_creditos": "10",
        },
        follow_redirects=False,
    )
    assert resposta.status_code == 422
    pagina = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "X" not in pagina.text or "Nenhum serviço ainda." in pagina.text


def test_duas_tabelas_mesmo_servico_referencias_diferentes(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "480p", "referencia": "Wan 3 480p"},
        follow_redirects=True,
    )
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "720p", "referencia": "Wan 3 720p"},
        follow_redirects=True,
    )
    lista = client_autenticado.get("/")
    import re
    ids = [int(x) for x in re.findall(r"/comparacoes/(\d+)", lista.text)]
    assert len(set(ids)) >= 2
    id_720, id_480 = ids[0], ids[1]
    client_autenticado.post(
        f"/comparacoes/{id_480}/servicos",
        data={
            "nome": "Higgsfield",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
    )
    client_autenticado.post(
        f"/comparacoes/{id_720}/servicos",
        data={
            "nome": "Higgsfield",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "40",
        },
    )
    pagina_480 = client_autenticado.get(f"/comparacoes/{id_480}").text
    pagina_720 = client_autenticado.get(f"/comparacoes/{id_720}").text
    assert "120" in pagina_480
    assert "30" in pagina_720
    assert "Comparando: Wan 3 480p" in pagina_480
    assert "Comparando: Wan 3 720p" in pagina_720


def test_editar_e_excluir_servico(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "A", "referencia": "ref"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    client_autenticado.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "Higgsfield",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
        follow_redirects=True,
    )
    pagina = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    import re
    servico_id = int(re.search(r"editar_servico=(\d+)", pagina.text).group(1))
    edicao = client_autenticado.get(
        f"/comparacoes/{comparacao_id}?editar_servico={servico_id}"
    )
    assert 'value="Higgsfield"' in edicao.text
    client_autenticado.post(
        f"/servicos/{servico_id}",
        data={
            "nome": "Higgsfield Pro",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
        follow_redirects=True,
    )
    assert "Higgsfield Pro" in client_autenticado.get(f"/comparacoes/{comparacao_id}").text
    client_autenticado.post(f"/servicos/{servico_id}/excluir", follow_redirects=True)
    final = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "Higgsfield Pro" not in final.text
    assert "Nenhum serviço ainda." in final.text
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```powershell
pytest tests/test_rotas_autenticacao_e_crud_comparacoes.py::test_servico_higgsfield_mostra_contas_na_tabela -v
```

Expected: FAIL (404 em `POST .../servicos`).

- [ ] **Step 3: Implementar rotas e montagem de `linhas`**

No topo de `aplicacao_fastapi_comparador_agregadores.py`, importe:

```python
from calculos_creditos_e_geracoes_por_dolar import (
    EntradaInvalidaCalculo,
    calcular_creditos_e_geracoes,
    formatar_numero_pt_br,
    parsear_decimal_entrada,
)
```

Dentro de `criar_app`, substitua a montagem vazia de `linhas=[]` por:

```python
    def _linhas_da_comparacao(comparacao_id: int) -> list[dict]:
        linhas = []
        for servico in banco.listar_servicos(comparacao_id):
            contas = calcular_creditos_e_geracoes(
                servico.custo_mensal_usd,
                servico.creditos_mes,
                servico.custo_referencia_creditos,
            )
            linhas.append(
                {
                    "servico": servico,
                    "custo_mensal": formatar_numero_pt_br(servico.custo_mensal_usd),
                    "creditos_mes": formatar_numero_pt_br(servico.creditos_mes),
                    "custo_referencia": formatar_numero_pt_br(
                        servico.custo_referencia_creditos
                    ),
                    "creditos_por_dolar": formatar_numero_pt_br(
                        contas.creditos_por_dolar
                    ),
                    "geracoes_por_dolar": formatar_numero_pt_br(
                        contas.geracoes_por_dolar
                    ),
                    "geracoes_mensais": formatar_numero_pt_br(contas.geracoes_mensais),
                }
            )
        return linhas
```

Passe `_linhas_da_comparacao(comparacao.id)` em todo GET/422 da tabela (argumento `linhas=` de `_resposta_tabela`).

Substitua o `get_tabela` da Task 4 por um que aceita query `editar_servico`. Rotas novas:

```python
    def _ler_servico_form(form_nome, custo, creditos, referencia):
        nome_ok = _validar_texto(form_nome, 1, 80)
        if nome_ok is None:
            raise EntradaInvalidaCalculo("nome inválido")
        return (
            nome_ok,
            parsear_decimal_entrada(custo),
            parsear_decimal_entrada(creditos),
            parsear_decimal_entrada(referencia),
        )

    @app.post("/comparacoes/{comparacao_id}/servicos", response_class=HTMLResponse)
    async def post_servico(
        request: Request,
        comparacao_id: int,
        nome: str = Form(""),
        custo_mensal_usd: str = Form(""),
        creditos_mes: str = Form(""),
        custo_referencia_creditos: str = Form(""),
    ):
        comparacao = banco.obter_comparacao(comparacao_id)
        if comparacao is None:
            return _pagina_404(request)
        try:
            nome_ok, custo, creditos, ref_cred = _ler_servico_form(
                nome, custo_mensal_usd, creditos_mes, custo_referencia_creditos
            )
            calcular_creditos_e_geracoes(custo, creditos, ref_cred)
        except EntradaInvalidaCalculo:
            return _resposta_tabela(
                request,
                comparacao,
                linhas=_linhas_da_comparacao(comparacao.id),
                erro_servico="Informe serviço, custo mensal, créditos e referência maiores que zero.",
                status_code=422,
            )
        banco.criar_servico(comparacao_id, nome_ok, custo, creditos, ref_cred)
        return RedirectResponse(url=f"/comparacoes/{comparacao_id}", status_code=302)

    @app.get("/comparacoes/{comparacao_id}", response_class=HTMLResponse)
    async def get_tabela(request: Request, comparacao_id: int, editar_servico: int | None = None):
        comparacao = banco.obter_comparacao(comparacao_id)
        if comparacao is None:
            return _pagina_404(request)
        servico_edicao = None
        if editar_servico is not None:
            servico_edicao = banco.obter_servico(editar_servico)
            if servico_edicao is None or servico_edicao.comparacao_id != comparacao.id:
                return _pagina_404(request)
        return _resposta_tabela(
            request,
            comparacao,
            linhas=_linhas_da_comparacao(comparacao.id),
            servico_edicao=servico_edicao,
        )

    @app.post("/servicos/{servico_id}", response_class=HTMLResponse)
    async def post_atualizar_servico(
        request: Request,
        servico_id: int,
        nome: str = Form(""),
        custo_mensal_usd: str = Form(""),
        creditos_mes: str = Form(""),
        custo_referencia_creditos: str = Form(""),
    ):
        servico = banco.obter_servico(servico_id)
        if servico is None:
            return _pagina_404(request)
        comparacao = banco.obter_comparacao(servico.comparacao_id)
        try:
            nome_ok, custo, creditos, ref_cred = _ler_servico_form(
                nome, custo_mensal_usd, creditos_mes, custo_referencia_creditos
            )
            calcular_creditos_e_geracoes(custo, creditos, ref_cred)
        except EntradaInvalidaCalculo:
            return _resposta_tabela(
                request,
                comparacao,
                linhas=_linhas_da_comparacao(comparacao.id),
                erro_servico="Informe serviço, custo mensal, créditos e referência maiores que zero.",
                servico_edicao=servico,
                status_code=422,
            )
        banco.atualizar_servico(servico_id, nome_ok, custo, creditos, ref_cred)
        return RedirectResponse(
            url=f"/comparacoes/{servico.comparacao_id}", status_code=302
        )

    @app.post("/servicos/{servico_id}/excluir")
    async def post_excluir_servico(servico_id: int):
        servico = banco.obter_servico(servico_id)
        if servico is None:
            return RedirectResponse(url="/", status_code=302)
        comparacao_id = servico.comparacao_id
        banco.excluir_servico(servico_id)
        return RedirectResponse(url=f"/comparacoes/{comparacao_id}", status_code=302)
```

Fica um único `get_tabela`. 422 de serviço também passa por `_resposta_tabela`.

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests -v
```

Expected: PASS em todos os arquivos de teste. Se a asserção `>40<` falhar por whitespace no HTML, relaxe para `"40" in pagina.text` **e** `"Higgsfield" in pagina.text` juntos, mantendo 120 e 4.

- [ ] **Step 5: Commit**

```powershell
git add aplicacao_fastapi_comparador_agregadores.py tests/test_rotas_autenticacao_e_crud_comparacoes.py
git commit -m "feat: cadastra servicos e mostra geracoes por dolar"
```

---

### Task 6: CSS mobile e README de deploy

**Files:**
- Modify: `static/estilos_comparador_agregadores.css`
- Create: `README.md`
- Modify: `templates/pagina_login_secret.html` / `pagina_base_hubsia.html` só se faltar classe no form (`formulario-empilhado` nos forms)

**Interfaces:**
- Consumes: telas já existentes
- Produces: layout usável em ~390px; README com env, uvicorn, proxy, backup do `.db`

- [ ] **Step 1: Teste de regressão (nenhum teste visual novo)**

Não há teste de CSS. Critério: `pytest tests -v` continua verde depois do CSS/README. Checklist manual do implementador (não pular): abrir `/` em 390px de largura (DevTools) e confirmar form empilhado + `.tabela-scroll { overflow-x: auto; }`.

- [ ] **Step 2: Confirmar baseline verde**

```powershell
pytest tests -v
```

Expected: PASS.

- [ ] **Step 3: CSS e README**

Substitua `static/estilos_comparador_agregadores.css` por:

```css
* { box-sizing: border-box; }
body {
  font-family: system-ui, sans-serif;
  margin: 0;
  color: #111;
  line-height: 1.4;
}
.topo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #ddd;
}
main { padding: 1rem; max-width: 960px; margin: 0 auto; }
form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
}
input, button {
  font-size: 1rem;
  padding: 0.5rem;
}
.tabela-scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 720px; }
th, td { border: 1px solid #ddd; padding: 0.4rem 0.5rem; text-align: left; white-space: nowrap; }
.erro, .aviso { padding: 0.75rem; border-radius: 4px; }
.erro { background: #fde8e8; }
.aviso { background: #e7f3ff; }
.login main { max-width: 22rem; padding-top: 3rem; }
@media (max-width: 480px) {
  main { padding: 0.75rem; }
  .topo { padding: 0.5rem 0.75rem; }
}
```

Crie `README.md`:

```markdown
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
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
pytest tests -v
```

Expected: PASS. Conferir o critério de pronto da spec: duas comparações, mesmo agregador, custos de referência diferentes, contas distintas; sem secret não lê nem grava.

- [ ] **Step 5: Commit**

```powershell
git add static/estilos_comparador_agregadores.css README.md
git commit -m "docs: readme de deploy na vps e layout mobile"
```

---

## Self-review (spec coverage)

| Spec | Task |
|---|---|
| Fórmulas Higgsfield 30/1200/10 → 40, 4, 120; equivalência; ≤0; pt-BR; vírgula | 1 |
| SQLite schema, cascade, nomes repetidos | 2 |
| Secret, cookie 30d, login/logout, GET /login autenticado, 302 sem sessão, 405 GET logout | 3 |
| CRUD comparação, 422 texto, 404, flash só se referência muda, PRG | 4 |
| CRUD serviço, 7 colunas calculadas, `?editar_servico=`, duas tabelas | 5 |
| CSS ~390px, README env/uvicorn/proxy/backup | 6 |
| `criar_app` para testes (secret e db temporários); `__getattr__("app")` para uvicorn | 3 |
| Fora de escopo (Docker, CSRF, contas) | não implementado, de propósito |

Desvio consciente: spec lista `uvicorn ...:app`; o plano usa `__getattr__` para não exigir `HUBSIA_SECRET` na importação dos testes. O comando do README permanece o da spec.
