# ADR 004 — Ajustes de Responsividade, Favicon Inline e Limpeza de Código Morto

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

A auditoria visual (`docs/analise/visual_e_idiomas.md`) apontou pontos de melhoria nos viewports `360px`, `768px` e `1024px`:
- Em `360px`: navbar sticky alta (`157.9px` em 3 linhas visuais), botões de ação/exportação desalinhados e sem largura total, modal com paddings largos e sem `overflow-wrap: anywhere`, além de erro HTTP 404 por ausência de favicon.
- Em `768px`: `@media (max-width: 768px)` colapsava todo o layout para 1 coluna única (`720px` por card) e `.filters-grid` gerava 3 colunas + 1 filtro órfão.
- Em `1024px`: os 3 campos de localização dividiam espaço horizontal com o campo de palavra-chave (`164.9px` cada).
- Existia ainda código morto remanescente de refatorações anteriores: 4 chaves i18n não usadas nos 8 idiomas (`static/i18n.js`), persistência incompleta de `huntly_last_filters` e `huntly_recent_keywords` (`static/script.js`), e bloco inalcançável de scraping em `get_job_count()` (`scraper.py`).

## Decisão

1. **Breakpoints progressivos e proteção contra overflow (`static/styles.css`):**
   - `@media (max-width: 1120px)`: `.primary-inputs-grid` passa para `1fr`, liberando largura ampla para País, Estado e Cidade em `1024px` (`~295px` cada).
   - `@media (max-width: 900px)`: `.filters-grid` usa grade simétrica `2×2` e `.results-grid` exibe **2 colunas** em tablet (`768px`).
   - `@media (max-width: 640px)`: compactação da `.navbar` mobile (`119.1px`), campos em 1 coluna, botões de formulário/exportação/cards com largura total proporcional, modal ajustado para telas estreitas, e `overflow-wrap: anywhere; word-break: break-word` aplicado a títulos, subtítulos, excertos e corpo do modal.
2. **Favicon inline SVG (`templates/index.html`):**
   - Adicionado `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,...">` no `<head>`, zerando requisições 404 no console sem adicionar arquivos binários estáticos.
3. **Limpeza aprovada (Decisões D1 e D3):**
   - Removidas as 4 chaves órfãs nos 8 idiomas em `static/i18n.js` (`heroTitleStart`, `heroTitleAccent`, `heroSubtitle`, `recentLabel`).
   - Removidos `huntly_last_filters`, `saveCurrentFilters()` e `huntly_recent_keywords` de `static/script.js`, mantendo o comportamento de filtros neutros ao abrir a página.
   - Simplificada `get_job_count()` em `scraper.py` removendo o trecho inalcançável de requisição HTML, preservando a assinatura da função e os parâmetros legados em `build_params()` para manter intacta a suíte `tests/`.

## Alternativas Descartadas

- **Implementar restauração automática de `huntly_last_filters`:** descartado (Decisão D1) para manter os filtros neutros ao abrir o aplicativo.
- **Remover `distance`, `sort_by` e `easy_apply` de `scraper.build_params()`:** descartado (Decisão D3) porque `tests/test_scraper.py` valida diretamente esses parâmetros.

## Consequências

- **Positivas:** Zero overflow horizontal e zero erros no console em `360px`, `768px`, `1024px` e `1440px`, com layout aproveitado em tablet/desktop e código-fonte mais enxuto.
- **Negativas / Pontos de atenção:** Nenhuma conhecida.
