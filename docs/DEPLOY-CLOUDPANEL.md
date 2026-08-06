# Docker com reverse proxy do CloudPanel

O CloudPanel não executa nem administra a stack do Hub Fiscal. Ele atua somente como **reverse proxy HTTPS** para a porta publicada pelo Docker, Dockge ou Portainer.

```text
Internet / HTTPS
        ↓
CloudPanel / Nginx
        ↓ reverse proxy
http://127.0.0.1:58088
        ↓
hubfiscal-web
        ↓
API e serviços internos da stack Docker
```

O GitHub publica imagens e pacotes de release. Não existe workflow SSH conectando ao servidor.

## Contrato recomendado

```env
COMPOSE_PROJECT_NAME=hubfiscal-wwsoftwares
INSTANCE_NAME=wwsoftwares
RESOURCE_PREFIX=hubfiscal-wwsoftwares

APP_NAME="Hub Fiscal - WWSoftware's"
APP_TIMEZONE=America/Bahia
HUBFISCAL_DOMAIN=hubfiscal.wwsoftwares.com.br
HUBFISCAL_CORS_ORIGINS=https://hubfiscal.wwsoftwares.com.br

IMAGE_REGISTRY=ghcr.io
IMAGE_NAMESPACE=wkarts
APP_IMAGE_TAG=latest

WEB_BIND_HOST=127.0.0.1
WEB_PUBLISHED_PORT=58088
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

No CloudPanel, aponte o domínio para:

```text
http://127.0.0.1:58088
```

Somente o frontend Nginx é publicado no host. PostgreSQL, Redis, RabbitMQ e MinIO permanecem na rede interna da stack.

## Imagens latest

A implantação normal utiliza:

```text
ghcr.io/wkarts/hubfiscal-api:latest
ghcr.io/wkarts/hubfiscal-web:latest
```

O Compose aplica `pull_policy: always`. Para rollback, substitua temporariamente:

```env
APP_IMAGE_TAG=0.2.2
```

Depois da correção, retorne a `latest`.

## Persistência no Dockge

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

Não coloque observações na mesma linha. Isto é inválido:

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data sempre usar assim
```

A forma correta é:

```env
# Sempre usar a pasta da própria stack
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

A estrutura física será:

```text
./hubfiscal-data/postgres
./hubfiscal-data/redis
./hubfiscal-data/rabbitmq
./hubfiscal-data/minio
./hubfiscal-data/celery
./hubfiscal-data/backups
```

## MinIO próprio

O MinIO já faz parte da mesma stack:

```env
MINIO_USER=hubfiscal
MINIO_PASSWORD=<senha-forte>
MINIO_BUCKET=hubfiscal-documents
MINIO_REGION=sa-east-1
MINIO_PUBLIC_ENDPOINT=
```

Os dados permanecem no servidor em `./hubfiscal-data/minio`. `sa-east-1` é apenas o identificador lógico compatível com S3.

## Instalação no Dockge

1. Crie a stack `hubfiscal-wwsoftwares`.
2. Use `deploy/dockge/compose.yaml`.
3. Copie `deploy/dockge/.env.example` para o `.env` da stack.
4. Gere segredos:

```bash
bash scripts/generate-env.sh \
  deploy/dockge/.env.example \
  /caminho/da/stack/.env
```

5. Valide:

```bash
bash deploy/docker-doctor.sh \
  deploy/dockge/compose.yaml \
  /caminho/da/stack/.env
```

6. Faça o deploy pelo Dockge.
7. Configure o reverse proxy no CloudPanel.

## Atualização

Com `APP_IMAGE_TAG=latest`:

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans --force-recreate
```

No Dockge, use **Update** ou **Deploy**. O serviço `hubfiscal-migrate` executará as migrations antes da API.

## Registry privado

```bash
printf '%s' "$GHCR_TOKEN" |
  docker login ghcr.io --username wkarts --password-stdin
```

O token precisa de `read:packages`.

## Diagnóstico

```bash
docker compose --env-file .env -f compose.yaml ps -a
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-storage-init
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-web
curl http://127.0.0.1:58088/api/v1/health/live
```

Não execute `docker compose down -v` em produção.
