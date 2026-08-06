# Versionamento e Release

O Hub Fiscal usa SemVer com uma fonte central de versão no arquivo `VERSION`.

A mesma versão é obrigatoriamente sincronizada em:

- `VERSION`;
- `apps/api/pyproject.toml`;
- `apps/api/src/hubfiscal/__init__.py`;
- `apps/web/package.json`;
- `.env.example`;
- `deploy/cloudpanel/.env.example`;
- `deploy/dockge/.env.example`;
- `deploy/portainer/.env.example`.

## Preparar uma versão

No GitHub:

```text
Actions → Preparar release → Run workflow
```

Escolha `patch`, `minor` ou `major`. O workflow:

1. calcula a próxima versão;
2. sincroniza todos os arquivos;
3. valida backend, frontend e todos os Compose;
4. impede colisão de tag;
5. cria `release/vX.Y.Z`;
6. abre uma Pull Request de release.

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
- constrói o frontend com dependências compatíveis fixadas;
- valida as stacks Docker, CloudPanel, Dockge e Portainer;
- publica imagens-base;
- publica API e Web para `linux/amd64` e `linux/arm64`;
- gera proveniência e SBOM;
- cria source ZIP e TAR.GZ;
- cria pacotes CloudPanel, Dockge e Portainer;
- gera `release-manifest.json` e `SHA256SUMS`;
- cria a tag anotada `vX.Y.Z`;
- publica a GitHub Release.

## Tags de imagens

Para uma release estável `0.2.1`:

```text
ghcr.io/wkarts/hubfiscal-api:0.2.1
ghcr.io/wkarts/hubfiscal-api:0.2
ghcr.io/wkarts/hubfiscal-api:0
ghcr.io/wkarts/hubfiscal-api:latest

ghcr.io/wkarts/hubfiscal-web:0.2.1
ghcr.io/wkarts/hubfiscal-web:0.2
ghcr.io/wkarts/hubfiscal-web:0
ghcr.io/wkarts/hubfiscal-web:latest
```

Pré-releases recebem a versão exata e a tag por commit, sem substituir `latest`.

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

Validação:

```bash
sha256sum -c SHA256SUMS
```

## Dependências do frontend

O Vite e o plugin Vue são fixados em versões compatíveis. O Dependabot agrupa o toolchain e não abre atualizações major isoladas. Uma migração de major precisa atualizar e validar conjuntamente:

```text
vite
@vitejs/plugin-vue
vue-tsc
typescript
```

## Versão em execução

A versão aparece na interface e nos endpoints:

```text
GET /
GET /api/v1/health
GET /api/v1/health/live
```

Cada build informa versão SemVer, commit SHA, ref/tag e data UTC da construção.
