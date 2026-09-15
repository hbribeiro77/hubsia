import re
from decimal import Decimal

from banco_sqlite_comparacoes_e_servicos import Servico
from tests.conftest import SECRET_TESTE


def test_health_sem_sessao_retorna_ok(client):
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.text == "ok"


def test_css_estatico_e_servido_sem_login(client):
    resposta = client.get("/static/estilos_comparador_agregadores.css")
    assert resposta.status_code == 200
    assert "text/css" in resposta.headers["content-type"]
    assert "--marca" in resposta.text
    assert "nth-child(even)" in resposta.text
    assert "1760px" in resposta.text
    assert ".botao-icone" in resposta.text
    assert "#f3eee6" in resposta.text
    assert "#d7efe8" in resposta.text
    assert "th a.ordenar" in resposta.text


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
    assert 'href="/"' in resposta.text
    assert "Voltar às comparações" in resposta.text


def test_rota_desconhecida_sem_sessao_redireciona_login(client):
    resposta = client.get("/rota-inexistente", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/login"


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
    assert "Novo serviço" in pagina.text
    assert 'class="cartao secao-colapsavel"' in pagina.text
    assert 'secao-colapsavel" open' not in pagina.text
    assert 'secao-colapsavel open' not in pagina.text
    assert 'id="modal-referencia"' in pagina.text
    assert 'aria-label="Editar nome e referência"' in pagina.text
    assert 'title="Custo mensal do plano em dólar"' in pagina.text
    assert "US$/mês" in pagina.text


def test_criar_comparacao_nome_vazio_nao_grava(client_autenticado):
    resposta = client_autenticado.post(
        "/comparacoes",
        data={"nome": "  ", "referencia": "Wan 3"},
        follow_redirects=False,
    )
    assert resposta.status_code == 422
    lista = client_autenticado.get("/")
    assert "Nenhuma comparação ainda." in lista.text


def test_comparacao_inexistente_404(client_autenticado):
    resposta = client_autenticado.get("/comparacoes/999")
    assert resposta.status_code == 404
    assert "Comparações" in resposta.text or "/" in resposta.text


def test_id_de_comparacao_invalido_retorna_html(client_autenticado):
    resposta = client_autenticado.get("/comparacoes/abc")
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")
    assert "Não encontrado" in resposta.text or "Comparações" in resposta.text


def test_excluir_comparacao_inexistente_retorna_404_html(client_autenticado):
    resposta = client_autenticado.post(
        "/comparacoes/999/excluir", follow_redirects=False
    )
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")
    assert "Não encontrado" in resposta.text


def test_excluir_servico_inexistente_retorna_404_html(client_autenticado):
    resposta = client_autenticado.post(
        "/servicos/999/excluir", follow_redirects=False
    )
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("text/html")
    assert "Não encontrado" in resposta.text
    assert "application/json" not in resposta.headers.get("content-type", "")


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


def test_lista_vazia_nao_mostra_duplicar(client_autenticado):
    lista = client_autenticado.get("/")
    assert "Nenhuma comparação ainda." in lista.text
    assert "Duplicar" not in lista.text


def test_duplicar_comparacao_redireciona_para_copia_com_servicos(
    client_autenticado,
):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "Wan 3 480p", "referencia": "Wan 3, 10s, 480p"},
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
    )
    lista = client_autenticado.get("/")
    assert "Duplicar" in lista.text
    duplicar = lista.text.find("Duplicar")
    excluir = lista.text.find("Excluir")
    assert duplicar != -1 and excluir != -1
    assert duplicar < excluir
    resposta = client_autenticado.post(
        f"/comparacoes/{comparacao_id}/duplicar", follow_redirects=False
    )
    assert resposta.status_code == 302
    local = resposta.headers["location"]
    assert local.startswith("/comparacoes/")
    assert local != f"/comparacoes/{comparacao_id}"
    copia = client_autenticado.get(local)
    assert copia.status_code == 200
    assert "Wan 3 480p (cópia)" in copia.text
    assert "Comparando: Wan 3, 10s, 480p" in copia.text
    assert "Higgsfield" in copia.text
    original = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "Wan 3 480p (cópia)" not in original.text
    assert ">Higgsfield<" in original.text
    lista = client_autenticado.get("/")
    assert "Wan 3 480p (cópia)" in lista.text
    assert lista.text.count("Duplicar") >= 2


def test_duplicar_comparacao_inexistente_retorna_404(client_autenticado):
    resposta = client_autenticado.post(
        "/comparacoes/999/duplicar", follow_redirects=False
    )
    assert resposta.status_code == 404
    assert "Não encontrado" in resposta.text


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
    assert 'aria-label="Editar"' in pagina.text
    assert 'aria-label="Excluir"' in pagina.text


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
    assert "Nenhum serviço ainda." in pagina.text


def test_servico_com_custo_extremo_retorna_422_e_nao_grava(client_autenticado):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "A", "referencia": "ref"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)
    resposta = client_autenticado.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "Extremo",
            "custo_mensal_usd": "1e400",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
        follow_redirects=False,
    )
    assert resposta.status_code == 422
    pagina = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert "Nenhum serviço ainda." in pagina.text


def test_tabela_com_servico_infinito_ainda_retorna_200(
    client_autenticado, monkeypatch
):
    client_autenticado.post(
        "/comparacoes",
        data={"nome": "A", "referencia": "ref"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client_autenticado)

    def listar_servicos_com_infinito(_banco, id_recebido):
        assert id_recebido == comparacao_id
        return [
            Servico(
                id=1,
                comparacao_id=comparacao_id,
                nome="Linha corrompida",
                custo_mensal_usd=Decimal("Infinity"),
                creditos_mes=Decimal("1200"),
                custo_referencia_creditos=Decimal("10"),
            )
        ]

    monkeypatch.setattr(
        "banco_sqlite_comparacoes_e_servicos.BancoComparacoes.listar_servicos",
        listar_servicos_com_infinito,
    )
    resposta = client_autenticado.get(f"/comparacoes/{comparacao_id}")
    assert resposta.status_code == 200
    assert "Linha corrompida" in resposta.text
    assert "Erro de cálculo" in resposta.text


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
    ids = list(
        dict.fromkeys(int(x) for x in re.findall(r"/comparacoes/(\d+)", lista.text))
    )
    assert len(ids) >= 2
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
    celulas_480 = re.findall(r"<td[^>]*>\s*([^<]*?)\s*</td>", pagina_480)
    celulas_720 = re.findall(r"<td[^>]*>\s*([^<]*?)\s*</td>", pagina_720)
    assert celulas_480[6] == "120"
    assert celulas_720[6] == "30"
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
    assert "Editar serviço" in edicao.text
    assert 'secao-colapsavel" open' in edicao.text
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


def _criar_comparacao_com_dois_servicos(client) -> int:
    client.post(
        "/comparacoes",
        data={"nome": "Ordem", "referencia": "Wan 3"},
        follow_redirects=True,
    )
    comparacao_id = _id_primeira_comparacao(client)
    client.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "Caro",
            "custo_mensal_usd": "30",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
    )
    client.post(
        f"/comparacoes/{comparacao_id}/servicos",
        data={
            "nome": "Barato",
            "custo_mensal_usd": "10",
            "creditos_mes": "1200",
            "custo_referencia_creditos": "10",
        },
    )
    return comparacao_id


def test_tabela_ordena_por_padrao_geracoes_por_dolar_desc(client_autenticado):
    comparacao_id = _criar_comparacao_com_dois_servicos(client_autenticado)
    pagina = client_autenticado.get(f"/comparacoes/{comparacao_id}").text
    assert pagina.find(">Barato<") < pagina.find(">Caro<")
    assert 'aria-sort="descending"' in pagina
    assert "ordenar=geracoes_por_dolar" in pagina


def test_tabela_ordena_por_servico_quando_query_pede(client_autenticado):
    comparacao_id = _criar_comparacao_com_dois_servicos(client_autenticado)
    pagina = client_autenticado.get(
        f"/comparacoes/{comparacao_id}?ordenar=servico&dir=asc"
    ).text
    assert pagina.find(">Barato<") < pagina.find(">Caro<")
    pagina_desc = client_autenticado.get(
        f"/comparacoes/{comparacao_id}?ordenar=servico&dir=desc"
    ).text
    assert pagina_desc.find(">Caro<") < pagina_desc.find(">Barato<")


def test_tabela_query_de_ordenacao_invalida_cai_no_padrao(client_autenticado):
    comparacao_id = _criar_comparacao_com_dois_servicos(client_autenticado)
    pagina = client_autenticado.get(
        f"/comparacoes/{comparacao_id}?ordenar=nao_existe&dir=xyz"
    ).text
    assert pagina.find(">Barato<") < pagina.find(">Caro<")
    assert 'aria-sort="descending"' in pagina
