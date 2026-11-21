# ADR 012 — Reorganização Responsiva do Cabeçalho (Links, Idioma e Tema)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

No layout anterior da barra superior (`<header class="navbar">`), a marca `huntly.`, os links (`filtros`, `resultados`), o seletor de idioma e o botão de tema compartilhavam o mesmo `<nav class="navbar-links">`. Em telas menores (`<= 640px`, como `360px`), os quatro elementos eram espremidos na segunda linha em uma mesma faixa, gerando poluição visual e pouco espaço entre links de navegação e controles de preferência.

## Decisão

1. **Separação Semântica (`templates/index.html`, `static/i18n.js`):**
   - Dividido o conteúdo de `.navbar-inner` em marca (`.navbar-brand`), navegação principal (`<nav class="navbar-nav">` com `ariaMainNav` traduzido nos 8 idiomas para `filtros` e `resultados`) e grupo utilitário (`.navbar-controls` contendo `#lang-select` e `#theme-toggle-btn`).

2. **Alinhamento Desktop e Grade em 2 Linhas no Mobile (`static/styles.css`):**
   - No desktop (`> 640px`): marca à esquerda (`margin-right: auto`), links à direita separados por divisória sutil (`border-left`) dos controles de idioma e tema (ambos padronizados com `height: 32px`).
   - Em telas menores (`@media (max-width: 640px)`): `.navbar-inner` passa a usar CSS Grid em 2 linhas:
     - **Linha 1:** marca `huntly.` à esquerda e controles (`idioma` + `tema`) alinhados à direita na mesma altura.
     - **Linha 2:** sub-barra horizontal ocupando toda a largura (`grid-column: 1 / -1`) com `filtros | resultados` divididos em 2 colunas iguais (`repeat(2, minmax(0, 1fr))`) e divisórias sutis (`border-top` / `border-left`).

## Alternativas Descartadas

- **Menu hambúrguer com JavaScript adicional:** descartado pois existem apenas 2 âncoras de página (`filtros` e `resultados`); uma sub-barra direta em 2 colunas evita cliques extras e mantém a navegação sempre visível.

## Consequências

- **Positivas:** Hierarquia visual nítida entre navegação e preferências do usuário em `360px`, maior área de toque nos links mobile e alinhamento vertical idêntico entre seletor de idioma e botão de tema.
- **Negativas / Pontos de atenção:** Se novos links forem adicionados ao `.navbar-nav`, a grade de 2 colunas em `<= 640px` deverá ser ajustada para `repeat(N, minmax(0, 1fr))` ou `auto-fit`.
