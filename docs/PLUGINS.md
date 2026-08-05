# SDK de plugins

Plugins implementam o contrato `FiscalPlugin` e declaram capacidades. O orquestrador resolve uma política por tenant, entidade fiscal, tipo documental e operação.

Plugins incluídos:

- `repository`: procura o documento já armazenado.
- `manual-upload`: recebe XML/ZIP pela interface ou API.
- `simulated-source`: fonte controlada para testes e demonstração.
- `generic-http-xml`: integra APIs HTTP configuráveis e extrai XML bruto ou Base64.
- `portal-assisted`: cria sessão que exige ação humana e não executa quebra de CAPTCHA.

Integrações específicas devem ser pacotes ou containers separados, sem alterar o núcleo.
