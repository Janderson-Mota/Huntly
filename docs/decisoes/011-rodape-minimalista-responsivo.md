# ADR 011 — Rodapé Minimalista, Centralizado, Sem Links e Responsivo

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

A interface do Huntly precisava de um fechamento visual no rodapé que acompanhasse a largura do container (`max-width: 1200px`), funcionasse nos temas claro e escuro e em todos os 8 idiomas, porém sem duplicar links do cabeçalho e informando diretamente o escopo da ferramenta ao lado da marca `huntly.`.

## Decisão

1. **Estrutura Centralizada e Sem Links (`templates/index.html`):**
   - `<footer class="site-footer">` após `<main>` exibe centralizadamente em linha contínua no desktop/tablet:
     - `<span class="footer-brand">huntly.</span>`
     - `<span class="footer-sep" aria-hidden="true">—</span>`
     - `<p class="footer-meta" data-i18n="footerRights">Buscador de vagas públicas · Sem vínculo com o LinkedIn</p>`
   - Nenhuma tag `<a>` dentro do `<footer>`.

2. **Layout Flexbox Centralizado e Tokens do Tema (`static/styles.css`):**
   - `body` configurado como flex container em coluna (`min-height: 100vh`) com `.main-container { flex: 1 0 auto; }` e `.site-footer { flex-shrink: 0; }`, mantendo o rodapé na base da viewport quando não há resultados.
   - `.site-footer-inner` usa `justify-content: center; text-align: center; align-items: baseline;` com borda superior sutil (`1px solid var(--border-light)`) alinhada ao container principal (`1200px`).
   - Em telas menores (`<= 640px`), `.footer-sep` é ocultado e a assinatura empilha centralizada abaixo de `huntly.` em uma composição limpa.

3. **Internacionalização Completa (`static/i18n.js`):**
   - Mantidas `ariaFooter` e `footerRights` nos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), validadas por paridade e ausência de links no `pytest`.

## Alternativas Descartadas

- **Navegação duplicada ou rodapé dividido nas extremidades (`space-between`):** descartados por preferência de layout centralizado único (`huntly. — Buscador de vagas públicas · Sem vínculo com o LinkedIn`) e ausência de links redundantes.

## Consequências

- **Positivas:** Rodapé discreto, transparente quanto ao vínculo com o LinkedIn, centralizado em todas as larguras e consistente nos temas claro e escuro.
- **Negativas / Pontos de atenção:** Caso novas seções textuais sejam adicionadas ao rodapé futuramente, recomenda-se preservar o alinhamento centralizado e a ausência de links redundantes.
