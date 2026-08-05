#!/usr/bin/env bash
set -euo pipefail
VERSION="$(cat VERSION)"
OUT="hubfiscal-${VERSION}.zip"
rm -f "$OUT"
zip -qr "$OUT" . -x '.git/*' '.env' 'local-data/*' 'node_modules/*' '*/node_modules/*' '*.zip'
echo "$OUT"
