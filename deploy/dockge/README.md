# Hub Fiscal no Dockge

## Arquitetura

O Dockge administra a stack Docker. O CloudPanel apenas encaminha o domínio HTTPS para:

```text
http://127.0.0.1:58088
```

## Estrutura

```text
<diretório-da-stack>/
├── compose.yaml
├── .env
└── hubfiscal-data/
    ├── postgres/
    ├── redis/
    ├── rabbitmq/
    ├── minio/
    ├── celery/
    └── backups/
```

## Instalação

1. Crie a stack `hubfiscal-wwsoftwares`.
2. Use `deploy/dockge/compose.yaml`.
3. Copie `deploy/dockge/.env.example` para o `.env` da stack.
4. Gere os segredos:

```bash
bash scripts/generate-env.sh \
  deploy/dockge/.env.example \
  /caminho/da/stack/.env
```

5. Confirme o contrato:

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

Não coloque comentários depois do valor de `HUBFISCAL_DATA_ROOT`.

6. Para packages privados, autentique o host:

```bash
printf '%s' "$GHCR_TOKEN" |
  docker login ghcr.io --username wkarts --password-stdin
```

7. Valide:

```bash
bash deploy/docker-doctor.sh \
  /caminho/da/stack/compose.yaml \
  /caminho/da/stack/.env
```

8. Clique em **Deploy**.

## Atualização automática da referência latest

A stack usa `pull_policy: always`. No Dockge, execute **Update** ou **Deploy** para consultar novamente:

```text
ghcr.io/wkarts/hubfiscal-api:latest
ghcr.io/wkarts/hubfiscal-web:latest
```

Para rollback, altere temporariamente:

```env
APP_IMAGE_TAG=0.2.2
```

Depois retorne para `latest`.

## Reverse proxy

Configure `hubfiscal.wwsoftwares.com.br` no CloudPanel para:

```text
http://127.0.0.1:58088
```

Não exponha PostgreSQL, Redis, RabbitMQ ou MinIO.

## Validação

```bash
docker compose \
  --env-file /caminho/da/stack/.env \
  -f /caminho/da/stack/compose.yaml \
  ps -a

curl http://127.0.0.1:58088/api/v1/health/live
```

## Observações

- O MinIO é próprio e executa dentro da mesma stack.
- Os dados ficam em `./hubfiscal-data/minio`.
- Não use `docker compose down -v` em produção.
- Faça backup de `./hubfiscal-data`.
