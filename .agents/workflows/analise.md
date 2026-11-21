---
description: Fase 1 - Análise completa somente leitura (@auditor e @frontend)
---

Quando o usuário digitar `/analise <escopo>`, siga `.agents/agents.md` e `.agents/rules/huntly.md`.
Esta fase é SOMENTE LEITURA: não altere código, não apague nada e não instale dependências.

Antes de iniciar, execute `python -m pytest -v` e registre o resultado como linha de base no relatório.

Escopos válidos:
- `geral` (assumir papel **@auditor**) -> Salvar em `docs/analise/auditoria_fullstack.md`:
  1. **Arquitetura e Dados:** Fluxo completo (Front -> `app.py` -> `scraper.py` -> `state.py`/Banco de dados), esquema de dados, cache e pontos frágeis.
  2. **Bugs e Lógica:** Causa raiz do filtro de país (Brasil retornando outros países), problemas de estado/concorrência, tratamento de falhas e casos de borda.
  3. **Limpeza:** Lista de arquivos, pastas, dependências e código morto com justificativa (NÃO apagar).

- `visual` (assumir papel **@frontend**) -> Salvar em `docs/analise/visual_e_idiomas.md`:
  1. **Responsividade:** Quebras de layout em 360px, 768px, 1024px e 1440px (formulário de busca, filtros e cards), anexando capturas de tela.
  2. **Idiomas (i18n):** Mapeamento de todos os textos fixos ou gerados via JS/HTML que não mudam de idioma. Separar claramente textos de interface de título/descrição vindos do LinkedIn.

Termine cada relatório com um **Plano de Correção Priorizado** e uma seção **Decisões Pendentes do Jandin**. Pare e aguarde aprovação.