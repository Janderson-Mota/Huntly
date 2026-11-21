# ADR 011 — Rodapé Editorial Minimalista, Responsivo e Traduzido com Suporte a Temas

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

A interface do Huntly possuía barra de navegação superior, painel de filtros e seção de resultados, porém não contava com um rodapé institucional que fechasse visualmente a página com linguagem direta, alinhamento ao container (`max-width: 1200px`), suporte aos temas claro/escuro e internacionalização nos 8 idiomas.

## Decisão

1. **Estrutura Editorial Direta (`templates/index.html`):**
   - Adicionado `<footer class="site-footer">` após `<main>`, dividido em dois blocos:
     - **Esquerda (`.footer-identity`):** marca `huntly.` e nota direta de origem/independência (`data-i18n="footerTagline"`, ex.: `"Busca em vagas públicas do LinkedIn · não afiliado ao LinkedIn"`).
     - **Direita (`.footer-right`):** navegação prática (`filtros`, `resultados`, `topo ↑` em `<nav class="footer-nav">`), divisor discreto e indicação enxuta de ano (`© 2026` via `footerRights`).

2. **Layout Flexbox Vertical e Tokens do Tema (`static/styles.css`):**
   - `body` configurado como flex container em coluna (`min-height: 100vh`) com `.main-container { flex: 1 0 auto; }` e `.site-footer { flex-shrink: 0; }`, mantendo o rodapé ancorado na base da viewport mesmo antes de qualquer busca.
   - Estilização com tokens CSS (`--border-light`, `--text-primary`, `--text-secondary`, `--text-muted`, `--accent-green`, `--font-serif`, `--font-mono`), herdando automaticamente os temas claro e escuro sem regras duplicadas.
   - Borda superior sutil (`1px solid var(--border-light)`) alinhada à largura dos painéis no desktop (`1024px` e `1440px`), centralizada em tablet (`768px`) e empilhada/centralizada no mobile (`360px`) sem overflow horizontal.

3. **Internacionalização Completa (`static/i18n.js`):**
   - Adicionadas as chaves `ariaFooter`, `ariaFooterNav`, `footerTagline`, `footerBackToTop` e `footerRights` em todos os 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), validadas por paridade no `pytest`.

## Alternativas Descartadas

- **Rodapé fixo (`position: fixed`):** descartado por consumir área útil de leitura em telas menores (`360px` / `768px`) e sobrepor cards.
- **Copy genérica de template ("Desenvolvido com foco em..." / "Todos os direitos reservados"):** substituída por nota transparente sobre a fonte pública dos dados e links úteis de retorno.

## Consequências

- **Positivas:** Fechamento visual limpo e autêntico em desktop e mobile nos temas claro e escuro, 100% traduzido nos 8 idiomas e sem impacto no grid de filtros.
- **Negativas / Pontos de atenção:** Novas chaves adicionadas ao rodapé devem manter paridade nos 8 dicionários de `static/i18n.js` (verificado por `pytest`).
