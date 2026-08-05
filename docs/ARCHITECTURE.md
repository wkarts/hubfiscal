# Arquitetura

O Hub Fiscal utiliza um monólito modular para regras centrais e workers distribuídos para conectores e processamento pesado.

```text
Vue 3 -> FastAPI -> PostgreSQL
                -> RabbitMQ -> Celery workers -> plugins
                -> Redis (cache, locks e resultados)
                -> MinIO/S3 (XML, certificados e anexos)
```

## Domínios

- Identidade, autenticação e autorização.
- Tenants, parceiros, clientes e usuários.
- Entidades fiscais, inscrições e certificados.
- Documentos fiscais e eventos.
- Plugins, instalações, políticas e roteamento.
- Jobs, tentativas, auditoria e webhooks.

## Multi-tenancy

Toda entidade de negócio possui `tenant_id`. O acesso é validado no serviço e preparado para políticas RLS no PostgreSQL. Usuários globais da plataforma são diferenciados por `is_platform_admin`.

## Segurança

- Senhas com Argon2.
- JWT de curta duração e refresh token.
- Certificados criptografados com Fernet antes do armazenamento em MinIO.
- Segredos de plugins criptografados.
- XML com parser seguro e bloqueio de DTD/entidades externas.
- Auditoria de operações sensíveis.
