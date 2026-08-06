# Versionamento e Release

O Hub Fiscal usa SemVer com fonte central no arquivo `VERSION`.

A versão é sincronizada em:

- `VERSION`;
- `apps/api/pyproject.toml`;
- `apps/api/src/hubfiscal/__init__.py`;
- `apps/web/package.json`;
- `.env.example`, no campo `VITE_APP_VERSION`.

A tag de implantação é independente:

```env
APP_IMAGE_TAG=latest
```

O script `set-version.py` nunca substitui `latest` por uma versão numérica.

## Preparar uma versão

```text
Actions → Preparar release → Run workflow
```

Escolha `patch`, `minor` ou `major`. O workflow:

1. calcula a próxima versão;
2. sincroniza API, frontend e metadados;
3. mantém `APP_IMAGE_TAG=latest` nos ambientes de implantação;
4. valida backend, frontend e todos os Compose;
5. impede colisão de tag;
6. cria `release/vX.Y.Z`;
7. abre uma Pull Request de release.

Localmente:

```bash
python3 scripts/set-version.py --bump patch
python3 scripts/set-version.py 1.0.0
bash scripts/check-version.sh
```

## Publicação automática

Após o merge da PR de release em `main`, o workflow `Release`:

- valida o contrato de versão;
- executa Ruff, compileall e Pytest;
- constrói o frontend;
- valida Docker, CloudPanel, Dockge e Portainer;
- publica imagens-base;
- publica API e Web para `linux/amd64` e `linux/arm64`;
- gera proveniência e SBOM;
- cria source ZIP e TAR.GZ;
- cria pacotes CloudPanel, Dockge e Portainer;
- gera `release-manifest.json` e `SHA256SUMS`;
- cria a tag anotada `vX.Y.Z`;
- publica a GitHub Release.

## Tags de imagens

Para uma release estável `0.2.2`:

```text
ghcr.io/wkarts/hubfiscal-api:0.2.2
ghcr.io/wkarts/hubfiscal-api:0.2
ghcr.io/wkarts/hubfiscal-api:0
ghcr.io/wkarts/hubfiscal-api:latest

ghcr.io/wkarts/hubfiscal-web:0.2.2
ghcr.io/wkarts/hubfiscal-web:0.2
ghcr.io/wkarts/hubfiscal-web:0
ghcr.io/wkarts/hubfiscal-web:latest
```

A stack padrão sempre usa `latest`. Tags SemVer permanecem disponíveis para rollback e homologação reprodutível.

Pré-releases recebem a versão exata e a tag por commit, sem substituir `latest`, pois `latest` representa exclusivamente a release estável mais recente.

## Artefatos

```text
hubfiscal-X.Y.Z-source.zip
hubfiscal-X.Y.Z-source.tar.gz
hubfiscal-X.Y.Z-cloudpanel.tar.gz
hubfiscal-X.Y.Z-dockge.tar.gz
hubfiscal-X.Y.Z-portainer.tar.gz
release-manifest.json
SHA256SUMS
```

O manifesto registra:

```json
{
  "deployment_tag": "latest",
  "images": {
    "api": {
      "versioned": "ghcr.io/wkarts/hubfiscal-api:X.Y.Z",
      "deployment": "ghcr.io/wkarts/hubfiscal-api:latest"
    }
  }
}
```

Validação:

```bash
sha256sum -c SHA256SUMS
```

## Atualização da instalação

Com `APP_IMAGE_TAG=latest`:

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans --force-recreate
```

O Compose também declara `pull_policy: always` nas imagens da aplicação.

## Dependências do frontend

O Vite e o plugin Vue são fixados em versões compatíveis. O Dependabot agrupa o toolchain e não abre atualizações major isoladas.

## Versão em execução

A versão aparece na interface e nos endpoints:

```text
GET /
GET /api/v1/health
GET /api/v1/health/live
```

Cada imagem carrega versão SemVer, commit SHA, ref/tag e data UTC da construção. O Compose não sobrescreve esses valores com `unknown`.
