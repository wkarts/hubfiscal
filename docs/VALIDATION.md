# Validação do Hub Fiscal

A CI valida cada Pull Request e cada push em `main`.

## Contrato de versão e imagem

- `VERSION`, API, pacote Python, frontend e `VITE_APP_VERSION` precisam coincidir.
- Os ambientes de produção precisam manter `APP_IMAGE_TAG=latest`.
- `set-version.py` não pode alterar a tag operacional `latest`.
- Os quatro Compose de produção precisam ser byte a byte idênticos.
- API e Web precisam declarar fallback `${APP_IMAGE_TAG:-latest}`.
- As imagens da aplicação precisam declarar `pull_policy: always`.

## Docker

São validados:

```text
compose.yaml
compose.production.yaml
deploy/cloudpanel/compose.yaml
deploy/dockge/compose.yaml
deploy/portainer/compose.yaml
```

O job executa:

- `docker compose config --quiet` com cada `.env.example`;
- build da API de desenvolvimento;
- build do frontend de desenvolvimento;
- build das imagens-base reais;
- build da API de produção;
- build do frontend de produção.

## Backend

- Ruff;
- `compileall`;
- Pytest;
- testes das URLs internas com credenciais escapadas;
- validação de configurações explícitas e automáticas.

## Frontend

- instalação do lock/contrato de dependências;
- TypeScript e `vue-tsc`;
- build Vite de produção.

## Release

O empacotamento é executado na CI e precisa gerar:

```text
source ZIP
source TAR.GZ
pacote CloudPanel
pacote Dockge
pacote Portainer
release-manifest.json
SHA256SUMS
```

O manifesto registra a versão exata e a tag operacional `latest`.

## Segurança

O workflow de segurança executa Trivy e publica o resultado SARIF no GitHub Code Scanning.
