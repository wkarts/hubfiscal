# Hub Fiscal no Portainer

## Pré-requisitos

- endpoint Docker Standalone com Compose compatível;
- acesso do host ao GHCR;
- diretório persistente configurado em `HUBFISCAL_DATA_ROOT`;
- registry `ghcr.io` cadastrado quando as imagens forem privadas.

## Registry privado

Em **Registries → Add registry → Custom registry**:

```text
Registry URL: ghcr.io
Username: usuário GitHub
Password: PAT com read:packages
```

## Criação da stack

1. Abra **Stacks → Add stack**.
2. Use `hubfiscal-wwsoftwares`.
3. Cole `deploy/portainer/compose.yaml` ou selecione o repositório Git.
4. Cadastre as variáveis de `deploy/portainer/.env.example`.
5. Gere os segredos e remova todos os `change-me-*`.
6. Clique em **Deploy the stack**.

No método Git repository:

```text
Compose path: deploy/portainer/compose.yaml
```

## Contrato principal

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

Quando o Portainer não resolver caminhos relativos no método escolhido, use um caminho absoluto, por exemplo:

```env
HUBFISCAL_DATA_ROOT=/opt/hubfiscal-wwsoftwares/hubfiscal-data
```

## Reverse proxy CloudPanel

```text
http://127.0.0.1:58088
```

Sem proxy reverso, altere `WEB_BIND_HOST=0.0.0.0` e proteja a porta com firewall.

## Atualização

A implantação usa `APP_IMAGE_TAG=latest` e `pull_policy: always`.

No Portainer:

1. abra a stack;
2. marque **Pull latest image**;
3. use **Update the stack**.

Para rollback, fixe temporariamente uma versão:

```env
APP_IMAGE_TAG=0.2.2
```

Depois retorne para `latest`.

## Diagnóstico no host

```bash
bash deploy/docker-doctor.sh deploy/portainer/compose.yaml deploy/portainer/.env

docker compose \
  --env-file deploy/portainer/.env \
  -f deploy/portainer/compose.yaml \
  ps -a

curl http://127.0.0.1:58088/api/v1/health/live
```

Não execute `docker compose down -v` em produção.
