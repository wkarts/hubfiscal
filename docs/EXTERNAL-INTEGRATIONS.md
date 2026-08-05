# Integrações fiscais externas

O Hub Fiscal possui um núcleo funcional e um SDK de plugins. Os conectores externos são instalados e configurados por tenant, CNPJ e ambiente, sem credenciais embutidas no código.

## Conectores incluídos

- **Repositório interno:** funcional para localizar documentos já armazenados.
- **Upload XML/ZIP:** funcional, com validação estrutural, hash e deduplicação.
- **Fonte simulada:** funcional para homologação e testes de fluxo.
- **HTTP genérico:** funcional para provedores REST configuráveis.
- **ConsultaDanfe:** adaptador baseado no contrato HTTP configurado pelo administrador.
- **Distribuição NF-e:** contrato de plugin e worker preparados; a comunicação SOAP/mTLS oficial deve ser habilitada com certificado, schemas e URLs vigentes do ambiente fiscal.
- **NFS-e Nacional:** adaptador configurável para APIs autorizadas do ADN/SEFIN.
- **WebISS:** adaptador configurável por município, versão de layout e credencial.
- **Caixa postal:** contrato de coleta preparado para IMAP/API autorizada.
- **Portal assistido:** cria uma operação que exige sessão humana; não resolve CAPTCHA automaticamente.

## Garantias

A plataforma nunca classifica HTML, PDF ou XML reconstruído como documento fiscal original. Um documento completo precisa passar pelas validações aplicáveis de chave, estrutura, protocolo, assinatura e hash.

## Dependências externas

Operações reais dependem de certificado válido, autorização do contribuinte, credenciais, contrato do provedor, disponibilidade do serviço e regras fiscais vigentes. A ausência desses dados não impede a inicialização da plataforma; o plugin permanece desabilitado ou em estado de configuração pendente.
