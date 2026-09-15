from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from banco_sqlite_comparacoes_e_servicos import BancoComparacoes
from calculos_creditos_e_geracoes_por_dolar import (
    EntradaInvalidaCalculo,
    calcular_creditos_e_geracoes,
    formatar_numero_pt_br,
    parsear_decimal_entrada,
)

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
        return templates.TemplateResponse(
            request,
            "pagina_nao_encontrada.html",
            {"flash": None},
            status_code=404,
        )

    @app.exception_handler(405)
    async def erro_metodo_nao_permitido(request: Request, exc: Exception):
        return HTMLResponse(
            "<!DOCTYPE html><html lang='pt-BR'><body>"
            "<h1>Método não permitido.</h1></body></html>",
            status_code=405,
        )

    @app.exception_handler(RequestValidationError)
    async def erro_validacao_requisicao(
        request: Request, exc: RequestValidationError
    ):
        if any(
            err.get("loc") and err["loc"][0] == "path" for err in exc.errors()
        ):
            return templates.TemplateResponse(
                request,
                "pagina_nao_encontrada.html",
                {"flash": None},
                status_code=404,
            )
        return HTMLResponse(
            "<!DOCTYPE html><html lang='pt-BR'><body>"
            "<h1>Dados inválidos.</h1></body></html>",
            status_code=422,
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

    def _consumir_flash(request: Request) -> str | None:
        token = request.cookies.get(COOKIE_FLASH)
        if not token:
            return None
        try:
            dados = _assinador(secret, SALT_FLASH).loads(token, max_age=120)
            mensagem = dados.get("m") if isinstance(dados.get("m"), str) else None
        except (BadSignature, SignatureExpired, TypeError):
            mensagem = None
        return mensagem

    def _resposta_tabela(request: Request, comparacao, **extra):
        flash = _consumir_flash(request)
        status = extra.pop("status_code", 200)
        contexto = {
            "comparacao": comparacao,
            "linhas": extra.get("linhas", []),
            "erro_meta": extra.get("erro_meta"),
            "erro_servico": extra.get("erro_servico"),
            "servico_edicao": extra.get("servico_edicao"),
            "flash": flash,
        }
        resposta = templates.TemplateResponse(
            request,
            "pagina_tabela_comparacao_servicos.html",
            contexto,
            status_code=status,
        )
        if COOKIE_FLASH in request.cookies:
            resposta.delete_cookie(
                COOKIE_FLASH,
                path="/",
                secure=https,
                httponly=True,
                samesite="lax",
            )
        return resposta

    def _linhas_da_comparacao(comparacao_id: int) -> list[dict]:
        linhas = []
        for servico in banco.listar_servicos(comparacao_id):
            def formatar_valor_armazenado(valor):
                try:
                    return formatar_numero_pt_br(valor)
                except (ArithmeticError, ValueError):
                    return "Valor inválido"

            linha = {
                "servico": servico,
                "custo_mensal": formatar_valor_armazenado(
                    servico.custo_mensal_usd
                ),
                "creditos_mes": formatar_valor_armazenado(servico.creditos_mes),
                "custo_referencia": formatar_valor_armazenado(
                    servico.custo_referencia_creditos
                ),
            }
            try:
                contas = calcular_creditos_e_geracoes(
                    servico.custo_mensal_usd,
                    servico.creditos_mes,
                    servico.custo_referencia_creditos,
                )
                linha.update(
                    {
                    "creditos_por_dolar": formatar_numero_pt_br(
                        contas.creditos_por_dolar
                    ),
                    "geracoes_por_dolar": formatar_numero_pt_br(
                        contas.geracoes_por_dolar
                    ),
                    "geracoes_mensais": formatar_numero_pt_br(contas.geracoes_mensais),
                    }
                )
            except (EntradaInvalidaCalculo, ArithmeticError, ValueError):
                linha.update(
                    {
                        "creditos_por_dolar": "Erro de cálculo",
                        "geracoes_por_dolar": "Erro de cálculo",
                        "geracoes_mensais": "Erro de cálculo",
                    }
                )
            linhas.append(linha)
        return linhas

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
    async def get_tabela(
        request: Request,
        comparacao_id: int,
        editar_servico: int | None = None,
    ):
        comparacao = banco.obter_comparacao(comparacao_id)
        if comparacao is None:
            return _pagina_404(request)
        servico_edicao = None
        if editar_servico is not None:
            servico_edicao = banco.obter_servico(editar_servico)
            if (
                servico_edicao is None
                or servico_edicao.comparacao_id != comparacao.id
            ):
                return _pagina_404(request)
        return _resposta_tabela(
            request,
            comparacao,
            linhas=_linhas_da_comparacao(comparacao.id),
            servico_edicao=servico_edicao,
        )

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
                linhas=_linhas_da_comparacao(comparacao.id),
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
    async def post_excluir_servico(request: Request, servico_id: int):
        servico = banco.obter_servico(servico_id)
        if servico is None:
            return _pagina_404(request)
        comparacao_id = servico.comparacao_id
        banco.excluir_servico(servico_id)
        return RedirectResponse(url=f"/comparacoes/{comparacao_id}", status_code=302)

    @app.post("/comparacoes/{comparacao_id}/excluir")
    async def post_excluir_comparacao(request: Request, comparacao_id: int):
        if not banco.excluir_comparacao(comparacao_id):
            return _pagina_404(request)
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
