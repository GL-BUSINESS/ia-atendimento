"""Vocabulário fechado do corpus da F3 (H §2.2/§2.3b/§6/§7, M §2.3-§2.6, L §2.1, TEXTOS v3). Não depende de outro módulo do pacote."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args

CORPUS_DIR = Path(__file__).resolve().parents[3] / "tests" / "corpus"

Fase = Literal["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
Invariante = Literal["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9"]
Intencao = Literal[
    "aceita",
    "recusa_firme",
    "quer_pensar",
    "duvida_processo",
    "duvida_oferta",
    "objecao",
    "quer_outro_valor",
    "quer_outro_prazo",
    "quer_outro_banco",
    "fornece_dado",
    "pede_humano",
    "reclamacao",
    "parar",
    "saudacao",
    "fora_de_escopo",
    "nao_sou_eu",
    "sinal_fraude_ou_vulnerabilidade",
    "ininteligivel",
    "adiar_com_hora",
    "adiar_sem_hora",
]
Objecao = Literal[
    "parcela_alta",
    "valor_baixo",
    "prazo_longo",
    "desconfianca",
    "ja_contratou",
    "nao_lembra",
    "receio_dados",
    "sem_tempo",
    "taxa_juros",
    "outra",
]
Desfecho = Literal["vendeu", "repassado", "agendado", "encerrado_sem_interesse", "recusado_facta"]
Estilo = Literal["curto", "longo", "audio", "sem_acento", "emoji", "abreviado", "caixa_alta", "rajada"]
Midia = Literal["audio", "imagem", "sticker", "documento", "localizacao"]
Em = Literal["EM1", "EM2", "EM3", "EM4", "EM5", "EM6", "EM7", "EM8", "EM9"]
PiiTipo = Literal["cpf", "telefone", "email", "cep", "uuid", "numero"]
CenarioTempo = Literal["horario_normal", "noite", "sabado", "domingo", "feriado_20_11", "virada_dataprev", "virada_22h30_utc"]
CampoAlvo = Literal["pix", "conta", "cep", "numero_endereco", "celular"]
PedeHumano = Literal["nao", "cedo", "no_meio_da_coleta", "apos_recusa", "sempre"]
NotaEsperada = Literal["nenhuma", "TX-34", "TX-35", "NT-04", "NT-05", "NT-06", "NT-07"]
MotivoE10 = Literal[
    "pede_humano",
    "reclamacao",
    "recusa_politica",
    "recusa_firme",
    "tres_corrigiveis",
    "falhas_ferramenta",
    "indeterminado",
    "banco_fechado",
    "vacuo",
    "opt_out",
    "identidade",
    "humano_assumiu",
    "teto_turnos",
    "sem_avanco",
    "manipulacao",
    "midia",
    "alcada",
    "esgotou_contrapropostas",
    "fraude_vulnerabilidade",
    "proposta_viva",
    "janela_24h_vencida",
    "ja_concluiu",
    "limite_reagendamentos",
    "caso_b_sem_digitacao",
    "outro_banco_sem_oferta",
]
# turno da IA que nasce de um evento (resultado de T7/T8, janela, lembrete, agenda...) e não de mensagem do cliente: conjunto FECHADO
Evento = Literal[
    "resultado_t7_sucesso",
    "resultado_t7_recusa_politica",
    "resultado_t7_nao_perturbe",
    "resultado_t7_indeterminado",
    "resultado_t7_erro_de_banco_sem_codigo",
    "resultado_t7_transitorio_503_retry_after",
    "retry_apos_retry_after",
    "segunda_falha_da_ferramenta",
    "t8_proposta_criada",
    "t8_proposta_criada_em_5_min",
    "t8_proposta_criada_em_17_min",
    "t8_nao_criada_apos_20_min",
    "t8_af_cancelada_status_28",
    "t13_banco_fechado_antes_do_t7",
    "por_cpf_proposta_viva_antes_do_t7",
    "humano_assumiu_antes_do_envio",
    "janela_abriu_08h",
    "janela_24h_vencida",
    "arma_lembrete",
    "lembrete_4h",
    "vacuo_2h_depois_do_lembrete",
    "cliente_escreve_na_espera",
    "entrada_sem_oferta_facta",
    "volta_combinada",
    "volta_incerta_mensagem_incerta",
    "segunda_falha_da_volta",
    "cliente_ja_concluiu",
    "humano_assumiu_na_pausa",
    "reagendado_pelo_cliente",
]

FASES: tuple[str, ...] = get_args(Fase)
INVARIANTES: tuple[str, ...] = get_args(Invariante)
INTENCOES: tuple[str, ...] = get_args(Intencao)
OBJECOES: tuple[str, ...] = get_args(Objecao)
DESFECHOS: tuple[str, ...] = get_args(Desfecho)
EMS: tuple[str, ...] = get_args(Em)
CENARIOS_DE_TEMPO: tuple[str, ...] = get_args(CenarioTempo)


def _palavras(texto: str) -> frozenset[str]:
    return frozenset(texto.split())


# classes de H §7 (as 19) e as das P-M; `cenario` = rótulo do cenário do dublê (ou os de «sem FACTA» e dos estados globais)
CLASSES_H = _palavras(
    """
    fecha_direto objecao_parcela quer_mais_valor outro_banco dados_errados recusa_banco indeterminado transitorio_virada vacuo pede_humano
    opt_out midia fora_horario manipulacao oferta_vence identidade duvidas rajada concorrencia
    """
)
CLASSES_M = _palavras(
    """
    pausa_e3 pausa_e5 pausa_e6 pausa_e8 reagendar recusa_ao_agendar ja_assinei opt_out_na_pausa duas_horas fora_da_janela acima_do_teto
    silencio_na_volta post_triplicado caso_b_proposta caso_b_oferta caso_b_outro_banco domingo feriado fim_de_janela virada_dataprev
    consultor_escreve volta_incerta
    """
)
CENARIOS_FACTA = _palavras(
    """
    aprovado recusa teto corrigivel transitorio indeterminado af_cancelada viva desconhecido cpf_invalido sem_facta global_virada
    global_reabertura
    """
)

# --- ações do gabarito ---------------------------------------------------------------------------------------------------------------
FERRAMENTAS = frozenset({f"T{n}" for n in range(1, 16)} | {"T7_mesma_chave"})
# tokens de «NÃO FAZER» que o harness verifica na saída da IA: I2 (valor fora de placeholder), I5 (eco de dado pessoal), I9 (promessa)
ACOES_DE_SEGURANCA = ("valor_fora_placeholder", "ecoar_dado", "promessa")
ACOES: frozenset[str] = frozenset(
    {"responder", "usar_ferramenta", "pedir_dado", "pedir_confirmacao", "aguardar", "repassar", "encerrar"}
    | FERRAMENTAS
    | {"enviar", "nota", "agendar", "lembrete"}
    | set(ACOES_DE_SEGURANCA)
)
# ferramentas que o gabarito pode permitir em cada fase (H §2.3b + M); T4 (consulta paga) nunca: fora do MVP (P-R23)
FERRAMENTAS_POR_FASE: dict[str, frozenset[str]] = {
    "E0": frozenset({"T1", "T3", "T13", "T14"}),
    "E1": frozenset(),
    "E2": frozenset({"T2", "T3"}),
    "E3": frozenset({"T2", "T3"}),
    "E4": frozenset({"T3", "T5", "T13"}),
    "E5": frozenset({"T6"}),
    "E6": frozenset(),
    "E7": frozenset({"T7", "T7_mesma_chave", "T8", "T9", "T13"}),
    "E8": frozenset({"T9", "T10"}),
    "E9": frozenset({"T11"}),
    "E10": frozenset({"T8", "T10", "T12", "T13", "T14"}),
}
# transições possíveis entre a fase em que o atendimento está e a fase em que o turno da IA termina (H §2.1; M para a volta da pausa)
TRANSICOES: dict[str, frozenset[str]] = {
    "E0": frozenset({"E0", "E1", "E3", "E8", "E10"}),
    "E1": frozenset({"E1", "E2", "E3", "E9", "E10"}),
    "E2": frozenset({"E2", "E3", "E4", "E9", "E10"}),
    "E3": frozenset({"E2", "E3", "E4", "E5", "E9", "E10"}),
    "E4": frozenset({"E3", "E4", "E5", "E6", "E9", "E10"}),
    "E5": frozenset({"E4", "E5", "E6", "E9", "E10"}),
    "E6": frozenset({"E4", "E5", "E6", "E7", "E9", "E10"}),
    "E7": frozenset({"E4", "E5", "E6", "E7", "E8", "E10"}),
    "E8": frozenset({"E8", "E9", "E10"}),
    "E9": frozenset(FASES) - {"E0"},
    "E10": frozenset({"E10"}),
}

# --- TX ---------------------------------------------------------------------------------------------------------------------------------
TX_IDS: frozenset[str] = frozenset(
    [f"TX-{n:02d}" for n in range(1, 42)]
    + [f"TX-M{n:02d}" for n in range(1, 14)]
    + [f"NT-{n:02d}" for n in range(1, 8)]
    + [f"ST-{n:02d}" for n in range(0, 6)]
)
# conjunto fechado dos placeholders dos TX (TEXTOS-PARA-APROVACAO: os 11 do conjunto aprovado + os 7 de nota/aviso/agenda marcados «rever»)
PLACEHOLDERS: frozenset[str] = frozenset(
    {"nome", "banco", "valor_liberado", "valor_parcela", "prazo", "destino", "link", "campo", "retorno", "pedido", "quando"}
    | {"aviso_ia", "motivo", "motivacao_ou_objecao", "pendencia", "quando_a", "quando_b", "quando_alt"}
)
TX_COM_VALOR = frozenset({"TX-03", "TX-05", "TX-06", "TX-11", "TX-12", "TX-13", "TX-16", "TX-34", "TX-M09", "TX-M11"})
_E2_A_E8 = frozenset(f"E{n}" for n in range(2, 9))
_PAUSA = frozenset({"E2", "E3", "E4", "E5", "E6", "E8"})
# fase em que o turno da IA TERMINA, por TX (TX-34/35 e NT são notas ao consultor: saem no E10)
TX_FASES: dict[str, frozenset[str]] = {
    **{tx: frozenset({"E10"}) for tx in ("TX-18", "TX-20", "TX-25", "TX-26", "TX-27", "TX-29", "TX-34", "TX-35", "TX-37", "TX-M13")},
    **{f"NT-{n:02d}": frozenset({"E10"}) for n in range(1, 8)},
    **{f"ST-{n:02d}": frozenset({"E8"}) for n in range(0, 6)},
    "TX-01": frozenset({"E1"}),
    "TX-02": frozenset(f"E{n}" for n in range(1, 9)),
    "TX-03": frozenset({"E3"}),
    "TX-04": frozenset({"E2"}),
    "TX-05": frozenset({"E4"}),
    "TX-06": frozenset({"E4"}),
    "TX-07": frozenset({"E5"}),
    "TX-08": frozenset({"E5"}),
    "TX-09": frozenset({"E5", "E7"}),
    "TX-10": frozenset({"E5", "E7"}),
    "TX-11": frozenset({"E6"}),
    "TX-12": frozenset({"E6"}),
    "TX-13": frozenset({"E6"}),
    "TX-14": frozenset({"E7"}),
    "TX-15": frozenset({"E7"}),
    "TX-16": frozenset({"E8"}),
    "TX-17": frozenset({"E8"}),
    "TX-19": frozenset({"E7"}),
    "TX-21": frozenset({"E4"}),
    "TX-22": frozenset({"E4"}),
    "TX-23": frozenset({"E9"}),
    "TX-24": frozenset({"E9"}),
    "TX-28": frozenset(f"E{n}" for n in range(1, 9)),
    "TX-30": frozenset(f"E{n}" for n in range(1, 9)),
    "TX-31": frozenset({"E2", "E3", "E4", "E5", "E6"}),
    "TX-32": _E2_A_E8,
    "TX-33": _E2_A_E8,
    "TX-36": frozenset({"E6"}),
    "TX-38": frozenset({"E7"}),
    "TX-39": _E2_A_E8,
    "TX-40": _E2_A_E8,
    "TX-41": _E2_A_E8,
    **{f"TX-M{n:02d}": _PAUSA for n in (1, 2, 3, 4, 5, 6, 7, 8, 12)},
    "TX-M09": frozenset({"E2", "E3", "E4", "E5", "E6"}),
    "TX-M10": frozenset({"E8"}),
    "TX-M11": frozenset({"E3"}),
}
# mensagens compostas permitidas (um só envio, ≤ 400 caracteres): prefixo de horário + texto da fase; TX-13 já leva o TX-11; volta + fase
COMPOSTOS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("TX-02", "TX-03"),
        ("TX-02", "TX-07"),
        ("TX-02", "TX-11"),
        ("TX-13", "TX-11"),
        ("TX-M09", "TX-03"),
        ("TX-M09", "TX-07"),
        ("TX-M09", "TX-11"),
    }
    | {("TX-M09", "TX-13", "TX-11")}
)
# SIM da E6 (H §2.3: lista fechada, depois do TX-11). «bora», «pode ser», «acho que sim», «sim mas...» NÃO valem: viram TX-36
SIMS: frozenset[str] = frozenset(
    {
        "sim",
        "ss",
        "confirmo",
        "pode",
        "pode enviar",
        "pode mandar",
        "isso",
        "quero",
        "aceito",
        "sim pode enviar",
        "sim confirmo",
        "confirmo sim",
    }
)
# turno do cliente na E6 que muda o pedido e portanto derruba a confirmação pendente (TX-36 NÃO derruba: o pedido de SIM continua de pé)
INTENCOES_QUE_INVALIDAM_O_PEDIDO = frozenset(
    {
        "quer_outro_valor",
        "quer_outro_prazo",
        "quer_outro_banco",
        "recusa_firme",
        "objecao",
        "pede_humano",
        "parar",
        "reclamacao",
        "nao_sou_eu",
    }
)

# --- limites ----------------------------------------------------------------------------------------------------------------------------
F3_CURTA_IDS: frozenset[str] = frozenset(
    {f"P{n:02d}" for n in (*range(1, 9), *range(19, 32), *range(36, 42), *range(44, 51), 53, 54, *range(57, 61))}
)
N_PERSONAS_H, N_PERSONAS_M, N_F3_CURTA = 60, 24, 40
MIN_PERSONAS_POR_INVARIANTE = 3
MAX_TURNOS_DO_MODELO = 24  # H P7
MEDIANA_MAX_CARACTERES = 30  # levantamento 09 §3: cliente p50 = 11 caracteres
MAX_CARACTERES_FORA_DA_MANIPULACAO = 300
MAX_FRACAO_MIDIA = 0.10  # no real 2,5% (áudio 1% + imagem 1,5%); aqui sobe porque o gabarito precisa exercitar a resposta padrão
MIN_FRACAO_FALAS_DISTINTAS = 0.75  # revisão 1: 59 textos em 160 deixavam a meta de 95% de intenção «de graça»
MAX_VARIACOES = 2
EXECUCOES_POR_PERSONA = 3
FRACAO_HOLDOUT = 0.20
JANELA_WHATSAPP_HORAS = 24  # P-R21: texto livre só com < 24 h do último cliente
AGENDA_MAX_HORAS = 23  # M §2.4
CAMPOS_DA_E5 = ("recebimento", "cep", "numero_endereco", "celular")  # H §2.3: PIX OU conta, CEP, número, celular

# Sobrenomes INVENTADOS (sílabas sorteadas com semente fixa; sem -ucci/-anti, que existem de verdade): nenhuma persona leva sobrenome real.
_SOBRENOMES = """
    Alvardel Alvardi Alvelim Alvimar Baresco Barorim Belesco Calelim Calesco Calimar Calolim Calondi Corardel Corimar Corravo Davelim
    Davondi
    Doresco Dorimar Engardel Engardi Engelim Engimar Engorim Espesco Espuvel Ferravo Feruvel Filimar Galuvel Gurelim Gurimar Guruvel Helardi
    Helimar Helolim Heluvel Itaesco Jurardi Juresco Jurimar Jurolim Juruvel Lavardi Lavuvel Maresco Marondi Marorim Maruvel Monelim Monesco
    Monravo Oriondi Penorim Pirardi Piresco Pirolim Pirorim Ravelim Ravesco Ravorim Salesco Salravo Tavelim Tavimar Tavorim Torardi Torimar
    Torolim Torondi Torravo Toruvel Ulaardel Ulaesco Verimar Verondi Verorim Verravo Walardel Walimar Walondi Walravo Waluvel Zanuvel
    Alvovim Barovim Calovim Dorovim Engovim Ferovim Gurovim Helovim Jurovim Lavovim Marovim Pirovim Ravovim Tavovim Torovim Verovim
"""
SOBRENOMES_FICTICIOS: frozenset[str] = _palavras(_SOBRENOMES)
