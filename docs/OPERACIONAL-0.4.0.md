# Hub Fiscal 0.4.0 — Console operacional

A versão 0.4.0 completa a experiência operacional inicialmente planejada para a plataforma.

## Consultas

- consulta por chave individual;
- consulta em lote com deduplicação;
- seleção de CNPJ, tipo de documento, ambiente e fonte;
- acompanhamento de jobs e lotes;
- Distribuição DF-e da NF-e com `distNSU`, `consNSU` e `consChNFe`;
- cursor `ultNSU`/`maxNSU` por tenant, CNPJ, ambiente e instalação;
- bloqueio temporário após consumo indevido ou ausência de novos documentos conforme retorno do Ambiente Nacional;
- limitação distribuída de consultas pontuais por Redis.

## Aplicativos e conectores

- catálogo visual de conectores;
- instalações separadas por tenant/CNPJ;
- configuração guiada em vez de JSON bruto;
- segredos criptografados;
- ativar, desativar, testar, reconfigurar e remover;
- configuração específica para Distribuição DF-e, API HTTP genérica e conectores HTTP especializados.

Os conectores `nfse-national`, `webiss` e `fiscal-mailbox` permanecem baseados no adaptador HTTP configurável nesta versão. Eles não são apresentados como implementação municipal/universal nativa quando dependem de contrato, layout ou credenciais externas.

## Conta do usuário

- edição de nome e e-mail;
- alteração da própria senha;
- foto/avatar armazenado no cofre de objetos;
- avatar exibido no cabeçalho.

## Segurança

- escopo de tenant e CNPJ preservado;
- certificado A1 continua criptografado no storage;
- material PEM de mTLS é temporário e removido ao final da chamada;
- plugins não expõem segredos nas respostas;
- conectores DF-e respeitam regras de consumo do Ambiente Nacional.

## Deploy

`APP_IMAGE_TAG=latest` permanece o padrão operacional. As tags SemVer continuam sendo publicadas para auditoria e rollback.
