# ADR 014 — Trava de Limite de Coleta em 25 a 50 Vagas (Padrão 25)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Anteriormente, o seletor de **Limite de vagas** oferecia as opções `25`, `50`, `75` e `Sem restrição` (com teto de até `250` vagas em `UNLIMITED_JOBS_CAP`). Como o scraper realiza requisições individuais ao endpoint público `/jobs-guest/jobs/api/jobPosting/<id>` do LinkedIn por vaga coletada, lotes maiores (75 a 250 requisições em sequência rápida) aumentam significativamente a probabilidade de rate limit (`HTTP 429`) e bloqueios anti-bot (`HTTP 999`/`403`), sobretudo em IPs de VPS.

## Decisão

1. **Interface e Cliente (`templates/index.html`, `static/i18n.js`, `static/script.js`):**
   - Removidas as opções `75` e `Sem restrição` (e suas chaves `limit75` / `limitUnlimited` nos 8 idiomas em `static/i18n.js`).
   - `#limit_jobs` agora oferece exclusivamente **`25` (padrão)** e **`50`**.
   - `getFormData()` em `static/script.js` aplica clamp seguro para manter `limit_jobs` sempre no intervalo `[25, 50]`.

2. **Trava no Back-end (`app.py`, `scraper.py`):**
   - Definidos `MIN_LIMIT_JOBS = 25`, `DEFAULT_LIMIT_JOBS = 25`, `MAX_LIMIT_JOBS = 50` e `UNLIMITED_JOBS_CAP = MAX_LIMIT_JOBS` em `app.py`, e `MIN_LIMIT_JOBS = 25`, `MAX_LIMIT_JOBS = 50`, `UNLIMITED_JOBS_CAP = MAX_LIMIT_JOBS` em `scraper.py`.
   - `_parse_limit()` em `app.py` e `get_job_count()` / `search_jobs_thread()` em `scraper.py` aplicam clamp estrito entre `25` e `50`: valores ausentes ou `<= 0` retornam `25`, strings legadas (`"unlimited"`, `"all"`, `"sem_restricao"`) retornam `50`, e qualquer inteiro fora da faixa é limitado a `[25, 50]`.

## Alternativas Descartadas

- **Manter `75` e `250` disponíveis apenas na UI avançada:** descartado pois o usuário optou por proteção direta contra excesso de requisições automáticas por busca.

## Consequências

- **Positivas:** Redução drástica do volume de requisições por busca no LinkedIn, menor risco de `429`/`999` e respostas mais previsíveis mesmo em ambientes restritos.
- **Negativas / Pontos de atenção:** Cada busca retorna no máximo 50 vagas (antes de qualquer filtragem em abas), garantindo que clientes legados que enviem `limit_jobs` acima de 50 ou `"unlimited"` recebam no máximo 50 sem erro HTTP.
