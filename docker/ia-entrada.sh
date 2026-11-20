#!/bin/sh
# Ponto de entrada da imagem: carrega os SEGREDOS de arquivos 0600 e só então executa o comando do serviço.
#
# Por que arquivo e não variável do compose (DEC-PIA-008, P-R10, RS-07): variável do compose fica no banco do Coolify, nos backups
# dele e no `docker inspect`; arquivo 0600 montado `:ro` não. O compose versionado só cita NOMES de configuração não secreta.
#
# Regras (falha fechado, sem nunca imprimir valor):
#   - diretório: "$IA_SEGREDOS_DIR/env" (montado :ro pelo compose). Sem IA_SEGREDOS_DIR: nada é carregado (o Settings recusa o boot).
#   - um arquivo por segredo, com o NOME da variável (ex.: env/MODELO_API_KEY_1). Só os nomes da lista SEGREDOS abaixo são lidos.
#   - o arquivo tem de ser regular (não link), do uid do processo e modo 600 ou 400; senão sai 78 (EX_CONFIG) citando só o nome.
#   - a mesma variável não pode vir do ambiente E do arquivo (origem ambígua): sai 78.
#   - o conteúdo é a primeira linha do arquivo, sem o fim de linha.
set -eu

SEGREDOS="DATABASE_URL MODELO_API_KEY_1 API_TOKENS CHAVE_H16 CHAVE_FINGERPRINT CHAT_REF_CHAVE PHOENIX_API_KEY"

falhar() {
  echo "ia-entrada: $*" >&2
  exit 78
}

if [ -n "${IA_SEGREDOS_DIR:-}" ]; then
  dir="${IA_SEGREDOS_DIR%/}/env"
  [ -d "$dir" ] || falhar "diretório de segredos ausente: $dir"
  eu="$(id -u)"
  for nome in $SEGREDOS; do
    arq="$dir/$nome"
    [ -e "$arq" ] || [ -L "$arq" ] || continue
    [ ! -L "$arq" ] || falhar "$nome: link simbólico recusado"
    [ -f "$arq" ] || falhar "$nome: não é arquivo regular"
    modo="$(stat -c '%a' "$arq")"
    dono="$(stat -c '%u' "$arq")"
    case "$modo" in 600 | 400) ;; *) falhar "$nome: modo $modo (exigido 600 ou 400)" ;; esac
    [ "$dono" = "$eu" ] || falhar "$nome: dono uid $dono, processo uid $eu (chown para o uid do contêiner)"
    eval "atual=\${$nome:-}"
    [ -z "$atual" ] || falhar "$nome: definido no ambiente E em arquivo; deixe só o arquivo"
    IFS= read -r valor <"$arq" || [ -n "${valor:-}" ] || falhar "$nome: arquivo vazio"
    valor="${valor%"$(printf '\r')"}"   # arquivo colado com CRLF: o \r final não é parte do segredo
    [ -n "$valor" ] || falhar "$nome: arquivo vazio"
    export "$nome=$valor"
    unset valor atual
  done
fi

[ "$#" -gt 0 ] || falhar "nenhum comando"
exec "$@"
