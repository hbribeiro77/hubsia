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
