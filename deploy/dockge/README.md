# Hub Fiscal no Dockge

## Arquitetura

O Dockge administra a stack Docker. O CloudPanel apenas encaminha o domínio HTTPS para:

```text
http://127.0.0.1:58088
```

## Estrutura da stack

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

1. Crie uma stack chamada `hubfiscal`.
2. Use o arquivo `deploy/dockge/compose.yaml`.
3. Copie `deploy/dockge/.env.example` para o `.env` da stack.
4. Gere os segredos:

```bash
bash scripts/generate-env.sh \
  deploy/dockge/.env.example \
  /caminho/da/stack/.env
```

5. Configure:

```env
HUBFISCAL_BIND_HOST=127.0.0.1
HUBFISCAL_HTTP_PORT=58088
HUBFISCAL_DOMAIN=hubfiscal.wwsoftwares.com.br
HUBFISCAL_CORS_ORIGINS=https://hubfiscal.wwsoftwares.com.br
HUBFISCAL_DATA_ROOT=./hubfiscal-data
MINIO_REGION=sa-east-1
MINIO_PUBLIC_ENDPOINT=
```

Não coloque comentários depois do valor de `HUBFISCAL_DATA_ROOT`.

Incorreto:

```env
HUBFISCAL_DATA_ROOT=./hubfiscal-data sempre usar assim
```

Correto:

```env
# Sempre usar a pasta da própria stack
HUBFISCAL_DATA_ROOT=./hubfiscal-data
```

6. Para packages privados, autentique o host no GHCR:

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

## Reverse proxy CloudPanel

Configure o site `hubfiscal.wwsoftwares.com.br` para encaminhar para:

```text
http://127.0.0.1:58088
```

Não exponha diretamente PostgreSQL, Redis, RabbitMQ ou MinIO.

## Validação

```bash
docker compose \
  --env-file /caminho/da/stack/.env \
  -f /caminho/da/stack/compose.yaml \
  ps -a

curl http://127.0.0.1:58088/api/v1/health/live
```

## Atualização

Altere `HUBFISCAL_IMAGE_TAG`, salve o `.env` e use **Update** ou **Deploy**. O serviço `hubfiscal-migrate` executará as migrations antes da API.

## Observações

- O MinIO é próprio e executa dentro da mesma stack.
- Os dados do MinIO ficam em `./hubfiscal-data/minio`.
- Não use `docker compose down -v` em produção.
- Faça backup de `./hubfiscal-data`.
