---
description: Fases 2, 3 e 4 - Implementação (@engenheiro), Revisão (@revisor) e Documentação (@documentador)
---

Quando o usuário digitar `/executar <etapa>`, siga `.agents/agents.md` e `.agents/rules/huntly.md`.

Etapas válidas:
- `corrigir` (assumir papel **@engenheiro**):
  1. Leia os planos aprovados em `docs/analise/`.
  2. Aplique UMA correção por vez na ordem de prioridade aprovada.
  3. Rode `python -m pytest -v` após cada alteração para garantir que os testes existentes continuam passando.
  4. Faça um commit isolado com mensagem descritiva para cada correção concluída.
  5. Ao finalizar as correções aprovadas, pare e avise que está pronto para o `@revisor`.

- `revisar` (assumir papel **@revisor**):
  1. Inspecione o `git diff master..melhorias` completo buscando bugs introduzidos, brechas de segurança ou alterações fora do escopo.
  2. Crie testes temporários em `tmp-tests/` validando especificamente o filtro de país (Brasil), a consistência de idiomas e as regras de banco/estado.
  3. Rode `pytest` (incluindo `tests/` e `tmp-tests/`). Se algum teste falhar, liste o erro exato para o `@engenheiro` corrigir.
  4. Com tudo passando, faça um commit de checkpoint, remova `tmp-tests/` e remova apenas os arquivos/códigos mortos previamente aprovados pelo Jandin.
  5. Faça o commit final de limpeza e avise que está pronto para o `@documentador`.

- `documentar` (assumir papel **@documentador**):
  1. Leia os relatórios em `docs/analise/` e o `git diff master..melhorias` para entender tudo o que mudou no projeto.
  2. Crie ou atualize os registros de decisão (ADRs) numerados em `docs/decisoes/` (formato: Contexto, Decisão, Alternativas Descartadas, Consequências) para cada escolha técnica tomada (ex: padrão de tradução, filtro de país, ajustes de arquitetura).
  3. Atualize o `README.md` e a documentação técnica do projeto refletindo a nova estrutura, rotas, filtros e processo de deploy na VPS.
  4. Faça um commit final apenas com os arquivos `.md` atualizados.