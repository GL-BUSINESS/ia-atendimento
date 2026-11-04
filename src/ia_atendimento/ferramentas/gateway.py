"""O gateway de ferramentas (B5.1; estudo F §Gateway 2–12): toda chamada, do modelo ou do código, passa por `Gateway.chamar`.

Ordem fixa de uma chamada (falha em qualquer passo devolve `Resultado` com `ErroDeFerramenta` e o executor não roda):

1. **Validação** (§2): a ferramenta existe; o modelo só chama as `do_modelo`; os argumentos cumprem o esquema `extra=forbid`. O modelo
   passa só apelidos (`oferta-1`): o gateway os troca pelo id real e confere no estado do atendimento (`referencias`); apelido que o
   contexto não deu, ou id de outro atendimento, é `PARAMETRO_INVALIDO`. Sem quem confira, só o apelido do próprio contexto vale.
2. **Orçamento** (§6): por turno ≤ 4 síncronas (a vaga é reservada aqui, atômica: o modelo chama em paralelo) e ≤ 5 s; por atendimento
   ≤ 2 pagas (contadas no disparo, a tentativa) e ≤ 3 corrigíveis (a saída `corrigivel` e o `CORRIGIVEL` tipado do executor).
3. **Pré-condições por código** (§3): cada nome declarado precisa de um verificador que devolva `True`; sem verificador, com exceção ou
   com qualquer outra resposta, `PRECONDICAO_FALHOU{nome}` (fail-closed). Banco fora da flag é `banco_habilitado`.
4. **Vaga do limitador** por serviço (FACTA 2, 3RN 2, C6 1; §10): o serviço não depende do modo, então a espera vem ANTES do destino.
   Síncrona: um prazo só (o menor entre o da ferramenta e o que resta do turno) cobre a fila e o efeito. Assíncrona: a fila tem o seu
   prazo e o do efeito recomeça ao pegar a vaga.
5. **Destino na hora do efeito** (§11, §12; R2-02): `modo_efetivo` relido AGORA (cache ≤ 5 s), depois da fila, e o destino resolvido
   por `Destinos`. Interceptado ⇒ só o simulador roda (sem simulador, `MODO_SOMENTE_LEITURA`).
6. **CPF em memória** (D18): só para a ferramenta que o usa e só com destino de produção ou dublê; lido a cada chamada, entregue ao
   executor e esquecido. A leitura é um ponto de espera: o destino é relido depois dela, e entre ele e o executor não há `await`.
   **Execução**: timeout de leitura (ou na fila) é `BANCO_INDISPONIVEL`; falha de efeito irreversível JÁ DISPARADO é `INDETERMINADO`
   (regra 12: nunca reenvia); outra exceção é `DESCONHECIDO`. A mensagem da exceção nunca sai daqui, e o erro tipado do executor é
   refeito sem a causa.
7. **Saída** (§7): reconstruída pelo esquema; ao modelo, `retorno_ao_modelo()` → projeção da allowlist (`proteger_retorno`).
8. **Registro** (§8): `RegistroDaChamada` (forma do ledger, sem PII), span `ia.ferramenta` e uma linha de log, só com códigos.

O que fica para depois: o ledger de verdade (`ferramenta_chamada`, idempotência, `reservada` antes da chamada) e o batimento antes de cada
efeito real são da B1.6; os executores (360, fixtures, FACTA, dublê) são da B5.2–B5.4.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ValidationError
from pydantic_ai import RunContext
from pydantic_ai.tools import Tool

from ia_atendimento import observabilidade
from ia_atendimento.contexto import Apelidos
from ia_atendimento.ferramentas.catalogo import Catalogo
from ia_atendimento.ferramentas.erros import CodigoDeErro, ErroDeFerramenta
from ia_atendimento.ferramentas.especificacao import Especificacao
from ia_atendimento.ferramentas.modo import SERVICO_DO_BANCO, Destino, Destinos, LeitorDeModo
from ia_atendimento.ferramentas.orcamento import ContadorDoAtendimento, OrcamentoDoTurno
from ia_atendimento.ferramentas.projecao import Deps
from ia_atendimento.ferramentas.saida import para_projetar, reconstruir
from ia_atendimento.ferramentas.segredo import CpfEmMemoria

registro = logging.getLogger(__name__)

CAMPOS_DE_REFERENCIA: Final = ("oferta_ref", "opcao_ref", "confirmacao_id", "tentativa_ref")
CONCORRENCIA_POR_SERVICO: Final[Mapping[str, int]] = {"facta": 2, "trn": 2, "c6": 1}
_DESTINOS_COM_CPF: Final = frozenset({"producao", "duble"})


@dataclass(frozen=True)
class Referencia:
    """O que o estado do atendimento diz de um id: que é dele e de qual banco é (a oferta FACTA leva a T5 à FACTA)."""

    id: str = field(repr=False)
    banco: str | None = None


@dataclass(frozen=True)
class ContextoDaChamada:
    atendimento_id: UUID
    pessoa_id: UUID
    atendimento_modo: str
    posse_real: bool = False  # predicado do ledger (08 §6), calculado pela B1.6
    apelidos: Apelidos = field(default_factory=Apelidos, repr=False, compare=False)


@dataclass(frozen=True)
class Pedido:
    """O que as pré-condições veem: a chamada já validada, sem destino e sem CPF."""

    especificacao: Especificacao = field(repr=False)
    args: BaseModel = field(repr=False)
    referencias: Mapping[str, Referencia] = field(repr=False)
    contexto: ContextoDaChamada
    banco: str | None


@dataclass(frozen=True)
class Chamada:
    """O que o executor recebe. `destino.url` é a ÚNICA URL que ele deve usar; `cpf` só existe durante a chamada."""

    pedido: Pedido
    destino: Destino
    cpf: CpfEmMemoria | None = field(default=None, repr=False)

    @property
    def args(self) -> BaseModel:
        return self.pedido.args

    @property
    def referencias(self) -> Mapping[str, Referencia]:
        return self.pedido.referencias

    @property
    def banco(self) -> str | None:
        return self.pedido.banco

    @property
    def contexto(self) -> ContextoDaChamada:
        return self.pedido.contexto


@dataclass(frozen=True)
class RegistroDaChamada:
    """Uma linha para o ledger/passo (F §Gateway 8): só códigos, números e o hash dos argumentos. Nunca CPF, valor nem id em claro."""

    atendimento_id: UUID
    ferramenta: str  # `t3` (CHECK da 0001)
    versao: str
    classe: str
    resultado: str  # `ok` ou o código do erro em minúsculas
    modo_efetivo: str | None
    destino: str | None
    simulado: bool
    latencia_ms: int
    args_hash: str | None
    banco: str | None


@dataclass(frozen=True)
class Resultado:
    ferramenta: str
    dados: BaseModel | None = field(default=None, repr=False)
    erro: ErroDeFerramenta | None = None
    destino: Destino | None = None

    @property
    def ok(self) -> bool:
        return self.erro is None

    def retorno_ao_modelo(self) -> dict[str, Any]:
        """O corpo que a projeção recebe: o envelope `{erro, precondicao}` ou a saída varrida (URL → `{{link}}`, sem PII)."""
        if self.erro is not None:
            return self.erro.para_o_modelo()
        return para_projetar(self.dados) if self.dados is not None else {}


Executor = Callable[[Chamada], Awaitable[Any]]
Precondicao = Callable[[Pedido], "bool | Awaitable[bool]"]
ResolvedorDeReferencias = Callable[[UUID, str, str], Referencia | None]
LeitorDeCpf = Callable[[UUID], Awaitable[CpfEmMemoria | None]]


@dataclass
class _Andamento:
    destino: Destino | None = None
    args_hash: str | None = None
    banco: str | None = None
    latencia_ms: int = 0


def _hash_dos_args(pedido: Pedido) -> str:
    corpo = pedido.args.model_dump(mode="json") | {campo: ref.id for campo, ref in pedido.referencias.items()}
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _esquema_para_o_modelo(entrada: type[BaseModel]) -> dict[str, Any]:
    esquema = entrada.model_json_schema()
    esquema.pop("title", None)
    esquema.pop("description", None)
    for propriedade in esquema.get("properties", {}).values():
        propriedade.pop("title", None)
    return esquema


class Gateway:
    def __init__(
        self,
        catalogo: Catalogo,
        destinos: Destinos,
        leitor_de_modo: LeitorDeModo,
        executores: Mapping[str, Executor],
        *,
        simuladores: Mapping[str, Executor] | None = None,
        precondicoes: Mapping[str, Precondicao] | None = None,
        referencias: ResolvedorDeReferencias | None = None,
        leitor_de_cpf: LeitorDeCpf | None = None,
        bancos_ligados: Callable[[str], Collection[str]] | None = None,
        registrar: Callable[[RegistroDaChamada], None] | None = None,
        contador: ContadorDoAtendimento | None = None,
        concorrencia: Mapping[str, int] = CONCORRENCIA_POR_SERVICO,
        cronometro: Callable[[], float] = time.perf_counter,
    ) -> None:
        simuladores = dict(simuladores or {})
        if fora := sorted((set(executores) | set(simuladores)) - {s.nome for s in catalogo}):
            raise ValueError(f"executor sem ferramenta no catálogo: {', '.join(fora)}")
        self._catalogo, self._destinos, self._leitor = catalogo, destinos, leitor_de_modo
        self._executores, self._simuladores = dict(executores), simuladores
        self._precondicoes = dict(precondicoes or {})
        self._referencias, self._ler_cpf = referencias, leitor_de_cpf
        self._bancos_ligados = bancos_ligados or (lambda flag: ())
        self._registrar, self._contador = registrar, contador or ContadorDoAtendimento()
        self._limitadores = {servico: asyncio.Semaphore(n) for servico, n in concorrencia.items()}
        self._cronometro = cronometro

    # --- a chamada ---------------------------------------------------------------------------------------------------------------------

    async def chamar(
        self, nome: str, args: Any, contexto: ContextoDaChamada, *, orcamento: OrcamentoDoTurno, pelo_modelo: bool = False
    ) -> Resultado:
        spec = self._catalogo.get(nome)
        if spec is None:  # sem nome do ledger (CHECK da 0001): só a linha de log
            registro.info("ferramenta recusada: fora do catálogo")
            return Resultado("?", erro=ErroDeFerramenta("PARAMETRO_INVALIDO"))
        andamento = _Andamento()
        with observabilidade.span_da_ferramenta(ferramenta=spec.nome_no_ledger, versao=spec.versao, classe=spec.classe) as span:
            try:
                if pelo_modelo and not spec.do_modelo:  # o modelo pedindo o que não pode vai ao registro e ao span (revisão B5.1, B-4)
                    raise ErroDeFerramenta("PARAMETRO_INVALIDO")
                pedido = self._preparar(spec, args, contexto, pelo_modelo)
                andamento.args_hash, andamento.banco = _hash_dos_args(pedido), pedido.banco
                self._conferir_orcamento(spec, contexto, orcamento)
                await self._conferir_precondicoes(pedido)
                dados = await self._executar(pedido, andamento, orcamento)
                resultado = Resultado(spec.nome, dados=dados, destino=andamento.destino)
            except ErroDeFerramenta as erro:  # cópia nova: sem a causa do executor nem os frames com o CPF (M-4)
                resultado = Resultado(spec.nome, erro=erro.copia_limpa(), destino=andamento.destino)
            self._fechar(spec, contexto, resultado, andamento, span)
        return resultado

    def _preparar(self, spec: Especificacao, args: Any, contexto: ContextoDaChamada, pelo_modelo: bool) -> Pedido:
        validado: BaseModel | None = None
        if isinstance(args, Mapping):
            with contextlib.suppress(ValidationError):
                validado = spec.entrada.model_validate(dict(args))
        if validado is None:  # fora do `except`: o erro não carrega o argumento recusado
            raise ErroDeFerramenta("PARAMETRO_INVALIDO")
        referencias = {
            campo: self._referencia(contexto, campo, str(valor), pelo_modelo)
            for campo in CAMPOS_DE_REFERENCIA
            if (valor := getattr(validado, campo, None)) is not None
        }
        return Pedido(spec, validado, referencias, contexto, self._banco(spec, referencias))

    def _referencia(self, contexto: ContextoDaChamada, campo: str, valor: str, pelo_modelo: bool) -> Referencia:
        real = contexto.apelidos.mapa.get(valor)
        if real is None and pelo_modelo:
            raise ErroDeFerramenta("PARAMETRO_INVALIDO")  # o modelo só cita o apelido que o contexto lhe deu
        if self._referencias is None:
            if real is None:
                raise ErroDeFerramenta("PARAMETRO_INVALIDO")  # id cru sem quem o confira no estado
            return Referencia(real)
        referencia = self._referencias(contexto.atendimento_id, campo, real if real is not None else valor)
        if referencia is None:
            raise ErroDeFerramenta("PARAMETRO_INVALIDO")  # não é deste atendimento
        return referencia

    @staticmethod
    def _banco(spec: Especificacao, referencias: Mapping[str, Referencia]) -> str | None:
        bancos = {r.banco for r in referencias.values() if r.banco}
        if len(bancos) > 1:
            raise ErroDeFerramenta("PARAMETRO_INVALIDO")
        banco = next(iter(bancos), None) or (spec.bancos[0] if len(spec.bancos) == 1 else None)
        if spec.servico == "banco" and banco not in SERVICO_DO_BANCO:
            raise ErroDeFerramenta("PARAMETRO_INVALIDO")
        if spec.bancos and banco not in spec.bancos:
            raise ErroDeFerramenta("PRECONDICAO_FALHOU", precondicao="banco_habilitado")
        return banco

    def _conferir_orcamento(self, spec: Especificacao, contexto: ContextoDaChamada, orcamento: OrcamentoDoTurno) -> None:
        """Os tetos do atendimento aqui são a recusa cedo; a paga é contada de novo, atômica, no disparo. A vaga da síncrona é RESERVADA
        aqui, sem `await` entre conferir e contar (chamadas do modelo rodam em paralelo; revisão B5.1, M-1)."""
        atendimento = contexto.atendimento_id
        esgotado = (spec.classe == "leitura_paga" and self._contador.pagas(atendimento) >= self._contador.max_pagas) or (
            spec.classe == "efeito_irreversivel" and self._contador.corrigiveis(atendimento) >= self._contador.max_corrigiveis
        )
        if esgotado or (spec.execucao == "sincrona" and not orcamento.reservar()):
            raise ErroDeFerramenta("ORCAMENTO_ESGOTADO")

    async def _conferir_precondicoes(self, pedido: Pedido) -> None:
        spec = pedido.especificacao
        if spec.flag_dos_bancos is not None and not await _vale(lambda p: p.banco in self._bancos_ligados(spec.flag_dos_bancos), pedido):
            raise ErroDeFerramenta("PRECONDICAO_FALHOU", precondicao="banco_habilitado")
        for nome in spec.precondicoes:
            verificar = self._precondicoes.get(nome)
            if verificar is None or not await _vale(verificar, pedido):
                raise ErroDeFerramenta("PRECONDICAO_FALHOU", precondicao=nome)

    def _resolver(self, pedido: Pedido) -> Destino:
        spec, contexto = pedido.especificacao, pedido.contexto
        modo = self._leitor.efetivo(contexto.atendimento_modo)  # relido na hora do efeito, não no começo do turno (R2-02)
        servico = SERVICO_DO_BANCO[pedido.banco] if spec.servico == "banco" and pedido.banco else spec.servico
        return self._destinos.resolver(servico, spec.classe, modo, posse_real=contexto.posse_real)

    async def _executar(self, pedido: Pedido, andamento: _Andamento, orcamento: OrcamentoDoTurno) -> BaseModel:
        spec = pedido.especificacao
        bruto, tipado, codigo, despachado = await self._rodar(pedido, andamento, orcamento)
        if tipado is not None:  # o erro tipado é refeito aqui, fora do `except`: sem a causa do executor (M-4)
            if despachado and tipado[0] == "CORRIGIVEL":  # o executor levantou `CORRIGIVEL`: conta no teto de 3 (M-3)
                self._contador.registrar_corrigivel(pedido.contexto.atendimento_id)
            raise ErroDeFerramenta(tipado[0], precondicao=tipado[1], retry_apos_s=tipado[2])
        if codigo is not None:
            raise ErroDeFerramenta(codigo)
        dados = reconstruir(spec, bruto)
        if getattr(dados, "classe", None) == "corrigivel":
            self._contador.registrar_corrigivel(pedido.contexto.atendimento_id)
        return dados

    async def _rodar(
        self, pedido: Pedido, andamento: _Andamento, orcamento: OrcamentoDoTurno
    ) -> tuple[Any, tuple[CodigoDeErro, str | None, int | None] | None, CodigoDeErro | None, bool]:
        """Vaga do limitador → destino → CPF → executor, com timeout. Devolve (retorno, erro tipado, código, despachado); nenhuma exceção
        sobe com a mensagem.

        - A vaga vem PRIMEIRO (o serviço não depende do modo) e o destino é resolvido depois dela, logo antes do executor: a parada dura
          alcança a T7 que esperava na fila atrás de duas T8 (revisão B5.1, A-1). Se o CPF é lido, o destino é relido depois da leitura.
        - Síncrona: um prazo só cobre a fila e o efeito (a espera conta no turno e estoura como `BANCO_INDISPONIVEL`; M-2). Assíncrona: a
          fila tem o seu prazo e, ao pegar a vaga, o prazo do efeito recomeça (`reschedule`).
        - `INDETERMINADO` só quando o efeito irreversível SAIU (`despachado`): timeout na fila não é dúvida, nada foi enviado."""
        spec = pedido.especificacao
        sincrona = spec.execucao == "sincrona"
        prazo = min(spec.timeout_s, orcamento.restante_s()) if sincrona else spec.timeout_s
        limitador = self._limitadores.get(_servico(pedido))
        inicio, despachado = self._cronometro(), False
        retorno: Any = None
        tipado: tuple[CodigoDeErro, str | None, int | None] | None = None
        codigo: CodigoDeErro | None = None
        try:
            async with asyncio.timeout(prazo) as relogio_do_prazo:
                async with limitador or contextlib.nullcontext():
                    if not sincrona:
                        relogio_do_prazo.reschedule(asyncio.get_running_loop().time() + spec.timeout_s)
                    funcao, chamada = await self._preparar_disparo(pedido, andamento)
                    despachado = True  # daqui até o `await` não há ponto de espera: o destino é o desta hora
                    retorno = await funcao(chamada)
        except ErroDeFerramenta as erro:  # do gateway (antes do disparo) ou do executor (CORRIGIVEL, RECUSA…): só os campos do vocabulário
            tipado = (erro.codigo, erro.precondicao, erro.retry_apos_s)
        except TimeoutError:
            codigo = "INDETERMINADO" if despachado and spec.classe == "efeito_irreversivel" else "BANCO_INDISPONIVEL"
        except Exception:
            codigo = "INDETERMINADO" if despachado and spec.classe == "efeito_irreversivel" else "DESCONHECIDO"
        finally:
            decorrido = self._cronometro() - inicio
            andamento.latencia_ms = max(int(decorrido * 1000), 0)
            if sincrona:
                orcamento.gastar(decorrido)
        return retorno, tipado, codigo, despachado

    async def _preparar_disparo(self, pedido: Pedido, andamento: _Andamento) -> tuple[Executor, Chamada]:
        """Destino desta hora, CPF se o destino o pede e a consulta paga contada; o último passo antes do executor não tem `await`."""
        spec = pedido.especificacao
        destino = self._resolver(pedido)
        cpf: CpfEmMemoria | None = None
        if spec.usa_cpf and destino.tipo in _DESTINOS_COM_CPF:
            cpf = await self._cpf(pedido)
            destino = self._resolver(pedido)  # a leitura do CPF é um ponto de espera: o modo pode ter mudado nela
            if destino.tipo not in _DESTINOS_COM_CPF:
                cpf = None
        andamento.destino = destino
        interceptado = destino.tipo == "interceptado"
        funcao = (self._simuladores if interceptado else self._executores).get(spec.nome)
        if funcao is None:
            raise ErroDeFerramenta("MODO_SOMENTE_LEITURA" if interceptado else "DESCONHECIDO")
        if spec.classe == "leitura_paga" and not self._contador.reservar_paga(pedido.contexto.atendimento_id):
            raise ErroDeFerramenta("ORCAMENTO_ESGOTADO")
        return funcao, Chamada(pedido, destino, cpf)

    async def _cpf(self, pedido: Pedido) -> CpfEmMemoria:
        cpf = None
        if self._ler_cpf is not None:
            with contextlib.suppress(Exception):
                cpf = await self._ler_cpf(pedido.contexto.pessoa_id)
        if not isinstance(cpf, CpfEmMemoria):
            raise ErroDeFerramenta("DESCONHECIDO")
        return cpf

    def _fechar(self, spec: Especificacao, contexto: ContextoDaChamada, resultado: Resultado, andamento: _Andamento, span: Any) -> None:
        destino = andamento.destino
        linha = RegistroDaChamada(
            atendimento_id=contexto.atendimento_id,
            ferramenta=spec.nome_no_ledger,
            versao=spec.versao,
            classe=spec.classe,
            resultado="ok" if resultado.erro is None else resultado.erro.codigo.lower(),
            modo_efetivo=destino.modo_efetivo if destino else None,
            destino=destino.tipo if destino else None,
            simulado=destino.simulado if destino else True,
            latencia_ms=andamento.latencia_ms,
            args_hash=andamento.args_hash,
            banco=andamento.banco,
        )
        for chave in ("resultado", "modo_efetivo", "destino", "latencia_ms"):
            if (valor := getattr(linha, chave)) is not None:
                span.set_attribute(chave, valor)
        registro.info(
            "ferramenta %s@%s %s destino=%s modo=%s", linha.ferramenta, linha.versao, linha.resultado, linha.destino, linha.modo_efetivo
        )
        if self._registrar is not None:
            self._registrar(linha)

    # --- o agente ---------------------------------------------------------------------------------------------------------------------

    def ferramentas_do_agente(self) -> dict[str, Tool[Deps]]:
        """As `Tool` do `Agent` geradas do registro (aceite da B5.1): só as do modelo, com o esquema de entrada da especificação. Passe a
        `criar_agente(..., ferramentas=gateway.ferramentas_do_agente())`: o retorno ainda passa pela projeção e pela fase da B1.4."""
        return {spec.nome: self._tool(spec) for spec in self._catalogo if spec.do_modelo}

    def _tool(self, spec: Especificacao) -> Tool[Deps]:
        async def funcao(ctx: RunContext[Deps], **argumentos: Any) -> dict[str, Any]:
            deps = ctx.deps
            contexto = ContextoDaChamada(deps.atendimento_id, deps.pessoa_id, deps.modo, deps.posse_real, deps.apelidos)
            orcamento = deps.orcamento if deps.orcamento is not None else OrcamentoDoTurno.esgotado()
            resultado = await self.chamar(spec.nome, argumentos, contexto, orcamento=orcamento, pelo_modelo=True)
            return resultado.retorno_ao_modelo()

        return Tool.from_schema(
            funcao, name=spec.nome, description=spec.descricao, json_schema=_esquema_para_o_modelo(spec.entrada), takes_ctx=True
        )


def _servico(pedido: Pedido) -> str:
    spec = pedido.especificacao
    return SERVICO_DO_BANCO.get(pedido.banco or "", "") if spec.servico == "banco" else spec.servico


async def _vale(verificar: Callable[[Pedido], Any], pedido: Pedido) -> bool:
    """O verificador disse `True` (síncrono ou não)? Exceção ou qualquer outra resposta é `False` (fail-closed)."""
    try:
        resposta = verificar(pedido)
        if inspect.isawaitable(resposta):
            resposta = await resposta
    except Exception:
        return False
    return resposta is True
