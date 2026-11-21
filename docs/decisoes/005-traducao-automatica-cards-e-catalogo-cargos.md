# ADR 005 — Tradução Automática dos Cards (`title` e `description`) e Catálogo Ampliado de Cargos de TI

**Status:** Aceito  
**Data:** 2026-11-20

## Contexto

Após a entrega da internacionalização completa da interface (ADR 002), o usuário solicitou duas evoluções na branch `melhorias`:
1. Traduzir automaticamente também o **título (`title`)** e a **descrição (`description`)** das vagas exibidas nos cards e no modal quando o idioma selecionado for diferente de português (`pt`), com cache no backend/sessão e fallback seguro para o texto original em caso de falha.
2. Ampliar o catálogo de sugestões de cargos de TI (`#it-role-suggestions`) cobrindo mais especialidades e mantendo todas traduzidas nos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`).

## Decisão

1. **Módulo de tradução dedicado sem novas dependências (`translator.py`):**
   - Implementado utilizando exclusivamente a biblioteca padrão Python e `requests` (já presente em `requirements.txt`), consultando `https://translate.googleapis.com/translate_a/single` (`client=gtx`, `sl=auto`, `dt=t`) com `TARGET_LANG_MAP` para os 7 idiomas não lusófonos (`en`, `es`, `fr`, `it`, `de`, `ru`, `zh` → `zh-CN`).
   - **Chunking seguro (`_split_chunks`):** descrições longas acima de `1800` caracteres são divididas preferencialmente em quebras de parágrafo (`\n\n`), linha (`\n`) ou espaço.
   - **Cache LRU em memória (`OrderedDict` + `threading.Lock`):** armazena até `MAX_CACHE_ENTRIES = 2000` entradas indexadas por `(tl, sha256(text))`, evitando requisições repetidas entre paginações e buscas.
   - **Fallback seguro:** falhas de rede, timeout ou resposta inesperada retornam o texto original sem lançar exceções e sem gravar falhas no cache.
2. **Rota sob demanda `POST /translate` (`app.py`):**
   - Valida o idioma contra `SUPPORTED_LANGS` (retornando `400` + `errInvalidLanguage` se inválido; retorno imediato `{}` para `pt`).
   - Traduz lotes de até 20 vagas (`translate_jobs_batch` com `ThreadPoolExecutor(max_workers=4)`) a partir de `job_ids` armazenados em `jobs_state` (ou `items` opcionais).
3. **Cache de sessão no cliente sem mutação dos dados originais (`static/script.js`):**
   - O array `searchResults` preserva integralmente os textos originais retornados pelo LinkedIn (permitindo retorno instantâneo ao idioma `pt`).
   - Traduções obtidas via `POST /translate` são armazenadas em um `Map` em memória e persistidas em `sessionStorage` (`huntly_translations_cache`, limitado a 200 entradas), com `translationInFlight` para deduplicar chamadas concorrentes.
   - `getDisplayJob(job)` resolve título/descrição para exibição nos cards, no modal e no filtro rápido (`#quick-filter-input`), mantendo fallback para os originais enquanto a tradução está em andamento ou caso falhe.
4. **Catálogo ampliado de 51 cargos de TI (`static/i18n.js`):**
   - `roleSuggestions` ampliado de 29 para **51 cargos únicos** com paridade 1:1 nos 8 idiomas, cobrindo Frontend, Backend, Full Stack, Mobile (geral, iOS, Android, Flutter/React Native), stacks (Python, Java, Node.js, React, Angular/Vue, TypeScript, .NET/C#, Go/Golang, Rust, PHP, C/C++), Software Engineer, DevOps, SRE, Cloud (AWS/Azure/GCP), Platform Engineer, Data Engineer, Data/BI Analyst, Data Scientist, Machine Learning, AI/LLM, MLOps, QA/Test Automation, InfoSec/Cybersecurity/Pentester-AppSec, Tech Lead, Software/Solutions Architect, PM/PO/Scrum Master, UX/UI & Product Designer, DBA, SysAdmin/Infra, Redes, Suporte Técnico/Help Desk, Analista de Sistemas, ERP/SAP, Game Dev, Embedded/IoT e Estágio em TI.

## Alternativas Descartadas

- **Adicionar bibliotecas externas como `deep-translator` ou `googletrans`:** descartado para não alterar `requirements.txt` nem introduzir dependências pesadas/instáveis no deploy da VPS.
- **Traduzir todas as 100 vagas em lote durante o scraping:** descartado para não aumentar latência na coleta inicial nem desperdiçar requisições em páginas nunca visualizadas pelo usuário (traduzir sob demanda por página exibida e modal é mais rápido e econômico).
- **Sobrescrever diretamente os campos `title` e `description` em `searchResults`:** descartado pois impediria restaurar o texto original ao voltar para `pt` ou alternar entre idiomas.

## Consequências

- **Positivas:** Cards e modais exibem título e descrição traduzidos automaticamente para o idioma selecionado na interface, com resposta instantânea em hits de cache (`sessionStorage` + LRU no backend) e resiliência total em caso de indisponibilidade do serviço de tradução.
- **Negativas / Pontos de atenção:** Caso o endpoint público de tradução imponha rate limit ou fique indisponível, os cards permanecem legíveis no idioma original graças ao fallback seguro. A exportação CSV/JSON (`app.py`) continua exportando os dados coletados originais presentes em `jobs_state`.
