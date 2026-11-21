# ADR 010 — "Cargo ou Palavra-chave" Opcional Mediante Filtro Mínimo Selecionado

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Anteriormente, tanto o front-end (`static/script.js`) quanto o back-end (`POST /search` em `app.py`) exigiam o preenchimento obrigatório de `keywords`. Isso impedia explorar vagas amplas em um país, região, janela de publicação, nível de experiência ou modalidade de trabalho sem digitar um termo de busca (por exemplo, "todas as vagas de Estágio Remotas no Brasil nos últimos 3 dias").

## Decisão

1. **Validação Condicional no Back-end (`app.py` em `start_search`):**
   - `keywords` passou a ser validada após o parsing dos demais filtros.
   - A busca sem `keywords` é aceita sempre que houver ao menos um filtro de seleção ativo: `location` (país/estado/cidade), `max_date`, `place`/`work_mode`, `experience_level`, `job_type` ou `easy_apply`.
   - `sort_by` e `limit_jobs` **não** contam como filtro ativo por possuírem valores padrão sempre selecionados (`"R"` e `25`), preservando o erro `HTTP 400` (`errNoKeyword`) quando o formulário é enviado vazio (compatibilidade integral com `tests/test_app.py::test_search_validation`).

2. **Compatibilidade com o Coletor (`scraper.py`):**
   - `build_params()` já omitia o parâmetro `keywords` da query string quando vazio (`if keywords:`), mantendo URLs válidas para o endpoint do LinkedIn com `geoId`, `f_TPR`, `f_WT` e `f_E`.

3. **Interface e Internacionalização (`templates/index.html`, `static/script.js`, `static/i18n.js`):**
   - Atualizada `handleSearch()` em `static/script.js` com a mesma regra do servidor (exigindo `keywords` ou ao menos um de `location`, `max_date`, `experience_level`, `work_mode`).
   - Rótulo `labelKeywords` atualizado nos 8 idiomas com indicação explícita de campo opcional (ex.: `"Cargo ou Palavra-chave (opcional)"`) e mensagem `errNoKeyword` atualizada nos 8 idiomas orientando a preencher cargo/palavra-chave ou selecionar ao menos um filtro.

## Alternativas Descartadas

- **Liberar busca 100% vazia sem nenhum filtro:** descartado porque enviaria consulta genérica sem país, data ou perfil ao LinkedIn, gerando resultados irrelevantes e desperdiçando requisições de detalhe.
- **Contar `sort_by` / `limit_jobs` como filtros:** descartado pois já vêm pré-selecionados por padrão e tornariam o envio acidental sempre válido.

## Consequências

- **Positivas:** Permite descoberta exploratória por país, senioridade, modalidade ou data sem restringir por palavra-chave, mantendo proteção contra buscas totalmente vazias.
- **Negativas / Pontos de atenção:** Buscas sem palavra-chave tendem a retornar maior volume no LinkedIn; o seletor de `Limite de vagas` (padrão `25`, teto `250`) continua limitando o lote coletado.
