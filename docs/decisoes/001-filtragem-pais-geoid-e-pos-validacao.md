# ADR 001 — Estratégia de Filtragem de País com `geoId` e Pós-Validação

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

Selecionar o país `"Brasil"` na interface enviava `location="Brasil"` diretamente ao endpoint guest do LinkedIn (`seeMoreJobPostings/search`). Conforme comprovado na auditoria (`docs/analise/auditoria_fullstack.md`), o LinkedIn resolvia a string isolada `"Brasil"` para `geoId=103644278` (Estados Unidos), retornando 10/10 vagas norte-americanas mesmo com filtro remoto (`f_WT=2`). Além disso, não havia verificação pós-coleta validando se a localização da vaga retornada pertencia de fato ao país escolhido.

## Decisão

1. **Chave canônica no frontend (`static/script.js`):** `LOCATION_DATA` utiliza `"Brazil"` como chave canônica (exibida ao usuário de forma traduzida nos 8 idiomas via `i18n.js`), mantendo estados e cidades no nome canônico.
2. **Normalização e `geoId` condicional no backend (`scraper.py`):**
   - `normalize_location_for_linkedin()` normaliza aliases do país (último segmento da string separada por vírgulas) para o nome canônico em inglês (`COUNTRY_ALIASES`).
   - `COUNTRY_GEO_IDS` mapeia os 8 países suportados (`Brazil: 106057199`, `Portugal: 100364837`, `United States: 103644278`, `Canada: 101174742`, `United Kingdom: 101165590`, `Germany: 101282230`, `Spain: 105646813`, `Ireland: 104738515`).
   - O parâmetro `geoId` é enviado em `build_params()` **somente quando apenas o país foi informado** (`len(parts) == 1`), pois enviar o `geoId` nacional junto com estado/cidade faz o LinkedIn ignorar o recorte estadual/municipal.
3. **Pós-validação por país (`job_matches_country` em `scraper.py`):**
   - Aplicada em `search_jobs_thread()` tanto sobre os resumos de listagem quanto sobre os detalhes individuais da vaga.
   - Rejeita explicitamente menções a outros países ou regiões supranacionais (`OTHER_COUNTRY_TOKENS`, como `"Latin America"` / `"América Latina"`, `"Estados Unidos"`, etc.), aceita menções ao país alvo nos 8 idiomas (`COUNTRY_TOKENS`), e aplica fallback para estados, capitais, cidades e UFs brasileiras (protegendo UFs homônimas a siglas estaduais dos EUA/Espanha como `AL`, `ES`, `MA`, `MS`, `MT`, `PA`, `SC`).

## Alternativas Descartadas

- **Enviar apenas `location=Brazil` sem `geoId` nem pós-validação:** reduz os falsos positivos iniciais, mas não garante isolamento caso o LinkedIn expanda resultados para vagas remotas/regionais fora do país.
- **Enviar `geoId` do país sempre (mesmo com estado/cidade):** descartado porque o `geoId` nacional sobrescreve o filtro granular de estado/cidade no LinkedIn.
- **Mapear `geoId` estático para cada estado e cidade:** descartado por gerar acoplamento alto e manutenção frágil de centenas de IDs proprietários do LinkedIn.

## Consequências

- **Positivas:** Selecionar `"Brasil"` (com ou sem estado/cidade) retorna exclusivamente vagas brasileiras (validado em teste automatizado e em busca real ao vivo com 100% de aderência).
- **Negativas / Pontos de atenção:** O mapeamento de `COUNTRY_GEO_IDS` e `COUNTRY_REGION_TOKENS` precisa ser atualizado caso novos países sejam adicionados a `LOCATION_DATA`.
