# ADR 016 — Tradução Pós-Carregamento Progressiva e Indicador Discreto no Modal

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Durante a busca ativa, disparar requisições para `/translate` a cada atualização parcial de `pollResults()` gerava concorrência de rede e reconstruía todo `#results-grid` em bloco para 9 cards de uma só vez. Além disso, ao abrir o modal **"Ver detalhes"** (`openJobModal`) para uma vaga com descrição longa ainda não traduzida por completo, o usuário não recebia nenhum feedback discreto indicando que a tradução sob demanda estava em andamento.

## Decisão

1. **Renderização imediata na coleta e tradução somente pós-carregamento (`static/script.js`):**
   - `renderFilteredResults()` agora recebe `{ skipTranslation = false }` e só invoca `ensureTranslations(pageItems, { mode: "preview" })` (e o prefetch silencioso da próxima página) quando `!skipTranslation && !isSearching`.
   - Em `pollResults()`, estados terminais (`complete`, `progress === 100`, `stopped`, `error` ou `!data.is_searching`) chamam `setIdleState()` **antes** de `await fetchResults()`, garantindo que o término da busca dispare automaticamente a tradução em segundo plano; o mesmo ocorre em `stopSearch()` quando já existem cards carregados.

2. **Micro-lotes progressivos com atualização pontual no DOM (`static/script.js`):**
   - No modo `preview` dos cards, os itens pendentes da página visível são divididos em blocos de `CARD_TRANSLATION_CHUNK_SIZE = 3` despachados em paralelo via `_translateChunk()`.
   - À medida que cada bloco retorna de `POST /translate`, o resultado é gravado no cache em memória + `sessionStorage` (`huntly_translations_cache_v3`) e os cards correspondentes são atualizados no próprio DOM por `updateCardElementInPlace()` (título, resumo e selo `.translated-badge`), recorrendo a `renderFilteredResults({ skipTranslation: true })` apenas quando há filtros instantâneos ativos (`#quick-filter-input` / `#exclude-filter-input`).

3. **Indicador discreto sob demanda e fallback seguro no modal (`templates/index.html`, `static/styles.css`, `static/i18n.js`, `static/script.js`):**
   - Adicionado `#modal-translating-indicator` com ponto pulsante discreto (`.modal-translating-dot`) entre os badges e o corpo da descrição no modal, estilizado via tokens de tema claro/escuro e traduzido nos 8 idiomas (`modalTranslating`).
   - `openJobModal()` exibe a vaga e o texto disponível imediatamente, ativa `#modal-translating-indicator` somente quando `job.description` existe e ainda não possui tradução completa em cache (`!(cached && cached.is_full)`), atualiza modal e card ao receber `mode=full` e sempre oculta o indicador no bloco `finally` (ou em `closeModal()`), mantendo o texto original caso a tradução falhe.

## Alternativas Descartadas

- **Traduzir dentro da thread do scraper antes de salvar em `SearchState`:** descartado pois acopla a coleta do LinkedIn à latência de um serviço externo de tradução e atrasa a exibição inicial dos cards.
- **Usar um único lote de 9+ vagas por página e reconstruir todo `#results-grid`:** descartado porque atrasa a aparição dos primeiros cards traduzidos e causa reflow completo da grade.
- **Bloquear a abertura do modal aguardando a tradução completa:** descartado para preservar abertura instantânea com indicador visual não intrusivo e fallback seguro para o texto original.

## Consequências

- **Positivas:** Cards aparecem instantaneamente após o scraping, traduzem progressivamente em segundo plano com reaproveitamento de cache (LRU no back-end e `sessionStorage` no navegador) e o modal oferece feedback claro nos 8 idiomas sem travar ou falhar em caso de indisponibilidade do tradutor.
- **Negativas / Pontos de atenção:** Durante uma fração de segundo logo após o término do scraping, os títulos/resumos aparecem no idioma original da vaga até os blocos assíncronos de 3 cards responderem.
