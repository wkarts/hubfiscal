#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(tr -d '[:space:]' < VERSION)"
export VERSION

python3 - <<'PY'
from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path

root = Path.cwd()
version = os.environ["VERSION"]
semver = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
if semver.fullmatch(version) is None:
    raise SystemExit(f"VERSION inválida: {version}")

api = tomllib.loads(
    (root / "apps/api/pyproject.toml").read_text(encoding="utf-8")
)["project"]["version"]
web = json.loads(
    (root / "apps/web/package.json").read_text(encoding="utf-8")
)["version"]
init_content = (
    root / "apps/api/src/hubfiscal/__init__.py"
).read_text(encoding="utf-8")
match = re.search(r'__version__\s*=\s*"([^"]+)"', init_content)
package_version = match.group(1) if match else None

env_root = (root / ".env.example").read_text(encoding="utf-8")
match = re.search(r"(?m)^VITE_APP_VERSION=(.+)$", env_root)
vite_version = match.group(1).strip() if match else None

values = {
    "VERSION": version,
    "apps/api/pyproject.toml": api,
    "apps/web/package.json": web,
    "apps/api/src/hubfiscal/__init__.py": package_version,
    ".env.example:VITE_APP_VERSION": vite_version,
}
for path, value in values.items():
    if value != version:
        raise SystemExit(
            f"Versão divergente em {path}: {value!r}; esperado {version!r}"
        )

deploy_env_paths = (
    root / "deploy/cloudpanel/.env.example",
    root / "deploy/dockge/.env.example",
    root / "deploy/portainer/.env.example",
)
for env_path in deploy_env_paths:
    content = env_path.read_text(encoding="utf-8")
    tag = re.search(r"(?m)^APP_IMAGE_TAG=(.+)$", content)
    if tag is None or tag.group(1).strip() != "latest":
        raise SystemExit(f"APP_IMAGE_TAG deve permanecer latest em {env_path}")
    if re.search(r"(?m)^(HUBFISCAL_IMAGE_TAG|GHCR_REGISTRY|GHCR_NAMESPACE)=", content):
        raise SystemExit(f"Variáveis legadas de imagem encontradas em {env_path}")

compose_paths = (
    root / "compose.production.yaml",
    root / "deploy/cloudpanel/compose.yaml",
    root / "deploy/dockge/compose.yaml",
    root / "deploy/portainer/compose.yaml",
)
canonical = compose_paths[0].read_text(encoding="utf-8")
for compose_path in compose_paths:
    content = compose_path.read_text(encoding="utf-8")
    if content != canonical:
        raise SystemExit(f"Compose divergente da stack canônica: {compose_path}")
    if "${APP_IMAGE_TAG:-latest}" not in content:
        raise SystemExit(f"Fallback latest ausente em {compose_path}")
    if "pull_policy: always" not in content:
        raise SystemExit(f"pull_policy: always ausente em {compose_path}")

print(
    f"Contrato de versão {version} aprovado; deploy usa latest por padrão "
    f"em {len(deploy_env_paths)} ambientes e {len(compose_paths)} Compose."
)
PY

if [[ "$MODE" == "--release" ]]; then
  EXPECTED_TAG="v${VERSION}"
  ACTUAL_TAG="${RELEASE_TAG:-${GITHUB_REF_NAME:-}}"
  if [[ -z "$ACTUAL_TAG" ]]; then
    echo "RELEASE_TAG ou GITHUB_REF_NAME não informado para validação de release." >&2
    exit 1
  fi
  if [[ "$ACTUAL_TAG" != "$EXPECTED_TAG" ]]; then
    echo "Tag inválida: $ACTUAL_TAG; esperado $EXPECTED_TAG" >&2
    exit 1
  fi
  echo "Contrato de release $EXPECTED_TAG aprovado."
fi
