# Relatório de construção — Hub Fiscal 0.1.0

Data da consolidação: 2026-08-05.

## Entregue

- Monorepositório Docker-first.
- API FastAPI multi-tenant com bootstrap administrativo, autenticação, clientes, usuários, CNPJs, certificados, documentos, plugins, políticas, jobs, API clients, webhooks e auditoria.
- Frontend Vue 3/TypeScript responsivo baseado na prévia visual aprovada.
- PostgreSQL, RabbitMQ, Redis e MinIO.
- Workers Celery e processamento assíncrono.
- SDK e catálogo de plugins com roteamento configurável.
- Compose local, produção e CloudPanel com persistência física.
- Imagens-base versionadas e publicação GHCR.
- CI, segurança, backup, restauração e documentação.

## Validações executadas

- `pytest`: 3 testes aprovados.
- `compileall`: aprovado.
- YAML, JSON e TOML: aprovados.
- Scripts Bash: aprovados.
- Contrato de versão: 0.1.0 aprovado.

## Limites do ambiente de geração

O ambiente local não possui Docker e o proxy interno de npm/PyPI não disponibilizou todos os pacotes oficiais necessários para executar o build completo dos containers. Os workflows do GitHub Actions foram incluídos para realizar os builds em runners com acesso aos registros públicos.

As integrações fiscais externas são ativadas por plugins e exigem credenciais, certificados, contratos, schemas e endpoints válidos. Nenhum segredo real foi embutido no pacote.
