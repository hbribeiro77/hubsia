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
