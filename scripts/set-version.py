#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


def parse_version(value: str) -> tuple[int, int, int, str | None]:
    match = SEMVER.fullmatch(value.strip())
    if match is None:
        raise SystemExit(f"Versão SemVer inválida: {value}")
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        match.group(4),
    )


def next_version(current: str, bump: str, prerelease: str | None) -> str:
    major, minor, patch, _ = parse_version(current)
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    elif bump == "patch":
        patch += 1
    value = f"{major}.{minor}.{patch}"
    return f"{value}-{prerelease}" if prerelease else value


def replace_project_version(path: Path, version: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^version\s*=\s*"[^"]+"\s*$',
        f'version = "{version}"',
        content,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Não foi possível atualizar a versão em {path}")
    path.write_text(updated, encoding="utf-8")


def update_frontend_example(version: str) -> None:
    path = ROOT / ".env.example"
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^VITE_APP_VERSION=.*$",
        f"VITE_APP_VERSION={version}",
        content,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"VITE_APP_VERSION ausente em {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza a versão do Hub Fiscal"
    )
    parser.add_argument("version", nargs="?", help="Versão SemVer explícita")
    parser.add_argument("--bump", choices=("major", "minor", "patch"))
    parser.add_argument(
        "--prerelease",
        help="Sufixo de pré-release, por exemplo rc.1",
    )
    args = parser.parse_args()

    current = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if args.version and args.bump:
        raise SystemExit("Use uma versão explícita ou --bump, não ambos")
    version = args.version or next_version(
        current,
        args.bump or "patch",
        args.prerelease,
    )
    parse_version(version)

    (ROOT / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    replace_project_version(ROOT / "apps/api/pyproject.toml", version)
    (ROOT / "apps/api/src/hubfiscal/__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )

    package_path = ROOT / "apps/web/package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = version
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    update_frontend_example(version)

    # APP_IMAGE_TAG é deliberadamente independente de VERSION. O padrão de
    # implantação permanece `latest`; tags SemVer continuam disponíveis para
    # auditoria, homologação e rollback.
    print(version)


if __name__ == "__main__":
    main()
