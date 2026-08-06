# Deploy Docker do Hub Fiscal

A versão `0.2.1` utiliza uma stack de produção canônica em `compose.production.yaml`. Os arquivos abaixo são cópias idênticas da mesma stack para facilitar a importação:

- `deploy/cloudpanel/compose.yaml`;
- `deploy/dockge/compose.yaml`;
- `deploy/portainer/compose.yaml`.

O CloudPanel não executa a stack. Ele faz somente o reverse proxy para a porta publicada pelo Docker, Dockge ou Portainer.

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

## Padrão de produção

```env
HUBFISCAL_BIND_HOST=127.0.0.1
HUBFISCAL_HTTP_PORT=58088
HUBFISCAL_DATA_ROOT=./hubfiscal-data
MINIO_REGION=sa-east-1
```

No CloudPanel, o reverse proxy deve apontar para:

```text
http://127.0.0.1:58088
```

## Instalação pela linha de comando

```bash
bash scripts/generate-env.sh deploy/dockge/.env.example .env
```

Ajuste obrigatoriamente:

```text
HUBFISCAL_DOMAIN
HUBFISCAL_CORS_ORIGINS
HUBFISCAL_BIND_HOST
HUBFISCAL_HTTP_PORT
HUBFISCAL_DATA_ROOT
GHCR_NAMESPACE
HUBFISCAL_IMAGE_TAG
```

Não coloque explicações na mesma linha de uma variável. Exemplo inválido:

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data sempre usar assim
```

Exemplo correto:

```env
# Sempre usar a pasta da própria stack
HUBFISCAL_DATA_ROOT=./hubfiscal-data
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

## Imagens no GHCR

```text
ghcr.io/wkarts/hubfiscal-api:0.2.1
ghcr.io/wkarts/hubfiscal-web:0.2.1
```

Quando os packages forem privados:

```bash
printf '%s' "$GHCR_TOKEN" |
  docker login ghcr.io --username wkarts --password-stdin
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

No Dockge, `./hubfiscal-data` é resolvido dentro da pasta da stack. A montagem inicial usa `/data` como destino absoluto dentro do container, evitando o erro `invalid mount path`.

Não remova esse diretório durante atualizações. Containers e imagens podem ser recriados sem apagar documentos e bancos.

## MinIO próprio

O MinIO é executado dentro da mesma stack e armazena os arquivos em:

```text
./hubfiscal-data/minio
```

Configuração:

```env
MINIO_USER=hubfiscal
MINIO_PASSWORD=senha-forte
MINIO_BUCKET=hubfiscal-documents
MINIO_REGION=sa-east-1
MINIO_PUBLIC_ENDPOINT=
```

`sa-east-1` é um identificador lógico compatível com S3; não significa que os dados sairão do seu servidor.

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
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-storage-init
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.production.yaml logs --tail=200 hubfiscal-web
```

Health check:

```bash
curl --fail http://127.0.0.1:58088/api/v1/health/live
```

## Portas públicas

A stack publica somente o frontend:

```text
HUBFISCAL_BIND_HOST:HUBFISCAL_HTTP_PORT
```

PostgreSQL, Redis, RabbitMQ e MinIO permanecem internos. Atrás do CloudPanel, use `127.0.0.1`. Sem proxy reverso, use `0.0.0.0` apenas com firewall adequado.
