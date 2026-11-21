# ADR 003 — Controle de Concorrência (`run_id`), Polling Otimizado e Paginação do Scraper

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

A auditoria identificou quatro problemas no fluxo de execução e coleta:
1. O endpoint guest `seeMoreJobPostings/search` retorna 10 vagas por página, mas `search_jobs_thread()` paginava com passo `25` (`page * 25`), pulando 15 vagas por página e truncando a coleta padrão (`limit_jobs=100`) em ~40 vagas.
2. `get_job_ids_per_page()` fazia dois parses completos com `BeautifulSoup` por página; `get_job_detail()` abortava na 1ª falha quando `fallback` era `None`; `keywords` substituía `jr` sem fronteira de palavra (`\b`); e `_extract_description_text` unia parágrafos sem separador (`get_text(strip=True)`).
3. `SearchState` (`state.py`) não possuía identificador de execução (`run_id`): após `stop()`, workers em voo de uma busca anterior podiam sobrescrever resultados ou status de uma nova busca, e `finish()` podia sobrescrever `"stopped"`.
4. `GET /status` serializava todo o array `results` (com descrições completas) a cada 900 ms, embora `pollResults()` descartasse `data.results` e chamasse `GET /results` em seguida.

## Decisão

1. **Paginação de 10 itens e parse único (`scraper.py`):**
   - Definir `PAGE_SIZE = 10` avançando `start_offset += max(len(new_ids), PAGE_SIZE)` com margem extra de páginas quando há pós-filtro de país.
   - Unificar extração de IDs e resumos em `_parse_page_jobs()` (um único `BeautifulSoup` por página).
   - Usar `re.sub(r"\bjr\.?\b", "junior", ...)` na normalização de `keywords`, corrigir o retry em `get_job_detail()` para tentar novamente mesmo sem `fallback`, e extrair descrições com `_extract_description_text()` (`separator="\n"` preservando quebras de parágrafo).
2. **Isolamento por `run_id` (`state.py`, `scraper.py`, `app.py`):**
   - `SearchState` incrementa `self._run_id` a cada `start()` (mantendo retorno booleano `True`/`False`).
   - `is_run_active(run_id)`, `stop`, `finish`, `fail`, `log`, `update_progress`, `set_total` e `set_results` ignoram mutações vindas de um `run_id` obsoleto; `finish()` não sobrescreve estados já encerrados (`not self._is_searching`).
3. **Polling enxuto (`app.py`, `state.py`, `static/script.js`):**
   - `GET /status` aceita `?include_results=0` (`snapshot(include_results=False)`), mantendo `include_results=1` como padrão para retrocompatibilidade.
   - O frontend consulta `/status?type=jobs&include_results=0` e só chama `/results` quando `collected_jobs` muda ou a busca alcança estado terminal.
4. **Hardening auxiliar (`app.py`, `static/script.js`):**
   - `TEMPLATES_AUTO_RELOAD` e `SEND_FILE_MAX_AGE_DEFAULT` são condicionados a `FLASK_DEBUG=true`.
   - `getSafeUrl()` no frontend passa a aceitar exclusivamente URLs `https://`.

## Alternativas Descartadas

- **Introduzir banco de dados (SQLite/Redis) e fila distribuída (Celery):** descartado nesta etapa por exceder o escopo aprovado e aumentar complexidade operacional na VPS; mitigado com documentação explícita de `gunicorn -w 1 --threads 4`.
- **Remover `results` do `/status` sem flag:** descartado para preservar compatibilidade com clientes ou testes que consultam `/status` diretamente.

## Consequências

- **Positivas:** Elimina perda de 15 vagas/página, reduz tráfego duplicado durante polling, evita sobrescrita concorrente entre execuções e melhora a legibilidade das descrições no modal.
- **Negativas / Pontos de atenção:** Como `jobs_state` permanece um singleton em memória no processo Python, o deploy em produção exige obrigatoriamente **1 único worker** com múltiplas threads (`-w 1 --threads 4`).
