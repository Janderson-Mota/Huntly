# Auditoria Full-Stack — Huntly (`@auditor`)

**Branch analisada:** `melhorias` (com alteração local não commitada em `.agents/workflows/rodar.md`)  
**Data da auditoria:** 2026-11-20  
**Escopo:** Análise somente leitura de ponta a ponta (`templates/`, `static/`, `app.py`, `scraper.py`, `state.py`, `tests/`, `requirements.txt`).

---

## 1. Linha de Base (`pytest`) e Ambiente

Comando executado: `python -m pytest -v`

- **Resultado:** **`17 passed, 348 warnings in 0.92s`**
  - `tests/test_app.py`: **9 testes passando** (`test_home_route`, `test_status_valid_and_invalid_types`, `test_search_validation`, `test_security_headers_present`, `test_csv_formula_injection_is_neutralized`, `test_export_empty_returns_400`, `test_export_csv_and_json_with_results`, `test_job_detail_endpoint`, `test_generate_csv_empty`).
  - `tests/test_scraper.py`: **8 testes passando** (`test_calculate_time_range`, `test_build_params_neutral_keyword_only`, `test_build_params_encodes_properly`, `test_build_params_supports_cascade_location_and_advanced_filters`, `test_get_job_ids_per_page_stops_after_max_retries`, `test_get_job_ids_per_page_parses_urns`, `test_search_state_bounds_logs_and_prevents_double_start`, `test_sanitize_job_url_blocks_unsafe_schemes`).
- **Ambiente observado:** Python `3.13.0rc3`, Flask `2.0.1`, Werkzeug `2.0.1`, requests `2.32.3`, BeautifulSoup4 `4.12.3`.
- **Divergência de ambiente:** `requirements.txt:1` exige `Flask>=3.0.0`, porém o ambiente global ativo possui `Flask 2.0.1` / `Werkzeug 2.0.1`, o que gera os 348 `DeprecationWarning` de `ast.Str` no `werkzeug/routing.py` em Python 3.13.

---

## 2. Arquitetura e Dados

### 2.1 Fluxo Ponta a Ponta

1. **Frontend (`templates/index.html`, `static/script.js`, `static/i18n.js`, `static/styles.css`):**
   - Renderizado via `GET /` (`app.py:62-64`).
   - O usuário preenche cargo/palavra-chave, localização em cascata (`country`, `state`, `city`) e filtros avançados (`job_max_date`, `experience_level`, `place`, `job_type`).
   - `getFormData()` (`static/script.js:351-369`) monta o payload JSON e dispara `POST /search` (`static/script.js:386-390`).
   - Após `200 OK`, `pollResults()` (`static/script.js:404-427`) faz polling a cada `900ms` em `GET /status?type=jobs` seguido de `GET /results?type=jobs` (`static/script.js:406-411, 429-435`), renderizando 9 cards por página (`static/script.js:171`) com filtro rápido client-side, modal de detalhes e exportação CSV/JSON (`static/script.js:304-309`).
2. **Backend HTTP (`app.py`):**
   - `POST /search` (`app.py:67-124`) valida tipos e limites (`_parse_limit`, `_parse_str`, `_parse_str_list`, `_validate_search_type`), aciona `jobs_state.start()` (`app.py:94`) e cria uma `threading.Thread(..., daemon=True)` executando `search_jobs_thread` (`app.py:112-113`).
   - `POST /stop` (`app.py:126-140`) valida `type` e chama `jobs_state.stop()`.
   - `GET /status` (`app.py:142-147`) retorna `jobs_state.snapshot()`.
   - `GET /results` (`app.py:150-155`) retorna `jobs_state.get_results()`.
   - `GET /job/<job_id>` (`app.py:158-163`) busca linearmente o `id` em `jobs_state.get_results()`.
   - `GET /export/csv` e `GET /export/json` (`app.py:209-233`) filtram itens sem `"error"`, sanitizam fórmulas (`_sanitize_csv_cell`, `app.py:166-170`) e devolvem download com UTF-8 BOM no CSV.
   - `add_security_headers` (`app.py:20-25`) injeta `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Referrer-Policy: strict-origin-when-cross-origin`.
3. **Motor de Coleta (`scraper.py`):**
   - Usa endpoints públicos guest do LinkedIn (`scraper.py:14-17`: `INIT_URL`, `PAGE_URL`, `POST_URL`, `PUBLIC_JOB_URL`) com `DEFAULT_HEADERS` (`scraper.py:19-26`), `MAX_RETRIES = 3`, `REQUEST_TIMEOUT = 20`, `DETAIL_WORKERS = 2` (`scraper.py:28-30`).
   - `search_jobs_thread` (`scraper.py:324-451`) coleta IDs e resumos em páginas de `PAGE_URL` e depois busca detalhes individuais em `POST_URL` usando `ThreadPoolExecutor(max_workers=2)` e `requests.Session` isolada por thread via `threading.local()` (`scraper.py:411-446`).
4. **Estado e Persistência (`state.py` + `localStorage`):**
   - **Banco de dados:** **Não existe banco de dados** (SQLite, PostgreSQL ou Redis). Toda a persistência de busca no servidor reside em memória na instância singleton `jobs_state = SearchState(...)` (`scraper.py:32`), protegida por `threading.Lock` (`state.py:14`).
   - **Esquema em memória (`state.py:17-24`):** `_is_searching`, `_status` (`idle | running | stopped | complete | error`), `_progress` (`0..100`), `_status_message`, `_log_messages` (`deque(maxlen=200)`), `_results` (`List[Dict[str, Any]]`), `_total`, `_collected`.
   - **Esquema de cada vaga (`scraper.py:262-269, 298-314`):**
     - Campos base: `id`, `title`, `company`, `location`, `time`, `link`, `description`.
     - Critérios dinâmicos de `li.description__job-criteria-item` (`scraper.py:308-312`), ex.: `"Nível de experiência"`, `"Tipo de emprego"`, `"Setores"`.
   - **Persistência no navegador (`static/script.js:115-121`):** `localStorage` armazena `huntly_last_filters` (gravado em `saveCurrentFilters`, nunca lido), `huntly_seen_jobs` (até 300 IDs), `huntly_lang`, `huntly_theme`, além da chave não usada `huntly_recent_keywords`.

### 2.2 Pontos Frágeis de Arquitetura, Concorrência e Performance

1. **Singleton global em memória (`scraper.py:32`, `state.py:10`):**
   - Impede uso concorrente por múltiplos usuários (uma busca bloqueia todas as outras com HTTP 400 em `app.py:94-95` e todos compartilham os mesmos resultados).
   - Impede múltiplos workers no Gunicorn (`gunicorn -w N`, com `N > 1`): cada processo teria seu próprio `jobs_state`, causando `400`/`404` ou status inconsistente entre requisições. Exige obrigatoriamente `-w 1 --threads 4` (ou similar) enquanto não houver store externo/sessão.
2. **Polling redundante e tráfego duplicado (`app.py:142-155`, `state.py:97-108`, `static/script.js:406-412`):**
   - `GET /status` chama `jobs_state.snapshot()`, que serializa e retorna **todo o array `results`** (incluindo descrições HTML/texto completas de todas as vagas já coletadas).
   - Logo em seguida, `pollResults()` (`static/script.js:410-411`) ignora `data.results` e dispara `GET /results?type=jobs`, transferindo e parseando os mesmos dados duas vezes a cada 900 ms.
3. **Race condition entre `stop()`, workers em voo e nova busca (`state.py:46-52`, `scraper.py:424-448`):**
   - `jobs_state.stop()` apenas marca `_is_searching = False` sem esperar as threads terminarem (`REQUEST_TIMEOUT = 20`, `scraper.py:29`). Se o usuário parar e iniciar imediatamente outra busca, threads remanescentes da busca anterior podem chamar `jobs_state.set_results(jobs)` (`scraper.py:438`), `update_progress` (`scraper.py:441`) ou `finish` (`scraper.py:448`), corrompendo o estado da busca nova (falta um identificador de geração/`run_id` no `SearchState`).
   - Além disso, após sair do loop `as_completed` (`scraper.py:429-443`), `scraper.py:448` chama `jobs_state.finish(...)` incondicionalmente, podendo sobrescrever um `stopped` caso `stop()` ocorra entre a última iteração e a linha `448`.
4. **Duplo parse de HTML por página (`scraper.py:214-217`):**
   - `_parse_job_summaries(res.text)` (`scraper.py:245`) cria um `BeautifulSoup(html, "html.parser")` e extrai todos os `div[data-entity-urn]`; em seguida `get_job_ids_per_page` (`scraper.py:217-223`) cria um segundo `BeautifulSoup(res.text, "html.parser")` apenas para extrair os mesmos IDs.
5. **Configurações de desenvolvimento fixas em `app.py:14-15`:**
   - `TEMPLATES_AUTO_RELOAD = True` e `SEND_FILE_MAX_AGE_DEFAULT = 0` estão ativos mesmo quando `FLASK_DEBUG` é `false` (`app.py:237`), impedindo cache de arquivos estáticos em produção.
6. **Persistência parcial de filtros (`static/script.js:116, 217-229, 347, 382`):**
   - `saveCurrentFilters()` grava no `localStorage` ao iniciar busca e `resetFilters()` apaga a chave, mas nenhuma função lê `huntly_last_filters` ao carregar a página.

---

## 3. Bugs e Lógica (Causa Raiz e Evidências)

### [P0 — CRÍTICO] Filtro de país: selecionar "Brasil" retorna vagas dos EUA / outros países

**Causa raiz identificada e comprovada em 3 elos:**
1. **Valor enviado em português pelo frontend (`static/script.js:37, 238-243, 283-287`):**
   - Em `LOCATION_DATA` (`static/script.js:36-110`), todos os países não lusófonos estão em inglês (`"United States"`, `"Canada"`, `"United Kingdom"`, `"Germany"`, `"Spain"`, `"Ireland"`), mas o Brasil está cadastrado com a chave `"Brasil"` (`static/script.js:37`).
   - Ao selecionar apenas o país "Brasil", `buildLocationString()` (`static/script.js:283-287`) envia `location: "Brasil"`.
2. **Backend repassa `location=Brasil` cru ao LinkedIn, sem `geoId` e sem normalização (`scraper.py:69-114`):**
   - `build_params()` (`scraper.py:98-101`) envia apenas `location=Brasil` (sem `geoId`).
   - O endpoint público guest do LinkedIn não resolve a palavra isolada `"Brasil"` para o Brasil. **Prova empírica executada contra o LinkedIn em 2026-11-20:**
     - `GET .../jobs/search?keywords=Python&location=Brasil` → LinkedIn resolveu para **`geoId=103644278` (Estados Unidos!)**.
     - `GET .../jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=Python&location=Brasil` (com e sem `f_WT=2` Remoto) → **HTTP 200, 10/10 vagas nos Estados Unidos** (`Aurora, Colorado, Estados Unidos`, `San Francisco, Califórnia, Estados Unidos`, `Morrisville, Carolina do Norte, Estados Unidos`, etc.).
     - `GET .../jobs/search?keywords=Python&location=Brazil` → LinkedIn resolveu para **`geoId=106057199` (Brasil)**, retornando `Rio de Janeiro e Região`, `Minas Gerais, Brasil`, `São Paulo e Região`.
     - `GET .../seeMoreJobPostings/search?...&location=Brasil&geoId=106057199` e `location=Brazil&geoId=106057199` (inclusive com `f_WT=2` Remoto) → **HTTP 200, 10/10 vagas exclusivamente no Brasil** (`Rio de Janeiro e Região`, `Minas Gerais, Brasil`, `São Paulo, SP`, `Florianópolis, SC`, `Curitiba, PR`, `Brasília, DF`).
3. **Ausência de validação pós-coleta de país (`scraper.py:245-270, 435-439`):**
   - Mesmo com `geoId` ou `location` com estado/cidade, o LinkedIn pode incluir vagas expandidas/remotas fora do país alvo caso o parser não valide a localização retornada.
   - **Nota de implementação importante:** O `geoId` do país **só deve ser enviado quando apenas o país estiver selecionado** (sem estado/cidade), pois um `geoId` nacional pode sobrepor o filtro de estado/cidade. Quando houver estado/cidade (ex.: `"Minas Gerais, Brasil"`), normalizar o sufixo `"Brasil"` → `"Brazil"` (ou manter compatibilidade sem `geoId` nacional).
   - **`geoId`s validados empiricamente no LinkedIn nesta auditoria:**
     - `Brasil` (`Brazil`): `106057199`
     - `Portugal`: `100364837`
     - `United States`: `103644278`
     - `Canada`: `101174742`
     - `United Kingdom`: `101165590`
     - `Ireland`: `104738515`
     - `Germany` e `Spain`: retornaram `HTTP 429` durante a sondagem; seus `geoId`s precisam ser confirmados antes ou no início da implementação (não adivinhar sem checar).

### [P1 — ALTO] Paginação do scraper pula 15 vagas por página (`scraper.py:358, 378`)

- Nos testes reais contra `PAGE_URL` (`seeMoreJobPostings/search`), cada página retornou **`count=10`** vagas (`li`).
- Porém `scraper.py:358` calcula `num_pages = max(1, math.ceil(total_jobs / 25))` e `scraper.py:378` solicita `start = page * 25`.
- Com o `limit_jobs = 100` padrão (`static/script.js:367`), o loop executa apenas `page = 0, 1, 2, 3` (`start = 0, 25, 50, 75`), coletando no máximo ~40 vagas únicas e descartando os intervalos `10..24`, `35..49`, `60..74`, `85..99`.

### [P1 — ALTO] Mensagens da API/Progresso e Metadados de Vagas fixos em PT-BR (`app.py`, `state.py`, `scraper.py`, `static/script.js`)

- Todas as mensagens de erro e progresso exibidas na UI (`static/script.js:394, 408, 416, 699`) vêm como strings em português do backend:
  - `app.py:32, 36, 44, 52, 58, 74, 82, 95, 118, 123, 132, 139, 163, 203`
  - `state.py:20, 39, 51`
  - `scraper.py:344, 360, 391, 405, 442, 448, 451`
- `scraper.py:25` envia `Accept-Language: pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7` fixo. Consequentemente:
  - `job.time` (ex.: `"Há 3 dias"`) e os critérios `li.description__job-criteria-item` (`"Nível de experiência"`, `"Tipo de emprego"`, `"Setores"`) vêm sempre em português.
  - `static/script.js:601, 625-626, 671-676` acessa literalmente `job["Tipo de emprego"]` e `job["Nível de experiência"]` e exibe seus valores brutos sem tradução.

### [P2 — MÉDIO] Substituição sem fronteira de palavra em `keywords` (`scraper.py:95`)

- `cleaned = cleaned.replace("jr", "junior").replace("Jr", "Junior")` altera substrings dentro de palavras (ex.: `mjre` → `mjuniore`), falha para `"JR"` ou `"jr."` e distorce termos que contenham `jr`. Deve usar regex com fronteira `\b` e case-insensitive (`\bjr\.?\b`).

### [P2 — MÉDIO] Falha prematura de retry em `get_job_detail` (`scraper.py:316`)

- O loop `for attempt in range(2):` (`scraper.py:282`) possui `if attempt == 1 or not fallback:` na linha `316`. Quando `fallback` é `None` (chamada direta sem resumo), qualquer exceção na 1ª tentativa aborta sem realizar a 2ª tentativa.

### [P2 — MÉDIO] Sobreposição nos valores de `experience_level` (`templates/index.html:131-132`)

- `<option value="3,4">` (Pleno) e `<option value="4">` (Sênior) compartilham o código `4` (Mid-Senior level do LinkedIn). Trata-se de escolha herdada do commit `2045b68`, mas vale sinalizar se o Jandin deseja manter ou ajustar.

### [P3 — BAIXO] Consistência de Segurança, Cache e Exportação

- `static/script.js:575-579`: `getSafeUrl` aceita `http://`, enquanto `scraper.py:240` restringe a `https://*.linkedin.com`.
- `app.py:206`: nome do arquivo exportado hardcoded em português (`vagas_linkedin_<timestamp>.csv/.json`).
- `app.py:14-15`: `TEMPLATES_AUTO_RELOAD = True` e `SEND_FILE_MAX_AGE_DEFAULT = 0` sempre ativos fora de debug.

---

## 4. Limpeza (Arquivos, Dependências e Código Morto — Somente Listagem)

> Nenhum item abaixo foi apagado nesta fase. A remoção depende de aprovação explícita do Jandin.

### 4.1 Arquivos e Pastas
- **Nenhum arquivo ou pasta morta versionada** foi encontrado no repositório (`app.py`, `scraper.py`, `state.py`, `templates/index.html`, `static/i18n.js`, `static/script.js`, `static/styles.css`, `tests/test_app.py`, `tests/test_scraper.py`, `README.md`, `requirements.txt`, `LICENSE`, `.gitignore`, `.gitattributes`, `.agents/`).
- `.pytest_cache/` é diretório transitório de execução já ignorado em `.gitignore:17`.

### 4.2 Dependências (`requirements.txt`)
- Todas as 4 dependências em `requirements.txt:1-4` são utilizadas (`Flask`, `requests`, `beautifulsoup4`, `gunicorn` para deploy em produção/VPS). Nenhuma dependência morta a remover.
- *Observação:* Alinhar o ambiente virtual/local para `Flask>=3.0.0` conforme `requirements.txt:1` elimina os 348 warnings de `werkzeug` no Python 3.13.

### 4.3 Código Morto / Obsoleto Identificado
1. **4 chaves i18n órfãs nos 8 idiomas (`static/i18n.js`):**
   - `heroTitleStart`, `heroTitleAccent`, `heroSubtitle`, `recentLabel` (resquícios do hero e chips removidos no commit `0b9cb55`).
   - Localização: linhas `6-8, 62` (`pt`), `84-86, 140` (`en`), `162-164, 218` (`es`), `240-242, 296` (`fr`), `318-320, 374` (`it`), `396-398, 452` (`de`), `474-476, 530` (`ru`), `552-554, 608` (`zh`) — total de **32 linhas mortas**.
2. **Chave de storage morta (`static/script.js:117`):**
   - `recentKeywords: "huntly_recent_keywords"` nunca é lida nem gravada.
3. **Bloco de scraping morto em `get_job_count()` (`scraper.py:133-160`):**
   - `_parse_limit()` (`app.py:28-37`) sempre retorna `>= 1` (`default=100`, `max(1, min(value, 500))`), tornando o fallback `limit_jobs <= 0` inalcançável via API (e não há testes chamando `get_job_count`). Pode ser simplificado/removido caso não haja uso futuro planejado para `limit_jobs=0`.
4. **Persistência incompleta `saveCurrentFilters` / `STORAGE_KEYS.filters` (`static/script.js:116, 217-229, 347, 382`):**
   - Grava `huntly_last_filters` no `localStorage`, mas nunca restaura ao iniciar (pendente decisão do Jandin: remover código morto ou implementar restauração).
5. **Parâmetros de UI removidos (`static/script.js:361-362, 366`):**
   - `sort_by: ""`, `distance: ""`, `easy_apply: false` foram removidos da interface no commit `ff853a7`. **Ressalva:** `tests/test_scraper.py:39-74` testa esses argumentos em `scraper.build_params()`, portanto não devem ser removidos de `scraper.py` sem aprovação explícita para ajustar `tests/`.
6. **Duplo parse `BeautifulSoup` em `scraper.py:214-217`:**
   - Eliminar o parse duplicado durante a correção da paginação.
7. **Funcionalidades desatualizadas no `README.md:51`:**
   - Ainda lista "distância máxima, ordenação e candidatura simplificada" (removidos da UI no commit `ff853a7`). Atualizar na etapa do `@documentador`.

---

## 5. Plano de Correção Priorizado (Backend & Arquitetura)

1. **[P0] Corrigir Filtro de País ("Brasil" e demais países):**
   - Normalizar nome canônico do país no backend (`"Brasil"` → `"Brazil"`), mapear `geoId` exato por país quando apenas o país for selecionado (sem estado/cidade), e adicionar filtragem pós-coleta por país/localização para garantir 100% de aderência ao país escolhido (especialmente em buscas do Brasil e remotas).
2. **[P1] Corrigir Paginação e Remover Duplo Parse no Scraper (`scraper.py`):**
   - Ajustar passo de paginação para o tamanho real retornado pelo LinkedIn (`10` ou cálculo dinâmico baseado em `new_ids` até atingir `limit_jobs` / página vazia), eliminando o segundo `BeautifulSoup` por página e corrigindo `attempt` em `get_job_detail` e regex `\bjr\.?\b`.
3. **[P1] Endurecer `SearchState` e Eliminar Polling Duplicado (`state.py`, `app.py`, `scraper.py`, `static/script.js`):**
   - Introduzir `run_id` por busca para impedir que threads antigas sobrescrevam buscas novas após `stop()`.
   - Evitar envio duplicado de `results` em `GET /status` (ou usar `results` já retornado com `count`/hash), além de condicionar `TEMPLATES_AUTO_RELOAD`/`SEND_FILE_MAX_AGE_DEFAULT` a `debug_mode`.
4. **[P1] Internacionalização Estruturada de Status, Erros e Metadados de Vagas (`state.py`, `app.py`, `scraper.py`, `static/i18n.js`, `static/script.js`):**
   - Retornar códigos estruturados (`status_code`, `status_params`, `error_code`) mantendo compatibilidade com os campos textuais atuais para preservar `tests/`.
   - Normalizar/traduzir datas relativas (`job.time`) e metadados estruturados (`Tipo de emprego`, `Nível de experiência`) na UI sem alterar `title` nem `description` da vaga.
5. **[Limpeza] Remover códigos mortos aprovados** (`static/i18n.js`, `static/script.js`, bloco morto de `get_job_count`).

---

## 6. Decisões Pendentes do Jandin

1. **D1 — Persistência de filtros (`huntly_last_filters`):** Remover o código morto que só grava no `localStorage` (mantendo filtros neutros ao abrir, como no commit `bcf53bb`) **ou** implementar restauração automática ao carregar a página? *(Recomendado: remover para manter filtros neutros.)*
2. **D2 — Tradução de Estados/Regiões vs Países:** Traduzir apenas os nomes dos **países** nos 8 idiomas (mantendo estados/cidades no nome local oficial usado pelo LinkedIn) **ou** traduzir também todos os estados estrangeiros? *(Recomendado: traduzir 100% dos países e manter estados/cidades no nome canônico.)*
3. **D3 — Código legado `distance`, `sort_by`, `easy_apply` e `get_job_count`:** Preservar os parâmetros em `scraper.build_params` / `app.py` para manter `tests/test_scraper.py` intacto, e remover apenas o bloco inalcançável de scraping em `get_job_count`? *(Recomendado: sim.)*
4. **D4 — Códigos i18n no backend (`status_code` / `error_code`):** Retornar códigos estruturados além das mensagens atuais para manter 100% de compatibilidade com `tests/` e traduzir tudo em tempo real no navegador? *(Recomendado: sim.)*
5. **D5 — Alteração local em `.agents/workflows/rodar.md`:** Incluir no commit de checkpoint antes de iniciar o Bloco 2?
