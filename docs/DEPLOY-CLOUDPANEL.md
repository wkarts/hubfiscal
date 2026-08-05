# Deploy GitHub Actions + CloudPanel

O deploy de produção usa o workflow `.github/workflows/deploy-cloudpanel.yml`, o ambiente GitHub `cloudpanel-production` e a stack `deploy/cloudpanel/compose.yaml`.

A publicação segue este fluxo:

```text
Merge da versão em main
        ↓
Workflow Release
        ↓
Tag + GitHub Release + imagens GHCR
        ↓
Workflow Deploy CloudPanel
        ↓
SSH + backup preventivo + docker compose pull/up
        ↓
Health check interno e público
        ↓
Rollback de containers se o health check falhar
```

## 1. Pré-requisitos no servidor

O servidor CloudPanel precisa possuir:

- Docker Engine e Docker Compose v2;
- usuário SSH com acesso ao Docker;
- acesso de saída ao `ghcr.io`;
- `curl`, `gzip` e cliente OpenSSH;
- site criado no CloudPanel para o domínio da plataforma.

Validação no servidor:

```bash
docker version
docker compose version
id
```

O usuário informado em `CLOUDPANEL_SSH_USER` deve executar `docker ps` sem `sudo` interativo.

## 2. GitHub Environment

No repositório, abra:

```text
Settings → Environments → New environment
```

Crie o ambiente:

```text
cloudpanel-production
```

Opcionalmente, configure aprovação obrigatória antes do deploy em **Required reviewers**.

## 3. GitHub Variables

Cadastre as seguintes Variables no ambiente `cloudpanel-production`:

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
| `MINIO_USER` | `hubfiscal` | Não |
| `MINIO_BUCKET` | `hubfiscal-documents` | Não |
| `HUBFISCAL_LOG_LEVEL` | `INFO` | Não |
| `HUBFISCAL_ACCESS_TOKEN_MINUTES` | `60` | Não |
| `HUBFISCAL_REFRESH_TOKEN_DAYS` | `30` | Não |

## 4. GitHub Secrets

Cadastre os seguintes Secrets no ambiente `cloudpanel-production`:

| Secret | Finalidade |
|---|---|
| `CLOUDPANEL_SSH_PRIVATE_KEY` | Chave privada do usuário SSH de deploy |
| `GHCR_TOKEN` | PAT com `read:packages` para o servidor baixar imagens privadas |
| `GHCR_USERNAME` | Usuário proprietário do PAT; opcional, usa o owner do repositório |
| `HUBFISCAL_SECRET_KEY` | Assinatura de tokens da aplicação, mínimo recomendado de 64 caracteres |
| `HUBFISCAL_ENCRYPTION_KEY` | Chave Fernet válida para criptografia de segredos |
| `HUBFISCAL_BOOTSTRAP_TOKEN` | Token para criação do primeiro administrador |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL |
| `RABBITMQ_PASSWORD` | Senha do RabbitMQ |
| `MINIO_PASSWORD` | Senha do MinIO |

Geração segura sugerida:

```bash
openssl rand -hex 64
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
openssl rand -hex 32
```

Não copie senhas para arquivos versionados. O workflow monta `.env.new` no runner, envia-o com permissão restrita e o servidor o renomeia para `.env`.

## 5. Chave SSH de deploy

Crie uma chave dedicada:

```bash
ssh-keygen -t ed25519 -C "hubfiscal-github-actions" -f hubfiscal-deploy
```

No servidor, adicione o conteúdo de `hubfiscal-deploy.pub` ao arquivo:

```text
~/.ssh/authorized_keys
```

Cadastre o conteúdo da chave privada `hubfiscal-deploy` no Secret `CLOUDPANEL_SSH_PRIVATE_KEY`.

## 6. CloudPanel e proxy reverso

Crie um site no CloudPanel para `HUBFISCAL_DOMAIN` e configure o proxy para:

```text
http://127.0.0.1:8088
```

O valor `8088` deve ser igual a `HUBFISCAL_HTTP_PORT`.

A aplicação web encaminha internamente:

```text
/api/*         → hubfiscal-api:8080
/docs          → hubfiscal-api:8080
/openapi.json  → hubfiscal-api:8080
```

PostgreSQL, Redis, RabbitMQ e MinIO não possuem portas públicas no Compose de produção.

## 7. Persistência física

Os dados ficam em `CLOUDPANEL_DATA_ROOT`:

```text
hubfiscal-data/
├── postgres/
├── redis/
├── rabbitmq/
├── minio/
├── celery/
└── backups/
```

O serviço `hubfiscal-storage-init` cria os diretórios no primeiro deploy. O diretório deve estar em disco persistente e incluído na estratégia de backup do servidor.

## 8. Deploy automático

Após uma release bem-sucedida, o workflow **Deploy CloudPanel** é iniciado automaticamente.

Também é possível executar manualmente:

```text
Actions → Deploy CloudPanel → Run workflow
```

O campo `image_tag` aceita uma versão já publicada, por exemplo:

```text
0.2.0
```

Quando vazio, o workflow usa o conteúdo de `VERSION` na branch `main`.

## 9. Segurança e rollback

Antes de substituir a versão, `deploy.sh`:

1. mantém uma cópia do `.env` anterior;
2. gera `pg_dump` compactado em `HUBFISCAL_DATA_ROOT/backups`;
3. valida o Compose;
4. baixa as imagens do GHCR;
5. aplica a stack;
6. executa o health check;
7. restaura os containers da versão anterior se a nova versão não ficar saudável.

O rollback automático restaura imagens e configuração. Restauração de banco é deliberadamente manual para evitar sobrescrever dados sem autorização.

## 10. Validação no servidor

```bash
cd /home/cloudpanel/htdocs/hubfiscal
cat .deployed-version
docker compose --env-file .env -f compose.yaml ps
./healthcheck.sh
```

A API também informa versão e build:

```bash
curl https://fiscal.exemplo.com.br/api/v1/health/live
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "hubfiscal-api",
  "build": {
    "version": "0.2.0",
    "sha": "commit-sha",
    "ref": "v0.2.0",
    "built_at": "2026-08-05T22:00:00Z"
  }
}
```

## 11. Diagnóstico

```bash
cd /home/cloudpanel/htdocs/hubfiscal
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-api
docker compose --env-file .env -f compose.yaml logs --tail=200 hubfiscal-web
```

Erros comuns:

- `denied` ao executar `docker pull`: revise `GHCR_TOKEN` e `GHCR_USERNAME`;
- falha SSH: revise host, porta, usuário, chave privada e `authorized_keys`;
- `502 Bad Gateway`: confirme `HUBFISCAL_HTTP_PORT` e o proxy do CloudPanel;
- banco não inicia: confira permissões e espaço em `CLOUDPANEL_DATA_ROOT`;
- health check público falha: valide DNS, certificado TLS e proxy reverso.
