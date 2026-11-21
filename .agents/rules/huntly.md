# Regras do projeto Huntly

## Segurança e Controle
- Trabalhar sempre na branch `melhorias`, nunca direto na `master`.
- Fazer commit de checkpoint antes de iniciar cada fase.
- Nunca apagar arquivos, pastas ou dependências sem listar antes e obter aprovação explícita do Jandin.
- Nunca rodar comandos destrutivos (`rm -rf`, `git reset --hard`, `git push --force`, apagar banco) sem aprovação.
- Nunca ler, alterar ou imprimir em relatórios o conteúdo de `.env`, chaves ou senhas.
- Nunca fazer deploy nem mexer no servidor de produção (VPS).

## Testes e Linha de Base
- A pasta `tests/` existente pertence ao Jandin: nunca apagar nem editar sem aprovação.
- Antes de qualquer alteração, rodar `python -m pytest -v` e registrar os testes passando como linha de base.
- Testes temporários novos devem ficar exclusivamente em `tmp-tests/` e ser apagados apenas na etapa final de revisão, após commit.

## Método
- Em fase de análise: SOMENTE LEITURA. Não alterar código, não apagar nada e não instale dependências.
- Toda afirmação técnica deve citar `arquivo:linha`. O que for hipótese deve ser marcado explicitamente como hipótese.
- Uma correção por vez: mudança mínima, uma prova (teste ou captura de tela) e um commit com mensagem clara.
- Não refatorar nem "melhorar" trechos que não estão no escopo aprovado.

## Critérios de Pronto
- **Filtro de país:** Selecionar "Brasil" retorna exclusivamente vagas do Brasil.
- **Idiomas (i18n):** 100% da interface (rótulos, datas, selects, mensagens, erros) segue o idioma escolhido, sem resquícios de outro idioma. Título e descrição das vagas permanecem no idioma original do LinkedIn.
- **Responsividade:** Zero rolagem horizontal e zero elementos cortados/sobrepostos em 360px, 768px, 1024px e 1440px.
- **Limpeza:** Nenhum arquivo, dependência ou código morto aprovado permanece no projeto.