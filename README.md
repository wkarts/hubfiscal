# Hub Fiscal

Plataforma SaaS fiscal multiempresa, Docker-first, orientada a plugins para captura, armazenamento, consulta e distribuição de documentos fiscais eletrônicos.

**Versão atual:** `0.2.1`

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
- Deploy CloudPanel opcional com SSH, backup preventivo, health check e rollback.

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

Exemplo pela linha de comando:

```bash
bash scripts/generate-env.sh deploy/portainer/.env.example .env
bash deploy/docker-doctor.sh compose.production.yaml .env
bash deploy/start.sh compose.production.yaml .env
```

A aplicação constrói internamente as URLs do PostgreSQL, Redis e RabbitMQ. As senhas podem conter caracteres especiais sem quebrar os endereços de conexão.

Documentação: [`docs/DEPLOY-DOCKER.md`](docs/DEPLOY-DOCKER.md).

## Versionamento

```bash
cat VERSION
bash scripts/check-version.sh
python3 scripts/set-version.py --bump patch
```

A versão é sincronizada entre API, frontend e todos os ambientes de deploy.

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
- proveniência e SBOM.

Consulte [`docs/RELEASE.md`](docs/RELEASE.md).

## Deploy CloudPanel automático

O deploy não é ativado somente por existir uma release. Para habilitar, configure a Variable de repositório:

```text
CLOUDPANEL_DEPLOY_ENABLED=true
```

As credenciais ficam no Environment `cloudpanel-production`. Sem essa ativação, o workflow é ignorado com sucesso e não cria um deployment vermelho.

Consulte [`docs/DEPLOY-CLOUDPANEL.md`](docs/DEPLOY-CLOUDPANEL.md).

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
