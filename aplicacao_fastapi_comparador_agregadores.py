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
    app = FastAPI()
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
