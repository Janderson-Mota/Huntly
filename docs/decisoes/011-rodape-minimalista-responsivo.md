# ADR 011 — Rodapé Minimalista, Responsivo e Traduzido com Suporte a Temas

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

A interface do Huntly possuía barra de navegação superior, painel de filtros e seção de resultados, porém não contava com um rodapé institucional que fechasse visualmente o layout mantendo a tipografia editorial, o alinhamento ao container (`max-width: 1200px`) e suporte a claro/escuro e aos 8 idiomas.

## Decisão

1. **Estrutura Semântica (`templates/index.html`):**
   - Adicionado `<footer class="site-footer">` após `<main>` com marca (`huntly.`), separador discreto, tagline institucional (`data-i18n="footerTagline"`) e assinatura de direitos (`data-i18n="footerRights"`).

2. **Layout Flexbox Vertical e Tokens do Tema (`static/styles.css`):**
   - `body` configurado como flex container em coluna (`min-height: 100vh`) com `.main-container { flex: 1 0 auto; }` e `.site-footer { flex-shrink: 0; }`, mantendo o rodapé ancorado na base da viewport mesmo antes de qualquer busca.
   - Estilização feita com tokens CSS (`--border-light`, `--text-primary`, `--text-secondary`, `--text-muted`, `--accent-green`, `--font-serif`, `--font-mono`), herdando automaticamente os temas claro e escuro sem regras duplicadas de cor.
   - Borda superior sutil (`1px solid var(--border-light)`) dentro de `.site-footer-inner`, alinhada exatamente à largura útil dos cards/painel de filtros no desktop (`1024px` e `1440px`), centralizada em tablet (`768px`) e empilhada verticalmente e centralizada no mobile (`360px`) sem overflow horizontal.

3. **Internacionalização Completa (`static/i18n.js`):**
   - Adicionadas as chaves `ariaFooter`, `footerTagline` e `footerRights` em todos os 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), validadas por paridade no `pytest`.

## Alternativas Descartadas

- **Rodapé fixo (`position: fixed`):** descartado por consumir área útil de leitura em telas menores (`360px` / `768px`) e sobrepor cards.

## Consequências

- **Positivas:** Fechamento visual consistente em desktop e mobile nos temas claro e escuro, 100% traduzido nos 8 idiomas e sem impacto nas duas fileiras de filtros do desktop.
- **Negativas / Pontos de atenção:** Qualquer nova chave de rodapé adicionada futuramente deve manter paridade nos 8 dicionários de `static/i18n.js` (garantido pelo teste automatizado em `tests/test_filters_and_tabs.py`).
