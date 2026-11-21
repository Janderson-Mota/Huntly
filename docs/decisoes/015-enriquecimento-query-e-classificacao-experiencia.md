# ADR 015 — Enriquecimento de Query por Experiência e Classificação Semântica Combinada

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Nos testes manuais da branch `melhorias`, foram identificados dois gargalos críticos no funil de coleta e classificação de experiência em `scraper.py`:

1. **Baixa precisão da busca textual no endpoint público do LinkedIn:** Enviar apenas o cargo base (ex.: `"PHP"`) com o filtro lateral `Estágio` (`f_E=1`) ou `Tech Lead` (`f_E=4`) fazia o endpoint público retornar majoritariamente vagas Pleno/Sênior ou mistas, deixando a aba **"Correspondentes"** vazia; por outro lado, enviar `"PHP Estágio"` ou `"PHP Tech Lead"` no parâmetro `keywords` trazia resultados aderentes.
2. **Rejeição indevida por metadado `not_applicable` e ausência de análise combinada:** Vagas legítimas de `"Tech Lead"`, `"Technical Lead"`, `"Estágio"`, `"Júnior"`, `"Pleno"`, `"Sênior"` e `"Diretor"/"Head"` frequentemente vêm marcadas pelo recrutador no LinkedIn com `experience_level_code = "not_applicable"` (ou ausente). Como `job_matches_experience()` barrava `meta_code == "not_applicable"` logo no início — além de não reconhecer variantes como `"Technical Lead"`, `"Líder de Tecnologia"`, `"<stack> Lead"` e declarações explícitas na descrição — essas vagas caíam na aba **"Talvez você goste"**.

## Decisão

1. **Enriquecimento direcionado da query (`build_experience_search_queries` em `scraper.py`):**
   - Criados o mapeamento por localidade `_EXP_SEARCH_TERMS_BY_LOCALE` (`pt`, `es`, `en`), `_infer_search_locale()` e `build_experience_search_queries()`, preservando `build_params()` como codificador puro de URL.
   - Quando há nível(is) de experiência selecionados e o termo ainda não está presente em `keywords` (verificado via `detect_title_experience_levels()` para evitar duplicações como `"Estágio Estágio"`), são geradas consultas direcionadas:
     - **Pass 1 (primárias):** uma consulta por nível selecionado combinando `keywords` ao termo principal do idioma inferido (ex.: `"PHP"` + `["1"]` em `Brazil`/`pt` → `"PHP Estágio"`; `"PHP"` + `["tech_lead"]` → `"PHP Tech Lead"`). Em multisseleção (ex.: `["1", "2"]`), cada nível recebe cota balanceada dentro da trava de `25–50` vagas em `search_jobs_thread()`, em vez de formar uma string impossível em `AND` (`"PHP Estágio Júnior"`).
     - **Pass 2 (secundárias / fallback):** termos equivalentes (ex.: `"PHP Internship"`, `"PHP Líder Técnico"`, `"PHP Technical Lead"`), passagens sem `f_E` para `tech_lead`/`trainee` (capturando vagas marcadas como `Não aplicável`) e a consulta original ampla apenas se ainda faltarem IDs para atingir `effective_limit`.
   - O loop de paginação por consulta rastreia `unseen_in_page` e encerra imediatamente quando não há IDs inéditos, evitando requisições redundantes.

2. **Classificação pós-coleta combinando título, descrição e metadado (`job_matches_experience` em `scraper.py`):**
   - Expandido `_TITLE_EXP_PATTERNS` para cobrir `"Technical Lead"`, `"Tech-Lead"`, `"TechLead"`, `"Líder de Tecnologia"`, `"Liderança Técnica"`, `"Dev Lead"`, `"Lead Dev"`, `"<stack> Lead"` (incluindo `.net lead`) e formas de `"Head"` (`^head`, `head de/of/em`, `head engenharia/tecnologia/...`).
   - Adicionada `detect_description_experience_levels()` com padrões conservadores baseados em prefixos declarativos da vaga (`vaga/cargo/nível/buscamos/procuramos/atuar como/looking for/hiring`), ignorando menções incidentais como `"reporta ao Diretor"` ou `"mentorar juniores"`.
   - Nova precedência em `job_matches_experience()`:
     1. **Título explícito:** se `title_levels & targets`, aprova (`True`) mesmo com `experience_level_code = "not_applicable"` ou ruído de metadado; se houver nível conflitante no título, reprova (`False`).
     2. **Descrição declarativa:** se `desc_levels & targets` (sem conflito no título), aprova quando `experience_level_code` é `not_applicable`/ausente ou compatível; se declarar outro nível conflitante, reprova (`False`).
     3. **Metadado estruturado (`_META_TO_TARGETS`):** fallback quando nem título nem descrição declaram senioridade, mantendo bloqueio para `not_applicable` e para níveis que exigem evidência semântica (`trainee`, `tech_lead`) quando ausentes no texto.

## Alternativas Descartadas

- **Concatenar todos os níveis em uma única string `keywords`:** descartado porque a busca do LinkedIn exige todas as palavras (`AND`), zerando resultados quando o usuário seleciona dois níveis (ex.: `Estágio` + `Júnior`).
- **Alterar `build_params()` para mutar `keywords` automaticamente:** descartado para preservar a previsibilidade da função pura de codificação de URL e a compatibilidade com testes unitários existentes.
- **Aceitar qualquer ocorrência isolada de palavras como `"Júnior"` ou `"Diretor"` na descrição:** descartado para evitar falsos positivos em descrições que apenas citam interlocutores (`"reporta ao Diretor"`, `"mentorar juniores"`).

## Consequências

- **Positivas:** Buscas como `"PHP" + Estágio` e `"Tech Lead"` passam a trazer resultados altamente relevantes já na primeira consulta e são classificadas corretamente na aba **"Correspondentes"** mesmo quando o LinkedIn marca a vaga como `"Não aplicável"`.
- **Negativas / Pontos de atenção:** Em multisseleção com múltiplos níveis, são feitas consultas adicionais no Pass 1 limitadas pela trava de `25–50` vagas totais e interrupção imediata ao não haver novos IDs.
