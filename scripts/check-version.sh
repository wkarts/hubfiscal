#!/usr/bin/env bash
set -euo pipefail
VERSION="$(tr -d '[:space:]' < VERSION)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]] || {
  echo "VERSION inválida: $VERSION" >&2
  exit 1
}
echo "Contrato de versão $VERSION aprovado."
