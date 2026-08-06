# Hub Fiscal

Plataforma SaaS fiscal multiempresa, Docker-first, orientada a plugins para captura, armazenamento, consulta e distribuição de documentos fiscais eletrônicos.

**Versão atual:** `0.2.2`

## Stack

- **API:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic e PostgreSQL.
- **Frontend:** Vue 3, TypeScript, Vite e ECharts.
- **Processamento:** Celery, RabbitMQ e Redis.
- **Documentos:** S3/MinIO com hash SHA-256 e metadados no PostgreSQL.
- **Infraestrutura:** Docker Compose, GHCR, CloudPanel, Dockge, Portainer e GitHub Actions.

## Recursos implementados

- Bootstrap seguro do primeiro administrador da plataforma.
- SaaS multi-tenant com clientes, usuários, perfis e escopos por CNPJ.
- Cadastro de CNPJs, filiais, inscrições estaduais e municipais.
- Cofre de certificados A1 com criptografia e armazenamento privado.
- Cofre fiscal para NF-e, NFC-e, CT-e, MDF-e e NFS-e.
- Importação de XML e ZIP, deduplicação e validação estrutural.
- SDK e catálogo de plugins com políticas de roteamento por tenant, CNPJ e documento.
- Jobs assíncronos, retentativas, auditoria, API clients e webhooks.
- Compose de desenvolvimento e stack canônica de produção.
- Pacotes prontos para CloudPanel, Dockge e Portainer.
- Persistência física fora dos containers.
- Migration one-shot antes da API.
- Versionamento SemVer centralizado.
- GitHub Release com artefatos, checksums, SBOM e imagens multi-arquitetura.

## Desenvolvimento local

```bash
bash scripts/generate-env.sh
docker compose --env-file .env -f compose.yaml up -d --build
```

Acesse:

- Interface: `http://localhost:3000`;
- API: `http://localhost:8080`;
- Swagger: `http://localhost:8080/docs`;
- RabbitMQ: `http://localhost:15672`;
- MinIO: `http://localhost:9001`.

Na primeira execução, abra **Criar administrador inicial** e informe o `HUBFISCAL_BOOTSTRAP_TOKEN` exibido pelo gerador.

## Produção Docker

Escolha o template adequado:

```text
deploy/cloudpanel/
deploy/dockge/
deploy/portainer/
```

O padrão operacional segue o mesmo contrato usado no Auditor Fiscal:

```env
COMPOSE_PROJECT_NAME=hubfiscal-wwsoftwares
INSTANCE_NAME=wwsoftwares
RESOURCE_PREFIX=hubfiscal-wwsoftwares

IMAGE_REGISTRY=ghcr.io
IMAGE_NAMESPACE=wkarts
APP_IMAGE_TAG=latest

WEB_BIND_HOST=127.0.0.1
WEB_PUBLISHED_PORT=58088
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

`latest` acompanha a última release **estável** publicada. Tags exatas `X.Y.Z` continuam sendo produzidas para auditoria, homologação e rollback.

O Compose usa `pull_policy: always` nas imagens API e Web. Ao atualizar a stack no Dockge ou Portainer, a referência `latest` é consultada novamente no GHCR.

### CloudPanel

O CloudPanel atua somente como reverse proxy HTTPS. Aponte o domínio para:

```text
http://127.0.0.1:58088
```

Não existe workflow SSH conectando ao seu servidor.

### Inicialização

```bash
bash scripts/generate-env.sh deploy/dockge/.env.example .env
bash deploy/docker-doctor.sh deploy/dockge/compose.yaml .env
bash deploy/start.sh deploy/dockge/compose.yaml .env
```

A aplicação constrói internamente as URLs do PostgreSQL, Redis e RabbitMQ. As senhas podem conter caracteres especiais sem quebrar os endereços de conexão.

O MinIO é executado na mesma stack e grava em `./hubfiscal-data/minio`.

Documentação: [`docs/DEPLOY-DOCKER.md`](docs/DEPLOY-DOCKER.md).

## Versionamento

```bash
cat VERSION
bash scripts/check-version.sh
python3 scripts/set-version.py --bump patch
```

`VERSION` sincroniza API, frontend e metadados de release. Ele **não altera** `APP_IMAGE_TAG=latest`.

## Release automática

```text
Actions → Preparar release → Run workflow
```

Após o merge da PR de versão, o workflow **Release** publica:

- tag `vX.Y.Z`;
- GitHub Release;
- source ZIP e TAR.GZ;
- pacotes CloudPanel, Dockge e Portainer;
- `release-manifest.json` e `SHA256SUMS`;
- imagens API e Web para `linux/amd64` e `linux/arm64`;
- tags exatas `X.Y.Z` e alias `latest` para releases estáveis;
- proveniência e SBOM.

O GitHub não acessa o servidor. A atualização da stack é executada pelo operador no Docker, Dockge ou Portainer.

Consulte [`docs/RELEASE.md`](docs/RELEASE.md) e [`docs/DEPLOY-CLOUDPANEL.md`](docs/DEPLOY-CLOUDPANEL.md).

## Plugins fiscais externos

O núcleo não depende de uma fonte fixa. Integrações reais exigem credenciais, certificados, contratos e endpoints do cliente. Elas são configuradas como instalações de plugin sem armazenar segredos no código-fonte.

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/PLUGINS.md`](docs/PLUGINS.md)
- [`docs/EXTERNAL-INTEGRATIONS.md`](docs/EXTERNAL-INTEGRATIONS.md)
- [`docs/RELEASE.md`](docs/RELEASE.md)
- [`docs/DEPLOY-DOCKER.md`](docs/DEPLOY-DOCKER.md)
- [`docs/DEPLOY-CLOUDPANEL.md`](docs/DEPLOY-CLOUDPANEL.md)
- [`docs/VALIDATION.md`](docs/VALIDATION.md)
