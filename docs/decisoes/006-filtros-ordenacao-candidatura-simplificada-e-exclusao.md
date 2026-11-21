# ADR 006 — Ordenação (`sort_by`), Candidatura Simplificada (`easy_apply`) e Filtro Negativo em Tempo Real

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

Em complemento à entrega dos ajustes de i18n e catálogo de cargos (ADR 005), foi solicitada uma atualização nos filtros da interface e na barra de resultados na branch `melhorias`:
1. Substituir o select **Tipo de contrato** (`#job_type`) no 4º slot de `.filters-grid` pelo select **Ordenar por** (`#sort_by`) com as opções **Mais relevantes** e **Mais recentes**, conectado ao parâmetro `sort_by` no `scraper.py`.
2. Adicionar um checkbox/filtro rápido de **Candidatura Simplificada** conectado ao parâmetro `f_AL=true` / `easy_apply` no `scraper.py`.
3. Adicionar um campo rápido de **exclusão de palavras-chave** na barra de resultados (`#results-toolbar`) para ocultar em tempo real vagas cujos títulos ou descrições contenham termos indesejados separados por vírgula (ex.: `"Sênior, Estágio"`).
4. Manter cobertura completa nos 8 idiomas em `static/i18n.js`, validar responsividade nos 4 viewports (`360px`, `768px`, `1024px`, `1440px`), preservar todos os testes em `pytest` e atualizar a documentação.

## Decisão

1. **Ordenação pelo LinkedIn com preservação da ordem na coleta paralela (`templates/index.html`, `app.py`, `scraper.py`):**
   - O 4º slot de `.filters-grid` passa a renderizar `#sort_by` (`name="sort_by"`) com `"R"` (**Mais relevantes**, padrão) e `"DD"` (**Mais recentes**).
   - Em `app.py`, `sort_by` é normalizado em maiúsculas (`.upper()`); em `scraper.py`, `build_params` já mapeia `"R"` e `"DD"` para `sortBy=R` / `sortBy=DD` quando presentes.
   - Em `search_jobs_thread()` (`scraper.py`), como a coleta de detalhes usa `ThreadPoolExecutor(max_workers=2)` com `as_completed`, resultados mais rápidos poderiam chegar fora da ordem original de `job_ids`. Passou-se a manter um mapa `job_order = {jid: idx ...}` para reordenar `jobs` conforme a sequência original retornada pelo LinkedIn antes de publicar em `jobs_state.set_results(list(jobs), run_id=run_id)`.
   - `job_type` foi mantido na validação de `POST /search` (recebendo `[]` pela UI) para preservar retrocompatibilidade de API e manter intacta a suíte de testes existente (`tests/`).
2. **Candidatura Simplificada (`#easy_apply` → `f_AL=true`):**
   - Adicionado o controle `<label class="easy-apply-toggle" for="easy_apply">` com `<input type="checkbox" id="easy_apply" name="easy_apply" />` dentro de `.form-actions` (alinhado à esquerda no desktop/tablet e acima dos botões empilhados no mobile).
   - Os botões de ação (`#reset-filters-btn`, `#stop-button`, `#search-btn`) foram agrupados em `.form-actions-buttons` para que `flex-direction: column-reverse` no breakpoint `<= 640px` reordene apenas os botões, mantendo o checkbox sempre visível acima deles.
   - Em `app.py`, adicionado `_parse_bool()` para converter com segurança strings (`"true"`/`"false"`) e booleanos JSON enviados para `easy_apply`, evitando falso positivo com `bool("false")`.
3. **Filtro negativo em tempo real na barra de resultados (`#exclude-filter-input` e `static/script.js`):**
   - Incluído `#exclude-filter-input` ao lado de `#quick-filter-input` dentro de `.results-filters` em `#results-toolbar`.
   - Em `renderFilteredResults()`, termos separados por vírgula são normalizados via `normalizeLookup()` (NFD sem acentos e lowercase) e comparados contra `title` e `description` tanto do objeto original quanto da versão traduzida retornada por `getDisplayJob(item)` (ex.: digitar `"Senior, Estagio"` exclui `"Sênior"`, `"Estágio"` e títulos traduzidos em outros idiomas).
   - `resetFilters()` limpa também `#exclude-filter-input`, desmarca `#easy_apply`, volta `#sort_by` para `"R"` e re-renderiza os cards carregados.
   - Adicionadas mensagens específicas de estado vazio quando todos os cards são ocultados apenas pela exclusão (`emptyNoMatchExcludeDesc`) ou pela combinação de inclusão + exclusão (`emptyNoMatchCombinedDesc`).
4. **Internacionalização e Responsividade (`static/i18n.js`, `static/styles.css`):**
   - Removidas dos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`) as 7 chaves exclusivas do select removido (`labelJobType`, `typeAll`, `typeFull`, `typePart`, `typeIntern`, `typeContract`, `typeTemp`), mantendo integralmente `empFullTime`..`empOther` usadas nos badges dos cards/modal.
   - Adicionadas nos 8 idiomas 9 novas chaves (`labelSortBy`, `sortRelevant`, `sortRecent`, `labelEasyApply`, `ariaQuickFilter`, `excludeFilterPlaceholder`, `ariaExcludeFilter`, `emptyNoMatchExcludeDesc`, `emptyNoMatchCombinedDesc`).
   - Ajustados os breakpoints (`640px` e `900px`) em `static/styles.css` garantindo `0` overflow horizontal nos 4 viewports (`360px`, `768px`, `1024px`, `1440px`).

## Alternativas Descartadas

- **Remover completamente `job_type` dos parâmetros de `app.py` e `scraper.py`:** descartado porque `tests/test_app.py` e `tests/test_scraper.py` exercitam diretamente validação de `job_type` e `build_params(..., job_type=["F"])`.
- **Aplicar exclusão de palavras-chave também sobre o campo `company`:** descartado pois termos comuns de senioridade/tipo (ou nomes de empresas) poderiam gerar falsos positivos; restringir aos campos `title` e `description` (originais e traduzidos) atende exatamente ao requisito.
- **Executar nova busca no LinkedIn com operadores booleanos `NOT` para o campo de exclusão:** descartado pois o usuário pediu filtragem instantânea em tempo real nos resultados já carregados na interface.

## Consequências

- **Positivas:** Usuários escolhem relevância vs. mais recentes já no formulário principal respeitando a ordem original do LinkedIn, ativam Candidatura Simplificada em um clique e filtram positivamente ou negativamente os cards sem novas requisições.
- **Negativas / Pontos de atenção:** `sort_by` inicia selecionado em `"R"` (`Mais relevantes`) com duas opções explícitas; a exclusão de palavras-chave atua sobre os cards coletados no cliente até o `limit_jobs` da busca atual.
