# ADR 002 — Estratégia de Internacionalização (i18n) da Interface e `Accept-Language`

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

Embora existisse um seletor para 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), diversos textos da interface permaneciam presos em português ou inglês misturado: nomes de países no `<select id="country">`, datas relativas (`job.time`), tipo de emprego e nível de experiência nos cards/modal, sugestões de cargo do `<datalist>`, atributos `aria-label`, mensagens de progresso/erro do backend (`state.py`, `app.py`, `scraper.py`), prefixo de exportação e a resposta do modal aberto durante troca de idioma. Além disso, `scraper.py` enviava `Accept-Language: pt-BR` fixo.

## Decisão

1. **Separação estrita entre UI e conteúdo da vaga (`.agents/rules/huntly.md`):**
   - **Interface 100% traduzida (`static/i18n.js` e `static/script.js`):** países (`countries`), sugestões de cargos (`roleSuggestions` com 29 itens nos 8 idiomas), atributos `aria-label` (`data-i18n-aria-label`), estados de vazio/paginação/toolbar, datas relativas (`formatRelativeTime()` com parser multilíngue para todas as 8 línguas), tipo de emprego (`translateEmploymentType`) e nível de experiência (`translateExperienceLevel`).
   - **Conteúdo original preservado:** título (`title`), empresa (`company`) e descrição (`description`) das vagas permanecem exatamente como publicados no LinkedIn.
2. **Códigos estruturados no backend com retrocompatibilidade (`app.py`, `state.py`, `scraper.py`):**
   - `SearchState` e as respostas JSON das rotas HTTP mantêm `status_message`, `error` e `message` originais (preservando 100% da suíte `tests/`) e passam a incluir `status_code`, `status_params`, `error_code` e `message_code`, resolvidos dinamicamente pelo frontend via `i18n.js`.
   - `get_job_detail()` extrai `employment_type_code` e `experience_level_code` a partir dos cabeçalhos/valores nos 8 idiomas, mantendo também as chaves originais para exportação CSV/JSON.
   - `/export/csv` e `/export/json` aceitam `?lang=` para localizar o prefixo do arquivo baixado (fallback `vagas_linkedin`).
3. **`Accept-Language` dinâmico (`scraper.py`):**
   - `POST /search` repassa `lang` ao scraper (`build_headers(lang)`), alinhando o header `Accept-Language` ao idioma escolhido na UI (com fallback `en-US,en;q=0.9`), fazendo com que metadados como `job.location` acompanhem o idioma selecionado.
4. **Países traduzidos vs estados/cidades canônicos (Decisão D2):**
   - Os 8 países são traduzidos em todos os idiomas em `i18n.js`, enquanto estados e cidades permanecem em seus nomes locais/canônicos.

## Alternativas Descartadas

- **Traduzir títulos e descrições das vagas via API externa de tradução:** descartado por violar a regra do projeto de manter o conteúdo original da vaga e por introduzir custo, latência e dependência externa.
- **Substituir completamente `status_message` e `error` por códigos sem texto PT:** descartado para não quebrar contratos de retrocompatibilidade e testes existentes.
- **Traduzir manualmente todos os estados e cidades nos 8 idiomas:** descartado por alto volume de manutenção e baixa utilidade frente aos nomes oficiais aceitos pelo LinkedIn.

## Consequências

- **Positivas:** A troca dinâmica de idioma (inclusive com modal aberto, resultados carregados ou banner de erro/status visível) traduz 100% da interface sem recarregar a página.
- **Negativas / Pontos de atenção:** Novas chaves adicionadas a `static/i18n.js` devem ser replicadas simetricamente em todos os 8 idiomas.
