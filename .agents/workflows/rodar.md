---
description: Fluxo automático completo do Huntly em 2 passos (Análise -> Aprovação -> Execução Total)
---

Siga `.agents/agents.md` e `.agents/rules/huntly.md`.
Execute o fluxo completo de forma autônoma, assumindo cada papel na ordem abaixo sem pedir intervenção entre as etapas internas:

### BLOCO 1: DIAGNÓSTICO COMPLETO (Executar tudo agora e parar só no final deste bloco)
1. Rode `python -m pytest -v` e registre a linha de base.
2. Como **@auditor**: analise front, back (`app.py`, `scraper.py`), estado/banco (`state.py`), ache a causa raiz do filtro de país (Brasil trazendo outros países), outros bugs e liste o que pode ser apagado. Salve em `docs/analise/auditoria_fullstack.md`.
3. Como **@frontend**: teste a responsividade em 360, 768, 1024 e 1440 px no navegador (com prints) e mapeie todos os textos fixos que não mudam de idioma. Salve em `docs/analise/visual_e_idiomas.md`.
4. **PARE AQUI:** Apresente um resumo único com o plano de correção, a lista do que será apagado e as decisões pendentes. Aguarde o "Aprovado" do Jandin.

---

### BLOCO 2: EXECUÇÃO TOTAL (Executar tudo em sequência assim que o Jandin responder "Aprovado")
1. Como **@engenheiro**: aplique todas as correções aprovadas (uma por vez, rodando `pytest` e fazendo um commit por correção na branch `melhorias`).
2. Como **@revisor**: revise o `git diff master..melhorias`, crie testes em `tmp-tests/` provando o filtro do Brasil e os idiomas, rode todo o `pytest`, apague `tmp-tests/` e remova os arquivos/códigos mortos aprovados. Faça o commit de limpeza.
3. Como **@documentador**: registre as decisões técnicas (ADRs) em `docs/decisoes/` e atualize o `README.md`. Faça o commit final de documentação.
4. Entregue o resumo final pronto para deploy.