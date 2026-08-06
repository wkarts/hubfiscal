# Hub Fiscal no Dockge

## Estrutura recomendada

```text
/opt/stacks/hubfiscal/
├── compose.yaml
├── .env
└── data/
```

## Instalação

1. Crie uma nova stack chamada `hubfiscal` no Dockge.
2. Cole o conteúdo de `compose.yaml` no editor da stack.
3. Copie `.env.example` para o campo de ambiente ou para `.env`.
4. Gere os segredos antes da implantação:

```bash
cd /opt/stacks/hubfiscal
bash /caminho/do/repositorio/scripts/generate-env.sh .env.example .env
```

5. Ajuste `HUBFISCAL_CORS_ORIGINS` e `HUBFISCAL_BIND_HOST`.
6. Quando o GHCR estiver privado, faça `docker login ghcr.io` no host.
7. Clique em **Deploy**.

## Validação

```bash
bash /caminho/do/repositorio/deploy/docker-doctor.sh \
  /opt/stacks/hubfiscal/compose.yaml \
  /opt/stacks/hubfiscal/.env
```

Após iniciar:

```bash
docker compose \
  --env-file /opt/stacks/hubfiscal/.env \
  -f /opt/stacks/hubfiscal/compose.yaml \
  ps -a
```

Acesse `http://IP_DO_SERVIDOR:8088`, salvo alteração de `HUBFISCAL_HTTP_PORT`.

## Atualização

Altere `HUBFISCAL_IMAGE_TAG`, salve o `.env` e use **Update** ou **Deploy**. O serviço `hubfiscal-migrate` executará as migrations antes da API.

## Observações

- Não use `docker compose down -v` em produção.
- Não altere o nome dos serviços, pois a rede interna depende deles.
- Faça backup de `HUBFISCAL_DATA_ROOT`.
- Caso a porta seja exposta diretamente, restrinja-a no firewall ou utilize proxy HTTPS.
