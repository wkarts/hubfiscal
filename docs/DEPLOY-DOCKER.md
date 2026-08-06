# Deploy Docker do Hub Fiscal

A versão `0.2.1` utiliza uma stack de produção canônica em `compose.production.yaml`. Os arquivos abaixo são cópias idênticas da mesma stack para facilitar importação nos painéis:

- `deploy/cloudpanel/compose.yaml`;
- `deploy/dockge/compose.yaml`;
- `deploy/portainer/compose.yaml`.

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

`hubfiscal-migrate` é um serviço one-shot. Ele executa as migrations antes da API e evita migrations concorrentes em reinícios da stack.

## Requisitos

- Docker Engine 26 ou superior;
- Docker Compose v2;
- acesso ao `ghcr.io`;
- mínimo recomendado: 4 vCPU, 8 GB de RAM e 40 GB livres;
- diretório persistente com permissão de gravação.

## Instalação pela linha de comando

```bash
cp deploy/portainer/.env.example .env
bash scripts/generate-env.sh .env .env --keep-existing
```

Ajuste obrigatoriamente:

```text
HUBFISCAL_BIND_HOST
HUBFISCAL_HTTP_PORT
HUBFISCAL_CORS_ORIGINS
HUBFISCAL_DATA_ROOT
GHCR_NAMESPACE
HUBFISCAL_IMAGE_TAG
```

Valide:

```bash
bash deploy/docker-doctor.sh compose.production.yaml .env
```

Para validar também o acesso às imagens:

```bash
HUBFISCAL_DOCTOR_PULL=true \
  bash deploy/docker-doctor.sh compose.production.yaml .env
```

Inicie:

```bash
bash deploy/start.sh compose.production.yaml .env
```

## Imagens privadas no GHCR

Quando os packages forem privados:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u wkarts --password-stdin
```

O token precisa do escopo `read:packages`.

## Persistência

A variável `HUBFISCAL_DATA_ROOT` contém:

```text
postgres/
redis/
rabbitmq/
minio/
celery/
backups/
```

Não remova esse diretório durante atualizações. Containers e imagens podem ser recriados sem apagar os documentos e bancos.

## Atualização

Altere somente:

```text
HUBFISCAL_IMAGE_TAG=X.Y.Z
```

Depois execute:

```bash
docker compose --env-file .env -f compose.production.yaml pull
docker compose --env-file .env -f compose.production.yaml up -d --remove-orphans
```

## Diagnóstico

```bash
docker compose --env-file .env -f compose.production.yaml ps -a
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-web
```

Health check:

```bash
curl --fail http://127.0.0.1:8088/api/v1/health/live
```

## Portas públicas

A stack publica somente o frontend pela variável:

```text
HUBFISCAL_BIND_HOST:HUBFISCAL_HTTP_PORT
```

PostgreSQL, Redis, RabbitMQ e MinIO permanecem internos. Em CloudPanel, use `127.0.0.1`; em Dockge ou Portainer sem proxy, use `0.0.0.0` com firewall adequado.
