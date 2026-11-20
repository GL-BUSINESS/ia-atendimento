#!/usr/bin/env bash
# Corta a versão: confere tudo, roda o portão e cria a TAG ANOTADA vX.Y.Z. NÃO faz push: imprime os comandos (o push da tag é
# o que dispara .github/workflows/imagem.yml, então é decisão consciente; o release no GitHub é feito depois com `gh`).
# Memória versionar-sempre-github: tag semver + release + CHANGELOG. Deploy por tag (PD-3): docs/DEPLOY.md.
#
# Uso:  bash scripts/release.sh X.Y.Z          (sem o `v`; a tag sai vX.Y.Z)
# Env:  CHECK_CMD   portão a rodar (padrão: bash scripts/check.sh; os testes do script trocam por `true`/`false`)
set -euo pipefail
cd "$(dirname "$0")/.."

erro() { echo "release: $*" >&2; exit 1; }

versao="${1:-}"
[[ "$versao" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "uso: bash scripts/release.sh X.Y.Z   (ex.: 0.2.0, sem o v)" >&2; exit 2; }
tag="v${versao}"

[ -f CHANGELOG.md ] || erro "CHANGELOG.md não existe"
grep -q "^## \[${versao//./\\.}\]" CHANGELOG.md || erro "CHANGELOG.md não tem a seção '## [${versao}]' (mova o [Unreleased] para a versão antes de cortar)"

no_pyproject="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -1)"
[ "$no_pyproject" = "$versao" ] || erro "pyproject.toml está em '${no_pyproject}', não em '${versao}' (a versão tem fonte única no pyproject; o imagem.yml confere)"

git rev-parse -q --verify "refs/tags/${tag}" >/dev/null && erro "a tag ${tag} já existe"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || erro "corte a release a partir da main (o imagem.yml só constrói tag que está na main)"
[ -z "$(git status --porcelain)" ] || erro "árvore suja: commite ou descarte antes"
if git rev-parse -q --verify refs/remotes/origin/main >/dev/null; then
  [ "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/main)" ] \
    || erro "HEAD difere de origin/main (rode 'git fetch origin' e atualize; a tag precisa estar na main do GitHub)"
fi

echo "== portão: ${CHECK_CMD:-bash scripts/check.sh}"
bash -c "${CHECK_CMD:-bash scripts/check.sh}" || erro "o portão reprovou; nenhuma tag foi criada"

git tag -a "${tag}" -m "ia-atendimento ${tag}"
echo "== tag anotada ${tag} criada em $(git rev-parse --short HEAD) (local; nada foi enviado)"
cat <<TXT

Próximos passos (só depois da revisão; o push da tag dispara a imagem):
  git push origin ${tag}
  gh release create ${tag} --verify-tag --notes-from-tag --title "ia-atendimento ${tag}"
Deploy na VPS é manual, na janela: bash scripts/deploy-vps.sh ${tag} --executar   (docs/DEPLOY.md)
Desfazer antes do push: git tag -d ${tag}
TXT
