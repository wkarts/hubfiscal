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

values = {
    "VERSION": version,
    "apps/api/pyproject.toml": api,
    "apps/web/package.json": web,
    "apps/api/src/hubfiscal/__init__.py": package_version,
}
for path, value in values.items():
    if value != version:
        raise SystemExit(
            f"Versão divergente em {path}: {value!r}; esperado {version!r}"
        )

env_paths = (
    root / ".env.example",
    root / "deploy/cloudpanel/.env.example",
    root / "deploy/dockge/.env.example",
    root / "deploy/portainer/.env.example",
)
for env_path in env_paths:
    content = env_path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^HUBFISCAL_IMAGE_TAG=(.+)$", content)
    if match is None or match.group(1).strip() != version:
        raise SystemExit(f"HUBFISCAL_IMAGE_TAG divergente em {env_path}")

print(
    f"Contrato de versão {version} aprovado em "
    f"{len(values) + len(env_paths)} arquivos."
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
