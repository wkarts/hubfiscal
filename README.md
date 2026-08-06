# Hub Fiscal

Plataforma SaaS fiscal multiempresa, Docker-first, orientada a plugins para captura, armazenamento, consulta e distribuição de documentos fiscais eletrônicos.

**Versão atual:** `0.2.0`

## Stack

- **API:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic e PostgreSQL.
- **Frontend:** Vue 3, TypeScript, Vite e ECharts.
- **Processamento:** Celery, RabbitMQ e Redis.
- **Documentos:** S3/MinIO com hash SHA-256 e metadados no PostgreSQL.
- **Infraestrutura:** Docker Compose, imagens-base versionadas no GHCR, CloudPanel/Dockge e GitHub Actions.

## Recursos implementados

- Bootstrap seguro do primeiro administrador da plataforma.
- SaaS multi-tenant com clientes, usuários, perfis e escopos por CNPJ.
- Cadastro de CNPJs, filiais, inscrições estaduais e municipais.
- Cofre de certificados A1 com criptografia e armazenamento privado.
- Cofre fiscal para NF-e, NFC-e, CT-e, MDF-e e NFS-e.
- Importação de XML e ZIP, deduplicação e validação estrutural.
- SDK e catálogo de plugins com políticas de roteamento por tenant/CNPJ/documento.
- Plugin de repositório, upload manual, fonte simulada, HTTP genérico e portal assistido.
- Jobs assíncronos, retentativas, auditoria e monitoramento.
- Clientes de API, escopos e webhooks.
- Dashboard responsivo com versão e commit de build visíveis.
- Compose para desenvolvimento, produção e CloudPanel com persistência física.
- Versionamento SemVer centralizado e sincronizado.
- GitHub Release automática com artefatos e checksums.
- Imagens API/Web `linux/amd64` e `linux/arm64` no GHCR.
- Deploy CloudPanel via SSH, GitHub Environment, backup preventivo e rollback.

## Inicialização rápida

```bash
cp .env.example .env
./scripts/generate-env.sh --keep-existing
docker compose up -d --build
```

Acesse:

- Interface: `http://localhost:3000`
- API: `http://localhost:8080`
- Swagger: `http://localhost:8080/docs`
- RabbitMQ: `http://localhost:15672`
- MinIO: `http://localhost:9001`

Na primeira execução, abra a tela **Criar administrador inicial** e informe o valor de `HUBFISCAL_BOOTSTRAP_TOKEN`.

## Versão e build

```bash
cat VERSION
./scripts/check-version.sh
curl http://localhost:8080/api/v1/health/live
```

A versão é sincronizada entre API, frontend, exemplos de ambiente e imagens Docker pelo script:

```bash
python3 scripts/set-version.py --bump patch
```

## Release automática

Use:

```text
Actions → Preparar release → Run workflow
```

O workflow cria uma PR de versão. Após o merge em `main`, o workflow **Release** publica:

- tag `vX.Y.Z`;
- GitHub Release;
- source ZIP e TAR.GZ;
- pacote de deploy CloudPanel;
- `release-manifest.json`;
- `SHA256SUMS`;
- imagens API e Web multi-arquitetura no GHCR;
- proveniência e SBOM das imagens.

Consulte [`docs/RELEASE.md`](docs/RELEASE.md).

## Deploy CloudPanel

O ambiente GitHub `cloudpanel-production` concentra Variables e Secrets. Depois da release, o workflow **Deploy CloudPanel**:

1. conecta ao servidor por SSH;
2. gera e transfere o `.env` de produção;
3. autentica o servidor no GHCR;
4. cria backup preventivo do PostgreSQL;
5. aplica `docker compose pull/up`;
6. executa health check;
7. restaura os containers anteriores em caso de falha.

Consulte [`docs/DEPLOY-CLOUDPANEL.md`](docs/DEPLOY-CLOUDPANEL.md) para a lista completa de Variables, Secrets, proxy reverso e persistência física.

## Plugins fiscais externos

O núcleo não depende de uma fonte fixa. Integrações reais exigem credenciais, certificados, contratos e endpoints do cliente. Elas são configuradas como instalações de plugin sem armazenar segredos no código-fonte.

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/PLUGINS.md`](docs/PLUGINS.md)
- [`docs/EXTERNAL-INTEGRATIONS.md`](docs/EXTERNAL-INTEGRATIONS.md)
- [`docs/RELEASE.md`](docs/RELEASE.md)
- [`docs/DEPLOY-CLOUDPANEL.md`](docs/DEPLOY-CLOUDPANEL.md)
- [`docs/VALIDATION.md`](docs/VALIDATION.md)
