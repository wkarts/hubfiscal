# Deploy GitHub Actions + CloudPanel

O Hub Fiscal usa:

- `.github/workflows/deploy-cloudpanel.yml`;
- GitHub Environment `cloudpanel-production`;
- `deploy/cloudpanel/compose.yaml`;
- `deploy/cloudpanel/deploy.sh`;
- `deploy/cloudpanel/healthcheck.sh`.

## Comportamento seguro

Uma release **não tenta implantar automaticamente** enquanto a Variable de repositório abaixo não estiver ativa:

```text
CLOUDPANEL_DEPLOY_ENABLED=true
```

Quando ausente ou `false`, o workflow termina com sucesso e registra **Deploy CloudPanel ignorado**. Isso permite publicar GitHub Releases e imagens sem possuir um servidor CloudPanel configurado.

## Pré-requisitos no servidor

```bash
docker version
docker compose version
docker ps
curl --version
python3 --version
```

O usuário SSH de deploy precisa executar Docker sem senha interativa de `sudo`.

## 1. Variable de ativação no repositório

Em:

```text
Settings → Secrets and variables → Actions → Variables
```

Cadastre somente quando o servidor estiver pronto:

```text
CLOUDPANEL_DEPLOY_ENABLED=true
```

## 2. GitHub Environment

Crie:

```text
Settings → Environments → New environment
cloudpanel-production
```

As demais Variables e Secrets devem ficar nesse Environment. É possível exigir aprovação humana em **Required reviewers**.

## 3. Variables do Environment

| Variable | Exemplo | Obrigatória |
|---|---|---:|
| `CLOUDPANEL_HOST` | `203.0.113.10` | Sim |
| `CLOUDPANEL_SSH_PORT` | `22` | Não |
| `CLOUDPANEL_SSH_USER` | `hubfiscal` | Sim |
| `CLOUDPANEL_DEPLOY_PATH` | `/home/cloudpanel/htdocs/hubfiscal` | Não |
| `CLOUDPANEL_DATA_ROOT` | `/home/cloudpanel/htdocs/hubfiscal-data` | Não |
| `HUBFISCAL_DOMAIN` | `fiscal.exemplo.com.br` | Sim |
| `HUBFISCAL_HTTP_PORT` | `8088` | Não |
| `GHCR_NAMESPACE` | `wkarts` | Não |
| `POSTGRES_DB` | `hubfiscal` | Não |
| `POSTGRES_USER` | `hubfiscal` | Não |
| `RABBITMQ_USER` | `hubfiscal` | Não |
| `RABBITMQ_VHOST` | `/` | Não |
| `MINIO_USER` | `hubfiscal` | Não |
| `MINIO_BUCKET` | `hubfiscal-documents` | Não |
| `HUBFISCAL_LOG_LEVEL` | `INFO` | Não |
| `HUBFISCAL_ACCESS_TOKEN_MINUTES` | `60` | Não |
| `HUBFISCAL_REFRESH_TOKEN_DAYS` | `30` | Não |

## 4. Secrets do Environment

| Secret | Finalidade |
|---|---|
| `CLOUDPANEL_SSH_PRIVATE_KEY` | Chave privada SSH de deploy |
| `HUBFISCAL_SECRET_KEY` | Assinatura de tokens; ao menos 32 caracteres |
| `HUBFISCAL_ENCRYPTION_KEY` | Chave Fernet válida |
| `HUBFISCAL_BOOTSTRAP_TOKEN` | Criação do administrador inicial |
| `POSTGRES_PASSWORD` | PostgreSQL |
| `RABBITMQ_PASSWORD` | RabbitMQ |
| `MINIO_PASSWORD` | MinIO |
| `GHCR_TOKEN` | Opcional para packages privados; escopo `read:packages` |
| `GHCR_USERNAME` | Opcional; proprietário do PAT |

Geração sugerida:

```bash
openssl rand -hex 64
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
openssl rand -hex 32
```

## 5. Chave SSH

```bash
ssh-keygen -t ed25519 -C "hubfiscal-github-actions" -f hubfiscal-deploy
```

Adicione `hubfiscal-deploy.pub` em `~/.ssh/authorized_keys` do usuário do servidor. Cadastre a chave privada em `CLOUDPANEL_SSH_PRIVATE_KEY`.

## 6. Proxy reverso

Crie o site no CloudPanel e encaminhe para:

```text
http://127.0.0.1:8088
```

A porta deve coincidir com `HUBFISCAL_HTTP_PORT`. O Nginx do container web encaminha `/api`, `/docs` e `/openapi.json` para a API interna.

## 7. Persistência

```text
/home/cloudpanel/htdocs/hubfiscal-data/
├── postgres/
├── redis/
├── rabbitmq/
├── minio/
├── celery/
└── backups/
```

Não use `docker compose down -v` em produção.

## 8. Deploy

Fluxo automático:

```text
Release concluída
    ↓
CLOUDPANEL_DEPLOY_ENABLED=true?
    ├── não → workflow aprovado e ignorado
    └── sim → preflight → SSH → backup → pull → migrate → up → health
```

Execução manual:

```text
Actions → Deploy CloudPanel → Run workflow
```

O campo `image_tag` aceita uma tag já publicada, por exemplo `0.2.1`.

## 9. Rollback

O script:

1. valida o novo `.env` e o Compose;
2. gera backup preventivo do PostgreSQL, quando a versão anterior está ativa;
3. preserva `.env.previous`;
4. baixa todas as imagens;
5. executa `hubfiscal-migrate` como tarefa one-shot;
6. inicia API, worker, beat e web;
7. verifica os quatro serviços e o endpoint público interno;
8. restaura `.env.previous` e os containers anteriores se qualquer etapa falhar.

O banco não é restaurado automaticamente para evitar perda de dados posteriores ao backup.

## 10. Instalação manual no servidor

```bash
mkdir -p /home/cloudpanel/htdocs/hubfiscal
cd /home/cloudpanel/htdocs/hubfiscal
cp deploy/cloudpanel/.env.example .env
bash scripts/generate-env.sh deploy/cloudpanel/.env.example .env
bash deploy/docker-doctor.sh deploy/cloudpanel/compose.yaml .env
bash deploy/start.sh deploy/cloudpanel/compose.yaml .env
```

Quando os arquivos forem copiados para o diretório de deploy, use `compose.yaml`, `.env`, `deploy.sh` e `healthcheck.sh` diretamente.

## 11. Diagnóstico

```bash
cd /home/cloudpanel/htdocs/hubfiscal
bash ./healthcheck.sh
docker compose --env-file .env -f compose.yaml ps -a
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-migrate
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-web
```

Erros comuns:

- `Variable/Secret obrigatório ausente`: o Environment não foi configurado;
- `denied` no GHCR: package privado sem `GHCR_TOKEN` válido;
- `502 Bad Gateway`: proxy ou `HUBFISCAL_HTTP_PORT` incorreto;
- `permission denied` no diretório de dados: ajuste proprietário/permissões de `CLOUDPANEL_DATA_ROOT`;
- migration falhou: consulte os logs de `hubfiscal-migrate`;
- health público falhou: revise DNS, certificado TLS e proxy.
