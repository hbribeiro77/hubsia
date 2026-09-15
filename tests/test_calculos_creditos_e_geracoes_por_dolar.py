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
