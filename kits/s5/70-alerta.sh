#!/usr/bin/env bash
# 70-alerta.sh — instala o `ia-alerta` (ntfy.sh público com tópico secreto, DEC-PIA-010) e a unidade `ia-s5-alerta@.service`, que os
# timers do kit usam em OnFailure. O tópico fica em /etc/ia-s5-adm/ntfy.topico (root 0600) e NUNCA vai para argumento de comando,
# log ou mensagem. A mensagem só aceita CÓDIGO e pares de uma LISTA FECHADA: chave em {unidade, banco, origem} com valor de rótulo
# técnico (minúsculas, dígito, _ e -, começando por letra; ex.: ia-s5-backup, ia_atendimento) e chave em {horas, arquivos, livre_pct}
# com valor NUMÉRICO de até 5 dígitos. Qualquer outro par vira `par_recusado=1` (regra «sem dado pessoal na mensagem»: nome,
# CPF formatado, telefone e e-mail não passam).
#
# Uso:  sudo bash 70-alerta.sh [--aplicar]           instala
#       sudo bash 70-alerta.sh --aplicar --testar    instala e manda «s5 teste_alerta» (confere no celular)
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir NTFY_URL_BASE
exigir_root
[[ "$NTFY_URL_BASE" =~ ^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?$ ]] || [[ "$NTFY_URL_BASE" =~ ^http://127\.0\.0\.1:[0-9]{1,5}$ ]] \
  || falhar "NTFY_URL_BASE deve ser https://host (http só em 127.0.0.1, para ensaio)"
TESTAR=0; [ "${ARGS_RESTANTES[0]:-}" = --testar ] && TESTAR=1

titulo "1. /usr/local/sbin/ia-alerta"
escrever /usr/local/sbin/ia-alerta 755 root:root <<SCRIPT
#!/usr/bin/env bash
# ia-alerta <codigo> [chave=valor ...] — manda um alerta da S5 ao ntfy (kit s5, 70-alerta.sh). Root (lê o tópico 0600).
set -euo pipefail
BASE="${NTFY_URL_BASE}"
TOPICO_ARQ=/etc/ia-s5-adm/ntfy.topico
codigo="\${1:-}"; shift || true
[[ "\$codigo" =~ ^[a-z0-9_]{1,40}\$ ]] || { logger -t ia-alerta "codigo recusado"; codigo="alerta_invalido"; set --; }
[ "\$#" -le 6 ] || { logger -t ia-alerta "pares demais"; codigo="alerta_invalido"; set --; }
msg="s5 \$codigo"
for par in "\$@"; do
  # lista fechada: rótulo técnico só nas chaves de rótulo; número só nas chaves de contagem
  if [[ "\$par" =~ ^(unidade|banco|origem)=[a-z][a-z0-9_-]{0,31}\$ ]] || [[ "\$par" =~ ^(horas|arquivos|livre_pct)=[0-9]{1,5}\$ ]]; then msg="\$msg \$par"
  else logger -t ia-alerta "par recusado em \$codigo"; msg="\$msg par_recusado=1"; fi
done
[ -r "\$TOPICO_ARQ" ] || { logger -t ia-alerta "sem topico; alerta \$codigo perdido"; exit 2; }
topico="\$(head -1 "\$TOPICO_ARQ" | tr -d '\r\n')"
[[ "\$topico" =~ ^[A-Za-z0-9_-]{16,64}\$ ]] || { logger -t ia-alerta "topico invalido"; exit 2; }
# a URL (que contém o tópico) vai por arquivo de configuração do curl via descritor, nunca na linha de comando (ps, journal)
if curl -sS --fail-with-body --max-time 10 --retry 3 --retry-delay 5 -o /dev/null \\
     -H "Title: IA S5" -H "Tags: warning" --data-raw "\$msg" -K <(printf 'url = "%s/%s"\n' "\$BASE" "\$topico") 2>/dev/null; then
  logger -t ia-alerta "enviado \$codigo"
else
  logger -t ia-alerta "FALHA ao enviar \$codigo (ntfy fora?)"; exit 1
fi
SCRIPT

titulo "2. ia-s5-alerta@.service (OnFailure dos timers do kit)"
escrever /etc/systemd/system/ia-s5-alerta@.service 644 root:root <<'UNIT'
[Unit]
Description=kit s5: alerta ntfy da falha de %i

[Service]
Type=oneshot
# %i = nome da unidade que falhou, sem o sufixo (as unidades do kit usam OnFailure=ia-s5-alerta@%N.service); não é dado pessoal.
# O ia-alerta valida o formato de novo.
ExecStart=/usr/local/sbin/ia-alerta unidade_falhou unidade=%i
UNIT
rodar systemctl daemon-reload

if [ "$TESTAR" = 1 ]; then
  titulo "3. teste"
  rodar /usr/local/sbin/ia-alerta teste_alerta origem=kit
fi
resumo_ok
