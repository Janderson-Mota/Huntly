# ADR 013 — Refinamento de Microcopy, Botões e Estado Vazio (Preservando Identidade Visual)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Após revisão visual da interface e dos textos nos 8 idiomas, identificamos inconsistências de linguagem e peso visual em botões, estado vazio inicial e mensagens de progresso da busca — ao mesmo tempo em que certos traços marcantes da identidade visual do Huntly deveriam permanecer intocados por decisão de produto.

## Decisão

### O que foi ajustado

1. **Botões e Microcopy (`templates/index.html`, `static/i18n.js`, `static/styles.css`):**
   - Padronizada a capitalização em Sentence case nos botões principais, exportação, detalhes e paginação (ex.: `Limpar filtros`, `Buscar vagas`, `Exportar CSV`, `Exportar JSON`, `Ver detalhes`).
   - Removidas todas as setas Unicode e ícones de seta dos botões, paginação e selo de tradução (`↗`, `→`, `←`, `bi-arrow-right`, substituindo `→` em `translatedFromTo` por `/`), bem como o ícone `bi-arrow-counterclockwise` do botão **Limpar filtros**.
   - Padronizados todos os botões da interface em formato compacto (`btn-sm` em `#reset-filters-btn`, `#search-btn`, `#stop-button`, `#modal-link`, cards, exportação e `.pagination-btn`) e reduzida a altura dos campos, `<select>` e `.multi-select-trigger` para `34px` (`30px` em `.lang-select` e `.theme-toggle-btn`).

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

- **Positivas:** Interface mais compacta e enxuta, sem setas decorativas nem ícone de reinício no botão de limpeza, com botões pequenos (`btn-sm`) e controles `<select>` proporcionais nos 8 idiomas.
- **Negativas / Pontos de atenção:** Testes em `tests/test_filters_and_tabs.py` validam explicitamente a ausência de `↗`, `→` e `←` nas chaves de botões/paginação/selo nos 8 idiomas, ausência de `bi-arrow-counterclockwise` / `bi-arrow-right` no HTML e presença de `btn-sm` nos botões principais e do modal, além da ausência de `ID`/`IDs` em `statusCollectingPages`.
