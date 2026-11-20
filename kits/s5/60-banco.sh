#!/usr/bin/env bash
# 60-banco.sh — bancos ia_atendimento e ia_obs, nas DUAS opções da DEC-PIA-009, escolhidas por BANCO_LOCAL no s5.env:
#
#   BANCO_LOCAL=s5  PostgreSQL ${PG_VERSAO} (PGDG) na própria S5: escuta em 127.0.0.1 (e no wg0 só para a S2 ler, se PG_LEITURA_S2=sim),
#                   sobe depois do wg0, papéis iguais aos da S4 (ia_owner dono; ia_app sem DDL/DELETE; ia_app_b reserva NOLOGIN;
#                   ia_leitura, ia_qualidade; ia_obs_a dono do ia_obs), pg_hba escrito por inteiro (só o que a IA usa + reject),
#                   TLS com CA própria para o ia_leitura_a da S2, senhas nascidas aqui (0600) e só o verificador SCRAM no banco.
#   BANCO_LOCAL=s4  nada de PostgreSQL aqui. O kit s4 (papéis, pg_hba, certificados) roda na S4 e entrega em ${S4_ENTREGA_DIR};
#                   este script COPIA para ${IA_SEGREDOS_DIR} com o dono e o modo que o código aceita (10001, 0600; G-0097).
#
# Nos dois casos termina gravando ${IA_SEGREDOS_DIR}/env/DATABASE_URL (0600, uid ${IA_UID}) sem imprimir a URL.
# As migrações são o passo seguinte: migrar.sh (G-0012).
#
# Uso:  sudo bash 60-banco.sh [--aplicar]
# Desfazer (S5; só com autorização nova do dono, é DROP): sudo -u postgres dropdb ia_atendimento; dropdb ia_obs; apagar os papéis ia_*.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ler_args "$@"
carregar_env
exigir BANCO_LOCAL IA_SEGREDOS_DIR IA_UID
validar_banco_local
exigir_root
[[ "$IA_UID" =~ ^[0-9]+$ ]] || falhar "IA_UID numérico"
ADM=/etc/ia-s5-adm
SENHAS="$ADM/pg-senhas"
ENV_DIR="$IA_SEGREDOS_DIR/env"

urlenc() { python3 -c 'import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.stdin.read().strip(), safe=""))'; }

diretorios() {
  titulo "0. diretórios de segredo (root:${IA_UID} 0750)"
  rodar install -d -m 750 -o root -g "$IA_UID" "$IA_SEGREDOS_DIR"
  rodar install -d -m 750 -o root -g "$IA_UID" "$ENV_DIR"
  rodar install -d -m 700 -o root -g root "$ADM"
}

# ---------------------------------------------------------------------------------------------------------------- opção S4
banco_na_s4() {
  exigir S4_ENTREGA_DIR WG_IP_S4 S4_PG_PORTA
  validar_ipv4 "$WG_IP_S4" WG_IP_S4
  titulo "1. certificados e senhas entregues pelo kit s4 → ${IA_SEGREDOS_DIR} (dono ${IA_UID}, 0600)"
  local f
  for f in ca.crt ia_app_a.crt ia_app_a.key ia_app_a.senha ia_obs_a.crt ia_obs_a.key ia_obs_a.senha; do
    if aplicando; then
      [ -s "$S4_ENTREGA_DIR/$f" ] || falhar "falta $S4_ENTREGA_DIR/$f (rode o kit s4: distribuir-certs.sh com VPS_SSH_DEST apontando a S5)"
      install -m 600 -o "$IA_UID" -g "$IA_UID" "$S4_ENTREGA_DIR/$f" "$IA_SEGREDOS_DIR/$f"
      info "$f copiado"
    else info "[simular] install -m 600 -o ${IA_UID} -g ${IA_UID} ${S4_ENTREGA_DIR}/$f ${IA_SEGREDOS_DIR}/$f"; fi
  done
  titulo "2. DATABASE_URL (ia_app_a → S4 pelo wg0, verify-full)"
  if aplicando; then
    { printf 'postgresql://ia_app_a:%s@%s:%s/ia_atendimento?sslmode=verify-full&sslrootcert=%s/ca.crt&sslcert=%s/ia_app_a.crt&sslkey=%s/ia_app_a.key' \
        "$(urlenc <"$IA_SEGREDOS_DIR/ia_app_a.senha")" "$WG_IP_S4" "$S4_PG_PORTA" "$IA_SEGREDOS_DIR" "$IA_SEGREDOS_DIR" "$IA_SEGREDOS_DIR"; } |
      escrever_segredo "$ENV_DIR/DATABASE_URL" "$IA_UID:$IA_UID"
  else info "[simular] gravaria $ENV_DIR/DATABASE_URL = postgresql://ia_app_a:<senha>@${WG_IP_S4}:${S4_PG_PORTA}/ia_atendimento?sslmode=verify-full&…"; fi
  info "as provas de conexão (positivo e negativo contra gl360) são do kit s4: provar.sh"
}

# ---------------------------------------------------------------------------------------------------------------- opção S5
P() { sudo -n -u postgres psql -X -q -p "$PG_PORTA" -v ON_ERROR_STOP=1 "$@"; }
consultar() { sudo -n -u postgres psql -X -qAt -p "$PG_PORTA" -d postgres -c "$1"; }
psql_db() {  # psql_db <banco> < SQL ; no simular mostra o SQL
  if aplicando; then P -d "$1"; else printf '   [simular] psql -d %s <<SQL\n' "$1"; sed 's/^/      | /'; fi
}

sql_papeis() { cat <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_owner')     THEN CREATE ROLE ia_owner     NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_app')       THEN CREATE ROLE ia_app       NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_leitura')   THEN CREATE ROLE ia_leitura   NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_qualidade') THEN CREATE ROLE ia_qualidade NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_app_a')     THEN CREATE ROLE ia_app_a     LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_leitura_a') THEN CREATE ROLE ia_leitura_a LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_obs_a')     THEN CREATE ROLE ia_obs_a     LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_app_b') THEN
    CREATE ROLE ia_app_b NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 20;
  END IF;
END $$;
ALTER ROLE ia_owner     NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE ia_app       NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE ia_leitura   NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE ia_qualidade NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE ia_app_a     LOGIN   NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20;
ALTER ROLE ia_leitura_a LOGIN   NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
ALTER ROLE ia_obs_a     LOGIN   NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20;
ALTER ROLE ia_app_b     NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT ia_app     TO ia_app_a, ia_app_b;
GRANT ia_leitura TO ia_leitura_a;
ALTER ROLE ia_leitura_a SET default_transaction_read_only = on;
ALTER ROLE ia_leitura_a SET statement_timeout = '5s';
ALTER ROLE ia_leitura_a SET idle_in_transaction_session_timeout = '10s';
SQL
}

sql_bancos_grants() { cat <<'SQL'
REVOKE ALL ON DATABASE ia_atendimento FROM PUBLIC;
REVOKE ALL ON DATABASE ia_obs FROM PUBLIC;
GRANT CONNECT ON DATABASE ia_atendimento TO ia_app, ia_leitura, ia_qualidade;
ALTER ROLE ia_app_a IN DATABASE ia_atendimento SET search_path = procrastinate, public;
ALTER ROLE ia_app_b IN DATABASE ia_atendimento SET search_path = procrastinate, public;
SQL
}

verificador() {  # ALTER ROLE com o verificador SCRAM-SHA-256, calculado do arquivo .senha (a senha não vai ao servidor nem à tela)
  python3 - "$SENHAS/$1.senha" "$1" <<'PY'
import base64, hashlib, hmac, os, sys
pw = open(sys.argv[1]).read().strip().encode()
it = 4096
salt = os.urandom(16)
s = hashlib.pbkdf2_hmac("sha256", pw, salt, it)
ck = hmac.new(s, b"Client Key", hashlib.sha256).digest()
sk = hmac.new(s, b"Server Key", hashlib.sha256).digest()
b = lambda x: base64.b64encode(x).decode()
print(f"ALTER ROLE {sys.argv[2]} PASSWORD 'SCRAM-SHA-256${it}:{b(salt)}${b(hashlib.sha256(ck).digest())}:{b(sk)}';")
PY
}

banco_na_s5() {
  exigir PG_VERSAO PG_PORTA PG_SHARED_BUFFERS PG_MAX_CONNECTIONS WG_IP_S5 WG_IP_S2
  validar_porta "$PG_PORTA" PG_PORTA; validar_ipv4 "$WG_IP_S5" WG_IP_S5; validar_ipv4 "$WG_IP_S2" WG_IP_S2
  [[ "$PG_VERSAO" =~ ^[0-9]{2}$ ]] || falhar "PG_VERSAO inválida"
  [[ "$PG_SHARED_BUFFERS" =~ ^[0-9]+(MB|GB)$ ]] || falhar "PG_SHARED_BUFFERS como 512MB ou 2GB"
  [[ "$PG_MAX_CONNECTIONS" =~ ^[0-9]+$ ]] || falhar "PG_MAX_CONNECTIONS numérico"
  local cluster="main" conf_dir="/etc/postgresql/${PG_VERSAO}/main" leitura="${PG_LEITURA_S2:-nao}" tls="$ADM/pg-tls"

  titulo "1. PostgreSQL ${PG_VERSAO} do repositório PGDG (e o locale pt_BR.UTF-8 dos bancos, igual à S4)"
  apt_instalar locales
  if locale -a 2>/dev/null | grep -qi '^pt_BR\.utf8$'; then info "locale pt_BR.UTF-8 presente"; else rodar_022 locale-gen pt_BR.UTF-8; fi
  if dpkg -s "postgresql-${PG_VERSAO}" >/dev/null 2>&1; then info "postgresql-${PG_VERSAO} já instalado"; else
    apt_instalar postgresql-common
    rodar_022 /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
    apt_instalar "postgresql-${PG_VERSAO}" "postgresql-client-${PG_VERSAO}"
  fi
  if aplicando; then
    pg_lsclusters -h | awk -v v="$PG_VERSAO" -v c="$cluster" -v p="$PG_PORTA" '$1==v && $2==c {f=1; if ($3!=p) {print "porta do cluster " $3 " != PG_PORTA " p; exit 1}} END {exit !f}' \
      || falhar "cluster ${PG_VERSAO}/${cluster} ausente ou em outra porta (pg_lsclusters)"
  fi

  titulo "2. TLS: CA própria da S5 (só para o ia_leitura_a da S2) e certificado do servidor"
  if aplicando; then
    install -d -m 700 "$tls"
    ( cd "$tls" && umask 077
      [ -s ca.key ] || { openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 1825 -subj "/O=GL Capital/CN=ia-s5-ca" \
                           -keyout ca.key -out ca.crt 2>/dev/null; info "CA criada (5 anos)"; }
      if [ ! -s servidor.crt ]; then
        openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj "/O=GL Capital/CN=${WG_IP_S5}" -keyout servidor.key -out servidor.csr 2>/dev/null
        printf 'subjectAltName=IP:%s,IP:127.0.0.1\n' "$WG_IP_S5" >servidor.ext
        openssl x509 -req -in servidor.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 397 -sha256 -extfile servidor.ext -out servidor.crt 2>/dev/null
        rm -f servidor.csr servidor.ext; info "certificado do servidor (397 dias)"
      fi
      if [ "$leitura" = sim ] && [ ! -s ia_leitura_a.crt ]; then
        openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj "/O=GL Capital/CN=ia_leitura_a" -keyout ia_leitura_a.key -out ia_leitura_a.csr 2>/dev/null
        openssl x509 -req -in ia_leitura_a.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 397 -sha256 -out ia_leitura_a.crt 2>/dev/null
        rm -f ia_leitura_a.csr; info "certificado de cliente ia_leitura_a (397 dias; entrega à S2 é do dono)"
      fi )
    install -m 644 -o root -g root "$tls/ca.crt" "$conf_dir/ia-ca.crt"
    install -m 644 -o postgres -g postgres "$tls/servidor.crt" "$conf_dir/ia-servidor.crt"
    install -m 600 -o postgres -g postgres "$tls/servidor.key" "$conf_dir/ia-servidor.key"
  else info "[simular] CA EC P-256 em $tls; servidor CN=${WG_IP_S5} (SAN IP); cliente ia_leitura_a se PG_LEITURA_S2=sim"; fi

  titulo "3. configuração (conf.d) e boot depois do wg0"
  local escuta="127.0.0.1"; [ "$leitura" = sim ] && escuta="127.0.0.1,${WG_IP_S5}"
  escrever "$conf_dir/conf.d/ia-s5.conf" 644 postgres:postgres <<CONF
# kit s5 (60-banco.sh) — bancos da IA na S5
listen_addresses = '${escuta}'
port = ${PG_PORTA}
max_connections = ${PG_MAX_CONNECTIONS}
shared_buffers = ${PG_SHARED_BUFFERS}
password_encryption = 'scram-sha-256'
ssl = on
ssl_cert_file = '${conf_dir}/ia-servidor.crt'
ssl_key_file = '${conf_dir}/ia-servidor.key'
ssl_ca_file = '${conf_dir}/ia-ca.crt'
ssl_min_protocol_version = 'TLSv1.3'
log_connections = 'authentication'
log_disconnections = off
log_line_prefix = '%m [%p] %q%u@%d '
# sem arquivamento de WAL: o backup é lógico (80-backup.sh); PITR fica como pendência do dono
archive_mode = off
CONF
  dropin_apos_wg0 "postgresql@${PG_VERSAO}-${cluster}.service"

  titulo "4. pg_hba por inteiro (backup e volta sozinho se o servidor recusar)"
  {
    echo "# kit s5 (60-banco.sh) — arquivo inteiro gerado; o original fica em .bak-ia-*"
    echo "local   all             postgres                                peer"
    echo "host    ia_atendimento  ia_app_a        127.0.0.1/32            scram-sha-256"
    echo "host    ia_obs          ia_obs_a        127.0.0.1/32            scram-sha-256"
    [ "$leitura" = sim ] && echo "hostssl ia_atendimento  ia_leitura_a    ${WG_IP_S2}/32           scram-sha-256  clientcert=verify-full"
    echo "host    all             all             0.0.0.0/0               reject"
    echo "host    all             all             ::/0                    reject"
    echo "local   all             all                                     reject"
  } | escrever "$conf_dir/pg_hba.conf" 640 postgres:postgres

  if aplicando; then
    # o servidor ainda roda com a config anterior: pg_hba_file_rules lê o arquivo NOVO do disco. Erro ⇒ restaura antes de reiniciar
    # (um pg_hba inválido impede o PostgreSQL de subir).
    systemctl start "postgresql@${PG_VERSAO}-${cluster}"
    for _ in $(seq 1 20); do consultar "select 1" >/dev/null 2>&1 && break; sleep 1; done
    if [ "$(consultar "select count(*) from pg_hba_file_rules where error is not null")" != 0 ]; then
      ultimo="$(ls -1t "$conf_dir"/pg_hba.conf.bak-ia-* 2>/dev/null | head -1 || true)"
      [ -z "$ultimo" ] || cp -p "$ultimo" "$conf_dir/pg_hba.conf"
      falhar "pg_hba novo com erro; restaurado o anterior, servidor não reiniciado"
    fi
    systemctl daemon-reload
    systemctl enable "postgresql@${PG_VERSAO}-${cluster}"
    systemctl restart "postgresql@${PG_VERSAO}-${cluster}"
    for _ in $(seq 1 30); do consultar "select 1" >/dev/null 2>&1 && break; sleep 1; done
    consultar "select 1" >/dev/null || falhar "o PostgreSQL não voltou depois do restart (journalctl -u postgresql@${PG_VERSAO}-${cluster})"
    info "servidor no ar com a config do kit; pg_hba sem erro"
  else rodar systemctl restart "postgresql@${PG_VERSAO}-${cluster}"; fi

  titulo "5. senhas (nascem aqui, 0600) e papéis"
  local l
  rodar install -d -m 700 "$SENHAS"
  for l in ia_app_a ia_obs_a ia_leitura_a; do
    if aplicando; then
      [ -s "$SENHAS/$l.senha" ] && info "$l: senha já existe" || { gerar_aleatorio 44 | escrever_segredo "$SENHAS/$l.senha" root:root; }
    else info "[simular] senha de $l em $SENHAS/$l.senha (0600) se ainda não existir"; fi
  done
  sql_papeis | psql_db postgres
  for l in ia_app_a ia_obs_a ia_leitura_a; do
    if aplicando; then verificador "$l" | P -d postgres; info "$l: verificador SCRAM gravado"; else info "[simular] ALTER ROLE $l PASSWORD 'SCRAM-SHA-256\$4096:…'"; fi
  done

  titulo "6. bancos e privilégios"
  local d dono
  for d in "ia_atendimento ia_owner" "ia_obs ia_obs_a"; do
    read -r nome dono <<<"$d"
    if aplicando && [ "$(consultar "select count(*) from pg_database where datname = '$nome'")" = 1 ]; then info "$nome já existe"
    else
      printf "CREATE DATABASE %s OWNER %s TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER libc LC_COLLATE 'pt_BR.UTF-8' LC_CTYPE 'pt_BR.UTF-8';\n" "$nome" "$dono" | psql_db postgres
    fi
  done
  sql_bancos_grants | psql_db postgres

  titulo "7. DATABASE_URL do app (ia_app_a por 127.0.0.1) em ${ENV_DIR}"
  if aplicando; then
    printf 'postgresql://ia_app_a:%s@127.0.0.1:%s/ia_atendimento' "$(urlenc <"$SENHAS/ia_app_a.senha")" "$PG_PORTA" |
      escrever_segredo "$ENV_DIR/DATABASE_URL" "$IA_UID:$IA_UID"
  else info "[simular] gravaria $ENV_DIR/DATABASE_URL = postgresql://ia_app_a:<senha>@127.0.0.1:${PG_PORTA}/ia_atendimento"; fi

  titulo "8. conferência"
  if aplicando; then
    local esperado_papeis atual
    esperado_papeis=$'ia_app|f|-1\nia_app_a|t|20\nia_app_b|f|20\nia_leitura|f|-1\nia_leitura_a|t|4\nia_obs_a|t|20\nia_owner|f|-1\nia_qualidade|f|-1'
    atual="$(consultar "select rolname || '|' || case when rolcanlogin then 't' else 'f' end || '|' || rolconnlimit from pg_roles where rolname like 'ia\_%' order by rolname collate \"C\"")"
    [ "$atual" = "$esperado_papeis" ] && info "OK  8 papéis como na S4" || falhar "papéis diferem do esperado"
    atual="$(consultar "select datname || '|' || pg_get_userbyid(datdba) from pg_database where datname like 'ia\_%' order by datname collate \"C\"")"
    [ "$atual" = $'ia_atendimento|ia_owner\nia_obs|ia_obs_a' ] && info "OK  2 bancos com os donos certos" || falhar "bancos diferem do esperado"
    ss -ltn | grep -q "127.0.0.1:${PG_PORTA} " && info "OK  escuta em 127.0.0.1:${PG_PORTA}" || falhar "não escuta em 127.0.0.1:${PG_PORTA}"
    if [ "$leitura" = sim ]; then ss -ltn | grep -q "${WG_IP_S5}:${PG_PORTA} " && info "OK  escuta em ${WG_IP_S5}:${PG_PORTA}" || falhar "não escuta no wg0 (o wg0 está de pé?)"; fi
    cat <<TXT

   Para a S2 ler (contrato 03), o DONO entrega à S2 por pipe (nada passa pela tela):
     $tls/ca.crt, $tls/ia_leitura_a.crt, $tls/ia_leitura_a.key e $SENHAS/ia_leitura_a.senha → /etc/ia-leitura-s5/ (grupo 70, 0640)
TXT
  fi
}

diretorios
case "$BANCO_LOCAL" in s4) banco_na_s4 ;; s5) banco_na_s5 ;; esac
resumo_ok
