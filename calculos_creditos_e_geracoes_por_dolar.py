from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite


class EntradaInvalidaCalculo(ValueError):
    pass


@dataclass(frozen=True)
class ResultadoCalculoAgregador:
    creditos_por_dolar: Decimal
    geracoes_mensais: Decimal
    geracoes_por_dolar: Decimal


def _validar_decimal_calculavel(valor: Decimal) -> None:
    if not valor.is_finite() or valor <= 0:
        raise EntradaInvalidaCalculo("número inválido")
    try:
        if not isfinite(float(valor)):
            raise EntradaInvalidaCalculo("número inválido")
        valor.quantize(Decimal("0.01"))
    except (InvalidOperation, OverflowError) as exc:
        raise EntradaInvalidaCalculo("número inválido") from exc


def parsear_decimal_entrada(texto: str) -> Decimal:
    bruto = (texto or "").strip().replace(",", ".")
    try:
        valor = Decimal(bruto)
    except InvalidOperation as exc:
        raise EntradaInvalidaCalculo("número inválido") from exc
    _validar_decimal_calculavel(valor)
    return valor


def calcular_creditos_e_geracoes(
    custo_mensal_usd: Decimal,
    creditos_mes: Decimal,
    custo_referencia_creditos: Decimal,
) -> ResultadoCalculoAgregador:
    for valor in (custo_mensal_usd, creditos_mes, custo_referencia_creditos):
        _validar_decimal_calculavel(valor)
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
