# ADR 007 — Multisseleção de Filtros, Validação Pós-Coleta em Duas Abas e Limite de Vagas

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

Mesmo após os avanços anteriores na filtragem de país e ordenação, identificaram-se três limitações práticas no fluxo de busca:
1. Os campos de **Nível de experiência** e **Modalidade de trabalho** permitiam apenas uma opção por vez (impedindo combinações comuns como `"Estágio + Júnior"` ou `"Remoto + Híbrido"`).
2. O endpoint público de busca do LinkedIn devolve frequentemente vagas que contradizem os filtros solicitados (por exemplo, filtrar `"Estágio"` e receber vagas com metadado `Pleno-sênior`, `Não aplicável` ou título `"Senior Python Developer"`). Descartar essas vagas silenciosamente reduzia demais o volume útil, enquanto misturá-las degradava a precisão.
3. O limite fixo de `100` vagas não oferecia opções granulares de velocidade vs. volume (`25`, `50`, `75` ou `Sem restrição`), e adicionar um quinto campo na linha de filtros avançados não podia quebrar o grid de filtros para uma 3ª fileira no desktop (`1024px` e `1440px`).

## Decisão

1. **Multisseleção compacta para Experiência e Modalidade (`templates/index.html`, `static/script.js`, `app.py`, `scraper.py`):**
   - Substituídos `#experience_level` e `#place` por componentes dropdown `.multi-select` (`#experience-multiselect` e `#work-mode-multiselect`) com checkboxes clicáveis, resumo dinâmico no botão disparador, contador numérico quando `>= 2` itens estão selecionados e retorno ao estado neutro ("Todos") quando nada está marcado.
   - Em `app.py`, adicionado `_parse_multi_filter()` aceitando listas JSON ou strings únicas/separadas por vírgula (preservando tokens compostos `"3,4"` e `"5,6"` e mantendo retrocompatibilidade para `work_mode` e `place`).
   - Em `scraper.py`, `_flatten_filter_codes()` achata e deduplica códigos enviando parâmetros separados por vírgula ao LinkedIn (`f_E=1,2`, `f_WT=2,3`).

2. **Validação pós-coleta rigorosa e separação em duas abas (`scraper.py`, `app.py`, `static/script.js`):**
   - Implementada classificação determinística `classify_job_match()` combinando três validadores estritos:
     - `job_matches_location()`: valida país (`job_matches_country`) e, quando informados, cidade ou estado/UF (`STATE_ALIASES`).
     - `job_matches_experience()`: valida metadado estruturado (`experience_level_code`) em conjunto com análise semântica multilíngue do título (`detect_title_experience_levels()`), enviando para a segunda aba falsos positivos como `"Senior Developer"`, `"Tech Lead"` ou metadado `"not_applicable"`.
     - `job_matches_work_mode()`: detecta modalidade (`remote`, `hybrid`, `onsite`) com prioridade para termos híbridos e ignorando negações explícitas (ex.: `"não é remoto"`), via critérios HTML ou texto da vaga (`detect_work_mode()`).
   - Cada vaga coletada recebe `match_category`:
     - **Aba 1 (`"Correspondentes"`, `match_category == "matched"`, ativa por padrão):** exibe exclusivamente vagas que atendem estritamente localização, experiência e modalidade selecionadas.
     - **Aba 2 (`"Talvez você goste"`, `match_category == "recommended"`):** preserva as demais vagas relevantes coletadas na busca (outros níveis/modalidades, `"Não aplicável"`, etc.) sem descartar conteúdo potencialmente útil.
   - Barra de filtro rápido (`#quick-filter-input`), exclusão negativa (`#exclude-filter-input`), paginação e exportação (`/results`, `/export/csv`, `/export/json` via `?tab=`, `?q=`, `?exclude=`) operam respeitando a aba ativa e mantendo compatibilidade quando `tab` não é informado.

3. **Seletor "Limite de vagas" com teto técnico seguro (`250`) e grid de 2 fileiras no desktop:**
   - Adicionado `#limit_jobs` com opções `25` (padrão), `50`, `75` e `"Sem restrição"` (`value="unlimited"`).
   - No backend (`app.py` e `scraper.py`), `"unlimited"` ou `0` são convertidos em `UNLIMITED_JOBS_CAP = 250`, protegendo a VPS contra rate limits e timeouts sem alterar a classificação das duas abas sobre todo o lote coletado.
   - Em `static/styles.css`, ajustado o grid para manter exatamente **2 fileiras** em `1024px` e `1440px` (`primary-inputs-grid` na Fileira 1 e `.filters-grid` com `repeat(5, minmax(0, 1fr))` na Fileira 2, rótulos compactos com `.form-group > label` e `@media (max-width: 1120px)` sem colapsar para 3ª fileira; colapso reservado para `<= 960px` e `<= 640px`).

4. **Internacionalização e cobertura de testes:**
   - Todos os novos rótulos, opções, `aria-label`, mensagens de abas e limites traduzidos nos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`).
   - Adicionada suíte dedicada `tests/test_filters_and_tabs.py` mantendo intactos `tests/test_app.py` e `tests/test_scraper.py`.

## Alternativas Descartadas

- **Descartar completamente vagas divergentes dos filtros de experiência/modalidade no backend:** descartado porque endpoints públicos do LinkedIn frequentemente classificam vagas válidas como `"Não aplicável"` ou omitem modalidade estruturada; mover para **"Talvez você goste"** preserva descoberta sem poluir a aba principal **"Correspondentes"**.
- **Enviar solicitação sem teto numérico no `"Sem restrição"` (ex.: 1000 vagas):** descartado pelo alto risco de HTTP `429`/bloqueio no LinkedIn e saturação de threads/timeouts no deploy da VPS; o teto técnico de `250` equilibra amplitude e estabilidade.
- **Usar `<select multiple>` nativo do HTML:** descartado por inconsistência visual entre navegadores e excesso de altura no grid de filtros; o dropdown customizado com checkboxes mantém altura uniforme de `40px` nas 5 colunas do desktop.

## Consequências

- **Positivas:** Maior precisão nos resultados principais (**Correspondentes**), transparência na separação de sugestões relacionadas (**Talvez você goste**), multisseleção combinada de níveis e modalidades e layout compacto de 2 fileiras no desktop (`1024px` e `1440px`) em todos os 8 idiomas.
- **Negativas / Pontos de atenção:** Quando a vaga não informa modalidade no título, localização ou descrição e o usuário filtra estritamente por uma modalidade, a vaga vai por segurança para **"Talvez você goste"** evitando falsos positivos em **"Correspondentes"**.
