# Deploy Docker do Hub Fiscal

A stack de produção canônica está em `compose.production.yaml`. Os arquivos abaixo são cópias idênticas para facilitar a importação:

- `deploy/cloudpanel/compose.yaml`;
- `deploy/dockge/compose.yaml`;
- `deploy/portainer/compose.yaml`.

O CloudPanel não executa containers. Ele atua somente como reverse proxy HTTPS para a porta publicada pela stack Docker.

## Serviços

```text
hubfiscal-storage-init
hubfiscal-postgres
hubfiscal-redis
hubfiscal-rabbitmq
hubfiscal-minio
hubfiscal-minio-init
hubfiscal-migrate
hubfiscal-api
hubfiscal-worker
hubfiscal-beat
hubfiscal-web
```

`hubfiscal-migrate` é uma tarefa one-shot. Ela executa as migrations antes da API e evita concorrência entre API, worker e beat.

## Contrato de imagem

```env
IMAGE_REGISTRY=ghcr.io
IMAGE_NAMESPACE=wkarts
APP_IMAGE_TAG=latest
```

A implantação usa `latest` por padrão. Cada release estável publica simultaneamente:

```text
ghcr.io/wkarts/hubfiscal-api:X.Y.Z
ghcr.io/wkarts/hubfiscal-api:latest
ghcr.io/wkarts/hubfiscal-web:X.Y.Z
ghcr.io/wkarts/hubfiscal-web:latest
```

O Compose possui `pull_policy: always` para API, migrate, worker, beat e Web. Assim, `docker compose up` ou a atualização da stack no Dockge/Portainer consulta novamente a imagem `latest`.

Para rollback, altere temporariamente:

```env
APP_IMAGE_TAG=0.2.2
```

Depois de estabilizar, retorne para:

```env
APP_IMAGE_TAG=latest
```

## Identidade da instalação

Cada instalação precisa de nomes exclusivos:

```env
COMPOSE_PROJECT_NAME=hubfiscal-wwsoftwares
INSTANCE_NAME=wwsoftwares
RESOURCE_PREFIX=hubfiscal-wwsoftwares
```

Isso evita colisões entre redes, containers e projetos Compose quando houver mais de uma stack no mesmo servidor.

## Porta e reverse proxy

```env
WEB_BIND_HOST=127.0.0.1
WEB_PUBLISHED_PORT=58088
```

No CloudPanel, configure:

```text
http://127.0.0.1:58088
```

Use `0.0.0.0` apenas quando o proxy estiver em outro host e a porta estiver protegida por firewall.

## Persistência

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

A estrutura física será:

```text
hubfiscal-data/
├── postgres/
├── redis/
├── rabbitmq/
├── minio/
├── celery/
└── backups/
```

O diretório relativo é resolvido a partir da pasta da stack. Não coloque comentários na mesma linha do valor.

Correto:

```env
# Dados dentro da pasta da stack
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

Incorreto:

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data usar sempre assim
```

## MinIO próprio

O MinIO faz parte da mesma stack:

```env
MINIO_USER=hubfiscal
MINIO_PASSWORD=<senha-gerada>
MINIO_BUCKET=hubfiscal-documents
MINIO_REGION=sa-east-1
MINIO_PUBLIC_ENDPOINT=
```

`sa-east-1` é um identificador lógico compatível com S3. Os dados permanecem em `./hubfiscal-data/minio` no seu servidor.

As imagens auxiliares são fixadas por padrão:

```env
MINIO_IMAGE=minio/minio:RELEASE.2025-09-07T16-13-09Z
MINIO_MC_IMAGE=minio/mc:RELEASE.2025-08-13T08-35-41Z
```

## Instalação

```bash
cp deploy/dockge/.env.example .env
bash scripts/generate-env.sh .env .env --keep-existing
```

Revise:

```text
COMPOSE_PROJECT_NAME
INSTANCE_NAME
RESOURCE_PREFIX
APP_NAME
HUBFISCAL_DOMAIN
HUBFISCAL_CORS_ORIGINS
HUBFISCAL_DATA_ROOT
WEB_BIND_HOST
WEB_PUBLISHED_PORT
```

Valide:

```bash
bash deploy/docker-doctor.sh deploy/dockge/compose.yaml .env
```

Valide também o registry:

```bash
HUBFISCAL_DOCTOR_PULL=true \
  bash deploy/docker-doctor.sh deploy/dockge/compose.yaml .env
```

Inicie:

```bash
bash deploy/start.sh deploy/dockge/compose.yaml .env
```

## Atualização usando latest

```bash
docker compose --env-file .env -f deploy/dockge/compose.yaml pull
docker compose --env-file .env -f deploy/dockge/compose.yaml up -d --remove-orphans --force-recreate
```

No Dockge, use **Update** ou **Deploy**. No Portainer, use **Pull latest image** e depois atualize a stack.

## Registry privado

Quando os packages do GHCR forem privados:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u wkarts --password-stdin
```

O token precisa de `read:packages`.

## Diagnóstico

```bash
docker compose --env-file .env -f deploy/dockge/compose.yaml ps -a
docker compose --env-file .env -f deploy/dockge/compose.yaml logs --tail=200 hubfiscal-storage-init
docker compose --env-file .env -f deploy/dockge/compose.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f deploy/dockge/compose.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f deploy/dockge/compose.yaml logs --tail=200 hubfiscal-web
```

Health check:

```bash
curl --fail http://127.0.0.1:58088/api/v1/health/live
```

Não execute `docker compose down -v` em produção e não remova `HUBFISCAL_DATA_ROOT` durante atualizações.
