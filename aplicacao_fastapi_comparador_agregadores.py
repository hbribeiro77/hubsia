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
        dados = _assinador(secret, SALT_SESSAO).loads(
            token, max_age=SESSAO_MAX_AGE
        )
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
    response.delete_cookie(
        COOKIE_SESSAO,
        path="/",
        secure=https,
        httponly=True,
        samesite="lax",
    )


def definir_cookie_flash(
    response: Response, secret: str, mensagem: str, https: bool
) -> None:
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


def ler_e_consumir_flash(
    request: Request, response: Response, secret: str, https: bool
) -> str | None:
    token = request.cookies.get(COOKIE_FLASH)
    response.delete_cookie(
        COOKIE_FLASH,
        path="/",
        secure=https,
        httponly=True,
        samesite="lax",
    )
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
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.exception_handler(404)
    async def erro_nao_encontrado(request: Request, exc: Exception):
        return HTMLResponse(
            "<!DOCTYPE html><html lang='pt-BR'><body>"
            "<h1>Página não encontrada.</h1></body></html>",
            status_code=404,
        )

    @app.exception_handler(405)
    async def erro_metodo_nao_permitido(request: Request, exc: Exception):
        return HTMLResponse(
            "<!DOCTYPE html><html lang='pt-BR'><body>"
            "<h1>Método não permitido.</h1></body></html>",
            status_code=405,
        )

    class ExigirSessao(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path == "/static" or request.url.path.startswith("/static/"):
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
    async def post_login(
        request: Request, secret_form: str = Form("", alias="secret")
    ):
        if hmac.compare_digest(secret_form.encode("utf-8"), secret.encode("utf-8")):
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
            html.delete_cookie(
                COOKIE_FLASH,
                path="/",
                secure=https,
                httponly=True,
                samesite="lax",
            )
        return html

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
    async def post_nova(
        request: Request, nome: str = Form(""), referencia: str = Form("")
    ):
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

    return app


def criar_app_de_ambiente() -> FastAPI:
    valor_secret = os.environ.get("HUBSIA_SECRET")
    if not valor_secret:
        raise RuntimeError("Defina HUBSIA_SECRET")
    db_path = os.environ.get(
        "HUBSIA_DB_PATH", str(BASE_DIR / "data" / "hubsia.db")
    )
    https = os.environ.get("HUBSIA_HTTPS", "").lower() == "true"
    return criar_app(secret=valor_secret, db_path=db_path, https=https)


def __getattr__(name: str):
    if name == "app":
        return criar_app_de_ambiente()
    raise AttributeError(name)
