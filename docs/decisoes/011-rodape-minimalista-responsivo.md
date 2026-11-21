# ADR 011 — Rodapé Minimalista, Genérico, Sem Links e Responsivo

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

A interface do Huntly precisava de um fechamento visual no rodapé que acompanhasse a largura do container (`max-width: 1200px`), funcionasse nos temas claro e escuro e em todos os 8 idiomas, porém sem introduzir repetição dos links já presentes no cabeçalho e sem parecer uma barra institucional excessiva.

## Decisão

1. **Estrutura Enxuta e Sem Links (`templates/index.html`):**
   - Mantido `<footer class="site-footer">` após `<main>` contendo apenas:
     - Marca em texto puro: `<span class="footer-brand">huntly.</span>`
     - Assinatura neutra e amigável: `<p class="footer-meta" data-i18n="footerRights">© 2026 · Todos os direitos reservados</p>`
   - Nenhuma tag `<a>` dentro do `<footer>` (removendo duplicação de links com o cabeçalho).

2. **Layout Flexbox Vertical e Tokens do Tema (`static/styles.css`):**
   - `body` configurado como flex container em coluna (`min-height: 100vh`) com `.main-container { flex: 1 0 auto; }` e `.site-footer { flex-shrink: 0; }`, ancorando o rodapé na base da viewport quando não há resultados.
   - Borda superior sutil (`1px solid var(--border-light)`) dentro de `.site-footer-inner`, alinhada à largura útil no desktop (`1024px` e `1440px`), e centralizada no tablet (`768px`) e mobile (`360px`) com suporte automático aos temas claro e escuro via tokens CSS.

3. **Internacionalização Completa (`static/i18n.js`):**
   - Mantidas as chaves `ariaFooter` e `footerRights` nos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), verificadas por paridade e ausência de links no `pytest`.

## Alternativas Descartadas

- **Navegação duplicada (`filtros`, `resultados`, `topo ↑`) no rodapé:** descartada por repetir os mesmos destinos já acessíveis no cabeçalho fixo.
- **Frases genéricas extensas ou links externos no rodapé:** descartados por preferência do projeto por uma assinatura discreta e limpa.

## Consequências

- **Positivas:** Rodapé minimalista, não repetitivo, sem links redundantes, consistente em claro/escuro e sem impacto visual no grid de filtros.
- **Negativas / Pontos de atenção:** Caso se deseje exibir links ou informações legais adicionais no futuro, o layout `.site-footer-inner` precisará ser expandido mantendo compatibilidade responsiva.
