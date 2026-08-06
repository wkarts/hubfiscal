# Docker com reverse proxy do CloudPanel

O CloudPanel não executa nem administra a stack do Hub Fiscal. Ele atua somente como **reverse proxy HTTPS** para a porta publicada pelo Docker, Dockge ou Portainer.

Arquitetura:

```text
Internet / HTTPS
        ↓
CloudPanel / Nginx
        ↓ reverse proxy
http://127.0.0.1:58088
        ↓
container hubfiscal-web
        ↓
API e serviços internos da stack Docker
```

Não existe workflow SSH para acessar o servidor. O GitHub publica as imagens e os pacotes de release; a instalação e a atualização da stack são executadas pelo administrador no Docker, Dockge ou Portainer.

## Arquivos disponíveis

```text
compose.production.yaml

deploy/cloudpanel/
├── compose.yaml
├── .env.example
├── deploy.sh
└── healthcheck.sh

deploy/dockge/
├── compose.yaml
├── .env.example
└── README.md

deploy/portainer/
├── compose.yaml
├── .env.example
└── README.md
```

Os quatro Compose de produção são mantidos idênticos e validados na CI.

## Porta publicada

O padrão do Hub Fiscal em produção é:

```env
HUBFISCAL_BIND_HOST=127.0.0.1
HUBFISCAL_HTTP_PORT=58088
```

No CloudPanel, configure o reverse proxy para:

```text
http://127.0.0.1:58088
```

Somente a aplicação web é publicada no host. PostgreSQL, Redis, RabbitMQ e MinIO permanecem na rede interna do Docker.

## Persistência no Dockge

Quando a stack estiver na pasta do Dockge, use:

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

A stack monta o caminho do host em `/data` somente no container inicializador. Os demais bind mounts usam destinos internos absolutos:

```text
./hubfiscal-data/postgres  → /var/lib/postgresql/data
./hubfiscal-data/redis     → /data
./hubfiscal-data/rabbitmq  → /var/lib/rabbitmq
./hubfiscal-data/minio     → /data
./hubfiscal-data/celery    → /tmp/celery
```

## MinIO próprio

O MinIO já faz parte da mesma stack:

```text
hubfiscal-minio
hubfiscal-minio-init
```

Configuração recomendada:

```env
MINIO_USER=hubfiscal
MINIO_PASSWORD=senha-forte
MINIO_BUCKET=hubfiscal-documents
MINIO_REGION=sa-east-1
MINIO_PUBLIC_ENDPOINT=
```

`sa-east-1` é apenas o identificador lógico da região S3. Os dados continuam armazenados fisicamente no seu próprio servidor em:

```text
./hubfiscal-data/minio
```

Enquanto o MinIO não tiver um proxy S3 dedicado, mantenha `MINIO_PUBLIC_ENDPOINT` vazio. A aplicação acessa o MinIO internamente por `http://hubfiscal-minio:9000`.

## Instalação com Dockge

1. Crie a stack no Dockge.
2. Use `deploy/dockge/compose.yaml`.
3. Copie `deploy/dockge/.env.example` para o ambiente da stack.
4. Gere os segredos:

```bash
bash scripts/generate-env.sh deploy/dockge/.env.example /caminho/da/stack/.env
```

5. Ajuste domínio e confirme:

```env
HUBFISCAL_DOMAIN=hubfiscal.wwsoftwares.com.br
HUBFISCAL_CORS_ORIGINS=https://hubfiscal.wwsoftwares.com.br
HUBFISCAL_BIND_HOST=127.0.0.1
HUBFISCAL_HTTP_PORT=58088
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

6. Valide antes de clicar em Deploy:

```bash
bash deploy/docker-doctor.sh \
  deploy/dockge/compose.yaml \
  /caminho/da/stack/.env
```

7. Faça o deploy no Dockge.

## Instalação com Docker Compose

```bash
cp deploy/cloudpanel/.env.example .env
bash scripts/generate-env.sh deploy/cloudpanel/.env.example .env
bash deploy/docker-doctor.sh compose.production.yaml .env
bash deploy/start.sh compose.production.yaml .env
```

## Imagens do GitHub Container Registry

A stack utiliza:

```text
ghcr.io/wkarts/hubfiscal-api:0.2.1
ghcr.io/wkarts/hubfiscal-web:0.2.1
```

Para packages públicos, não é necessário login. Para packages privados:

```bash
printf '%s' "$GHCR_TOKEN" |
  docker login ghcr.io --username wkarts --password-stdin
```

## Diagnóstico

```bash
docker compose --env-file .env -f compose.yaml ps -a
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-storage-init
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-web
curl http://127.0.0.1:58088/api/v1/health/live
```

## Atualização

1. Altere `HUBFISCAL_IMAGE_TAG` para a versão publicada.
2. Execute `Pull`/`Update` no Dockge ou Portainer.
3. O serviço `hubfiscal-migrate` executará as migrations antes da API.
4. Não use `docker compose down -v`, pois os dados são persistentes.
