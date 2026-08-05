# CloudPanel / Dockge

1. Copie `deploy/cloudpanel/.env.example` para `.env` e ajuste domínio, senhas e diretórios.
2. Crie o diretório físico configurado em `HUBFISCAL_DATA_ROOT`.
3. Importe `deploy/cloudpanel/compose.yaml` no Dockge ou execute pelo terminal.
4. Configure o proxy reverso do CloudPanel para o serviço web e para `/api`.
5. Mantenha PostgreSQL, Redis, RabbitMQ e MinIO sem portas públicas em produção.

Os volumes são bind mounts físicos, permitindo backup, inspeção e restauração sem depender do diretório interno do Docker.

## Backup e restauração

```bash
./scripts/backup.sh
HUBFISCAL_RESTORE_CONFIRM=RESTORE ./scripts/restore.sh /caminho/do/backup
```

A restauração interrompe temporariamente API e workers e substitui o banco e o conteúdo do MinIO.
