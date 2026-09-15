from tests.conftest import SECRET_TESTE


def test_raiz_sem_sessao_redireciona_login(client):
    resposta = client.get("/", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/login"


def test_login_secret_invalido_permanece_na_tela(client):
    resposta = client.post("/login", data={"secret": "errado"}, follow_redirects=False)
    assert resposta.status_code == 200
    assert "Secret inválido." in resposta.text


def test_login_sem_secret_permanece_na_tela_html(client):
    resposta = client.post("/login", data={}, follow_redirects=False)
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    assert "Secret inválido." in resposta.text


def test_login_secret_nao_ascii_nao_500(client):
    resposta = client.post("/login", data={"secret": "inválido"})
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
    assert resposta.headers["content-type"].startswith("text/html")


def test_rota_desconhecida_autenticada_retorna_404_html(client_autenticado):
    resposta = client_autenticado.get("/rota-inexistente")
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")


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


def test_excluir_comparacao_inexistente_retorna_404_html(client_autenticado):
    resposta = client_autenticado.post(
        "/comparacoes/999/excluir", follow_redirects=False
    )
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")
    assert "Não encontrado" in resposta.text


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
