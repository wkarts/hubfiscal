# Hub Fiscal

Plataforma SaaS fiscal multiempresa, Docker-first, orientada a plugins para captura, armazenamento, consulta e distribuição de documentos fiscais eletrônicos.

## Stack

- **API:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic e PostgreSQL.
- **Frontend:** Vue 3, TypeScript, Vite e ECharts.
- **Processamento:** Celery, RabbitMQ e Redis.
- **Documentos:** S3/MinIO com hash SHA-256 e metadados no PostgreSQL.
- **Infraestrutura:** Docker Compose, imagens-base versionadas no GHCR, CloudPanel/Dockge e CI/CD GitHub Actions.

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
- Dashboard responsivo baseado na identidade visual do mockup aprovado.
- Compose para desenvolvimento, produção e CloudPanel com persistência física.
- Workflows para CI, imagens-base, publicação de imagens e segurança.

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

## Plugins fiscais externos

O núcleo não depende de uma fonte fixa. Integrações reais exigem credenciais, certificados, contratos e endpoints do cliente. Elas são configuradas como instalações de plugin sem armazenar segredos no código-fonte.

Consulte `docs/ARCHITECTURE.md`, `docs/PLUGINS.md`, `docs/EXTERNAL-INTEGRATIONS.md`, `docs/DEPLOY-CLOUDPANEL.md` e `docs/VALIDATION.md`.
