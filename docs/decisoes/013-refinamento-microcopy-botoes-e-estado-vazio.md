# ADR 013 — Refinamento de Microcopy, Botões e Estado Vazio (Preservando Identidade Visual)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Após revisão visual da interface e dos textos nos 8 idiomas, identificamos inconsistências de linguagem e peso visual em botões, estado vazio inicial e mensagens de progresso da busca — ao mesmo tempo em que certos traços marcantes da identidade visual do Huntly deveriam permanecer intocados por decisão de produto.

## Decisão

### O que foi ajustado

1. **Botões e Microcopy (`templates/index.html`, `static/i18n.js`):**
   - Padronizada a capitalização em Sentence case nos botões principais, exportação, detalhes e paginação (ex.: `Limpar filtros`, `Buscar vagas`, `Exportar CSV`, `Exportar JSON`, `Ver detalhes`).
   - Removido o símbolo de link externo (`↗`) de ações internas (`btnExportCsv`, `btnExportJson`, `btnDetails`), mantendo `↗` exclusivamente nos links externos para o LinkedIn (`btnOpenLinkedin`, `modalOpenLinkedin`).

2. **Estado Vazio Leve e Compacto (`static/styles.css`, `templates/index.html`, `static/i18n.js`):**
   - Removidos a borda tracejada e o container branco pesado do `.empty-state`, reduzindo o padding vertical para `1.5rem 1rem` e adotando texto direto (`Pronto para buscar` / `Escolha um cargo ou filtro acima para listar vagas.`).

3. **Mensagens Naturais de Progresso e Sem Resultados (`templates/index.html`, `static/i18n.js`):**
   - Reescritas nos 8 idiomas as mensagens de status (`statusPreparing`, `statusCounting`, `statusCollectingPages`, `statusFetchingDetails`, `statusNoResults`, `statusComplete`, `statusError`) e de abas vazias (`emptyTabMatchedTitle/Desc`, `emptyTabRecommendedTitle/Desc`), removendo jargões internos como `"IDs"` e `"estritamente"` sem alterar nenhum placeholder dinâmico.

### O que foi mantido intacto por decisão explícita

- **Linhas superiores coloridas dos cards** (`.result-card:nth-child(3n + 1/2/3)` em `static/styles.css`).
- **Bandeiras no seletor de idiomas** (`#lang-select` em `templates/index.html`).
- **Fonte `JetBrains Mono`** no trecho dos cards (`.card-excerpt`) e no subtítulo do estado vazio (`.empty-state p`).

## Alternativas Descartadas

- **Trocar `JetBrains Mono` por fonte sans-serif ou remover faixas coloridas e bandeiras:** descartado por escolha do usuário para preservar a assinatura estética atual do Huntly.

## Consequências

- **Positivas:** Interface mais legível antes da primeira busca, ações internas e externas semanticamente diferenciadas (`↗` apenas para fora do app) e mensagens naturais nos 8 idiomas.
- **Negativas / Pontos de atenção:** Testes em `tests/test_filters_and_tabs.py` agora validam explicitamente a ausência de `↗` em ações internas, presença em links externos do LinkedIn e ausência do jargão `ID`/`IDs` em `statusCollectingPages`.
