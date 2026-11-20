"""Consumo do `batimento` v2 da vigia da S2 (contrato 08 §7.4; D-15 fail-closed; B1.6b).

O arquivo `{"v":2,"gerado_em":…,"seq":…,"impedidos":{chave: devolvendo|devolvido|fechado},"vivos":{chave: estado}}` (estado em
`reservado|agendado|aberto|pausado`) é lido a cada 15 s por uma `FonteBatimento` (porta: o endereço NÃO mora aqui; a hospedagem
da IA está em revisão). Regras:

- **Ausente, `v ≠ 2`, forma inválida, `seq` menor que o último aceito ou `gerado_em` com mais de 90 s** ⇒ `indisponivel`: a IA não age
  (`Canal.enviar`, `Canal.nota`, `iniciar`, o repasse e o reaper do boot recusam o efeito real) e há alerta crítico. 59, 75 e 89 s não
  alertam nem bloqueiam; 91 s bloqueia e alerta (R2-04: o timer da vigia grava a cada 60 s).
- **(i) `impedidos` barra sempre** ⇒ `impedido`: quem chama encerra `repassado/devolvido_pela_s2` sem efeito.
- **(ii) `vivos` exigido** na retomada, no reaper do boot e na 1ª ação depois de indisponibilidade (`recem_voltou`): chave ausente
  de `vivos` ou com outro estado ⇒ `fora_de_vivos` (não age; alerta amarelo). **(iii)** o `iniciar` e o repasse usam só a regra (i).
- Só consulta quem vai executar efeito REAL (`modo_efetivo ∈ {real, teste}` ou a devolução com posse real): quem chama decide.

Nada aqui fala com a rede: a leitura vem pela porta, o relógio é injetado e o alerta sai por `Alertas`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final, Literal, Protocol

from ia_atendimento.alertas import Alertas
from ia_atendimento.relogio import Relogio

VERSAO: Final = 2
IDADE_MAX: Final = timedelta(seconds=90)
INTERVALO_LEITURA_S: Final = 15
ESTADOS_IMPEDIDOS: Final = frozenset({"devolvendo", "devolvido", "fechado"})
ESTADOS_VIVOS: Final = frozenset({"reservado", "agendado", "aberto", "pausado"})

Situacao = Literal["livre", "impedido", "indisponivel", "fora_de_vivos"]


class BatimentoInvalido(ValueError):
    """O corpo lido não tem a forma v2 (nunca ecoa o conteúdo)."""


class FonteBatimento(Protocol):
    """Porta da leitura: devolve o JSON já decodificado, ou None se ausente (HTTP fora, 404, timeout)."""

    async def buscar(self) -> object | None: ...


@dataclass(frozen=True)
class Batimento:
    gerado_em: datetime
    seq: int
    impedidos: Mapping[str, str] = field(default_factory=dict)
    vivos: Mapping[str, str] = field(default_factory=dict)


def _mapa(corpo: Mapping[str, Any], nome: str, permitidos: frozenset[str]) -> dict[str, str]:
    valor = corpo.get(nome, {})
    if not isinstance(valor, Mapping) or any(not isinstance(k, str) or v not in permitidos for k, v in valor.items()):
        raise BatimentoInvalido(f"campo {nome} fora da forma")
    return dict(valor)


def ler_batimento(corpo: object) -> Batimento:
    """Valida a forma v2. `v ≠ 2` ou qualquer campo fora da forma ⇒ `BatimentoInvalido`."""
    if not isinstance(corpo, Mapping) or corpo.get("v") != VERSAO:
        raise BatimentoInvalido("versão do batimento diferente de 2")
    seq, gerado = corpo.get("seq"), corpo.get("gerado_em")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0 or not isinstance(gerado, str):
        raise BatimentoInvalido("seq ou gerado_em fora da forma")
    try:
        gerado_em = datetime.fromisoformat(gerado)
    except ValueError:
        raise BatimentoInvalido("gerado_em fora da forma") from None
    if gerado_em.tzinfo is None:
        raise BatimentoInvalido("gerado_em sem fuso")
    return Batimento(gerado_em, seq, _mapa(corpo, "impedidos", ESTADOS_IMPEDIDOS), _mapa(corpo, "vivos", ESTADOS_VIVOS))


class LeitorBatimento:
    """Guarda o último batimento aceito. `atualizar()` é chamado pelo laço de 15 s; `situacao()` por quem vai agir.

    `seq` que regride é recusado (o anterior continua, e envelhece até ficar indisponível); forma inválida derruba o aceito (fail-closed).
    `exigir_vivos` liga sozinho depois de qualquer indisponibilidade, até a 1ª ação liberada (regra ii)."""

    def __init__(self, fonte: FonteBatimento, relogio: Relogio, alertas: Alertas) -> None:
        self._fonte = fonte
        self._relogio = relogio
        self._alertas = alertas
        self._ultimo: Batimento | None = None
        self._esteve_indisponivel = True  # processo recém-iniciado = 1ª ação depois de indisponibilidade (reaper do boot)

    async def atualizar(self) -> None:
        try:
            corpo = await self._fonte.buscar()
        except Exception:  # a porta não pode derrubar o laço: falha de leitura = ausente
            corpo = None
        if corpo is None:
            return
        try:
            novo = ler_batimento(corpo)
        except BatimentoInvalido:
            self._ultimo = None
            self._alertas.alertar("critico", "batimento_invalido")
            return
        if self._ultimo is not None and novo.seq < self._ultimo.seq:
            self._alertas.alertar("critico", "batimento_seq_regrediu")
            return
        self._ultimo = novo

    def aceitar(self, corpo: object) -> None:
        """Atalho síncrono (testes e o reaper do boot): o mesmo que `atualizar` com o corpo já lido."""
        try:
            novo = ler_batimento(corpo)
        except BatimentoInvalido:
            self._ultimo = None
            return
        if self._ultimo is None or novo.seq >= self._ultimo.seq:
            self._ultimo = novo

    def disponivel(self, agora: datetime | None = None) -> Batimento | None:
        agora = agora or self._relogio.agora()
        if self._ultimo is None or agora - self._ultimo.gerado_em > IDADE_MAX:
            return None
        return self._ultimo

    @property
    def recem_voltou(self) -> bool:
        """Processo recém-iniciado ou batimento que esteve indisponível: a 1ª ação de conversa exige a chave em `vivos` (regra ii)."""
        return self._esteve_indisponivel

    def situacao(self, chave: str, *, esperado_em_vivos: str | None = None, atendimento_id: object = None) -> Situacao:
        """O que o batimento diz para a chave AGORA. Sem `esperado_em_vivos` vale só a regra (i) (o `iniciar`, regra iii, e o repasse,
        que não está em `vivos`); com ele, a regra (ii). Liberado com a regra (ii) fecha o «recém-voltou»."""
        batimento = self.disponivel()
        if batimento is None:
            self._esteve_indisponivel = True
            self._alertas.alertar("critico", "batimento_indisponivel", atendimento_id=atendimento_id)
            return "indisponivel"
        if chave in batimento.impedidos:
            return "impedido"
        if esperado_em_vivos is not None:
            if batimento.vivos.get(chave) != esperado_em_vivos:
                self._alertas.alertar("amarelo", "fora_de_vivos", atendimento_id=atendimento_id)
                return "fora_de_vivos"
            self._esteve_indisponivel = False
        return "livre"
