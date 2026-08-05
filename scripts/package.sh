#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(tr -d '[:space:]' < VERSION)"
TAG="v${VERSION}"
SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
BUILT_AT="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
OUT_DIR="${1:-release-assets}"
PREFIX="hubfiscal-${VERSION}/"

./scripts/check-version.sh
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git archive --format=zip --prefix="$PREFIX" HEAD > "$OUT_DIR/hubfiscal-${VERSION}-source.zip"
  git archive --format=tar --prefix="$PREFIX" HEAD | gzip -n > "$OUT_DIR/hubfiscal-${VERSION}-source.tar.gz"
else
  zip -qr "$OUT_DIR/hubfiscal-${VERSION}-source.zip" . \
    -x '.git/*' '.env' 'local-data/*' 'node_modules/*' '*/node_modules/*' 'release-assets/*'
  tar --exclude='.git' --exclude='.env' --exclude='local-data' --exclude='node_modules' \
    --exclude='release-assets' -czf "$OUT_DIR/hubfiscal-${VERSION}-source.tar.gz" .
fi

CLOUDPANEL_STAGE="$(mktemp -d)"
trap 'rm -rf "$CLOUDPANEL_STAGE"' EXIT
mkdir -p "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}"
cp deploy/cloudpanel/compose.yaml "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}/compose.yaml"
cp deploy/cloudpanel/.env.example "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}/.env.example"
cp deploy/cloudpanel/deploy.sh "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}/deploy.sh"
cp deploy/cloudpanel/healthcheck.sh "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}/healthcheck.sh"
cp docs/DEPLOY-CLOUDPANEL.md "$CLOUDPANEL_STAGE/hubfiscal-cloudpanel-${VERSION}/README.md"
tar -C "$CLOUDPANEL_STAGE" -czf "$OUT_DIR/hubfiscal-${VERSION}-cloudpanel.tar.gz" "hubfiscal-cloudpanel-${VERSION}"

python3 - "$OUT_DIR" "$VERSION" "$TAG" "$SHA" "$BUILT_AT" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
version, tag, sha, built_at = sys.argv[2:]
artifacts = []
for path in sorted(out.iterdir()):
    if not path.is_file():
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifacts.append({"name": path.name, "sha256": digest, "size": path.stat().st_size})
manifest = {
    "product": "Hub Fiscal",
    "version": version,
    "tag": tag,
    "commit": sha,
    "built_at": built_at,
    "artifacts": artifacts,
    "images": [
        f"ghcr.io/wkarts/hubfiscal-api:{version}",
        f"ghcr.io/wkarts/hubfiscal-web:{version}",
    ],
}
(out / "release-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

(
  cd "$OUT_DIR"
  sha256sum hubfiscal-* release-manifest.json > SHA256SUMS
)

printf 'Artefatos da versão %s gerados em %s\n' "$VERSION" "$OUT_DIR"
