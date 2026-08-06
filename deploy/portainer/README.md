# Hub Fiscal no Portainer

## Pré-requisitos

- endpoint Docker Standalone ou Swarm com Docker Compose compatível;
- acesso do host ao GHCR;
- diretório persistente configurado em `HUBFISCAL_DATA_ROOT`;
- registro `ghcr.io` cadastrado quando as imagens forem privadas.

## Registry privado

No Portainer, abra:

```text
Registries → Add registry → Custom registry
```

Configure:

```text
Registry URL: ghcr.io
Username: usuário GitHub
Password: PAT com read:packages
```

## Criação da stack

1. Abra **Stacks → Add stack**.
2. Use o nome `hubfiscal`.
3. Cole `compose.yaml` no editor ou selecione o repositório Git.
4. Cadastre as variáveis existentes em `.env.example`.
5. Gere previamente os valores de segredo; não mantenha `change-me-*`.
6. Clique em **Deploy the stack**.

Quando usar o método Git repository, informe:

```text
Compose path: deploy/portainer/compose.yaml
```

As variáveis ainda devem ser cadastradas no Portainer, porque `.env.example` não é carregado automaticamente.

## Persistência

Valor recomendado:

```text
HUBFISCAL_DATA_ROOT=/opt/hubfiscal/data
```

O usuário do Docker precisa escrever nesse diretório. A stack cria os subdiretórios necessários usando `hubfiscal-storage-init`.

## Acesso

Sem proxy reverso:

```text
HUBFISCAL_BIND_HOST=0.0.0.0
HUBFISCAL_HTTP_PORT=8088
```

A aplicação ficará em `http://IP_DO_SERVIDOR:8088`.

Atrás de proxy no mesmo host, prefira:

```text
HUBFISCAL_BIND_HOST=127.0.0.1
```

## Atualização

Altere `HUBFISCAL_IMAGE_TAG` e use **Pull latest image and redeploy**. A tag deve existir no GHCR; não use `latest` como única referência em produção.

## Diagnóstico no host

```bash
bash deploy/docker-doctor.sh deploy/portainer/compose.yaml deploy/portainer/.env

docker compose \
  --env-file deploy/portainer/.env \
  -f deploy/portainer/compose.yaml \
  ps -a
```
