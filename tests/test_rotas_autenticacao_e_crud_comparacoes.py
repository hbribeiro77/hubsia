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
