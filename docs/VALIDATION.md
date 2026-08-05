# Validação do pacote 0.1.0

Validações executadas no pacote gerado:

- Compilação estática dos módulos Python com `compileall`.
- Testes automatizados do backend com `pytest`.
- Leitura e validação sintática dos arquivos YAML de Compose e GitHub Actions.
- Validação sintática dos scripts Bash.
- Validação dos arquivos JSON do frontend.

## Observação sobre o frontend

O build do Vue é executado pelo workflow de CI usando o registro público do npm. No ambiente de geração deste pacote, o proxy npm interno não disponibilizou alguns pacotes oficiais com escopo (`@vitejs`, `@types`), portanto não foi possível concluir o download das dependências nessa máquina. Isso não altera os arquivos do projeto; o workflow executará `npm install` e `npm run build` em um runner GitHub com acesso normal ao npm.
