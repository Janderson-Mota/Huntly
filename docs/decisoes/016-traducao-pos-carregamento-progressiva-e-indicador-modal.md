# ADR 016 — Tradução Pós-Carregamento em Lote Único, Fallback MyMemory e Indicador no Modal

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Nos testes manuais em ambiente local, duas falhas foram observadas quando o navegador disparava diversas chamadas seguidas a `POST /translate` após `GET /results?type=jobs`:

1. **Disparos múltiplos e saturação upstream (`429`):** Dividir a página em sub-lotes de 3 cards + prefetch da página seguinte + re-disparos em trocas de página/aba gerava dezenas de chamadas simultâneas e múltiplas requisições concorrentes em `translator.py` contra `translate.googleapis.com`, levando ao retorno `HTTP 429 Too Many Requests` (`/sorry/index`).
2. **Fallback silencioso e envenenamento de cache:** Quando o tradutor falhava, `translator.py` devolvia o texto original com `source_lang: None` e `was_translated: False` em `HTTP 200`, e `static/script.js` gravava essa resposta não traduzida em `translationCache` / `sessionStorage`, impedindo novas tentativas e deixando os cards no idioma original. Além disso, o lote máximo de `/translate` estava limitado a `20` itens frente às buscas de `25–50` vagas.

## Decisão

1. **Requisição única em lote pós-busca e preservação em memória (`static/script.js`, `app.py`):**
   - Elevado o limite de lote de `20` para `50` vagas em `/translate` (`app.py`) e em `MAX_BATCH_ITEMS` (`translator.py`).
   - Removido o chunking em blocos de 3 e os gatilhos automáticos dentro de `renderFilteredResults()` e `prefetchTimeout`: agora o front-end dispara **1 única chamada `POST /translate`** em `mode=preview` após o término da busca (`pollResults()` / `stopSearch()`) ou ao trocar o idioma da página (`applyLanguage()`), cobrindo até 50 vagas coletadas nas duas abas (`Correspondentes` e `Talvez você goste`).
   - Cada tradução válida (`isValidTranslationEntry`, exigindo `source_lang || was_translated`) passa a ser salva tanto em `localStorage` (`huntly_translations_cache_v4`, até 250 entradas) quanto diretamente no objeto da vaga em `searchResults` via `item._translations[lang]`. Trocar de aba, paginar ou aplicar filtros rápidos/exclusão lê do estado em memória com **zero** chamadas extras.
   - Respostas de fallback em falha (`source_lang: null, was_translated: false`) nunca são gravadas no cache do navegador nem no back-end.

2. **Fallback automático MyMemory + cooldown e cache persistente (`translator.py`):**
   - Reduzido `TRANSLATE_WORKERS` de `8` para `4` para suavizar concorrência upstream.
   - Adicionado cooldown global de 300s para Google `gtx` após `HTTP 429`/`403` e fallback automático para a API pública REST do MyMemory (`https://api.mymemory.translated.net/get`, com sub-chunks de até 450 caracteres e detecção heurística conservadora de idioma-fonte `_detect_source_language()`), mantendo compatibilidade com os mocks de `requests.post` na suíte de testes e fallback seguro para o texto original quando ambos os provedores falharem.
   - Adicionada persistência leve do cache LRU em arquivo temporário (`huntly_translation_cache_v1.json`, desativada durante execuções `pytest`) para evitar re-traduções entre reinícios locais.

3. **Indicador discreto sob demanda no modal (`templates/index.html`, `static/styles.css`, `static/i18n.js`, `static/script.js`):**
   - Ao abrir **Ver detalhes** (`openJobModal`), caso `job.description` exista e ainda não tenha `is_full: true` em cache, `#modal-translating-indicator` é exibido enquanto `POST /translate` (`mode=full`) traduz a descrição completa, atualizando modal e card e ocultando o indicador em `finally` / `closeModal()`.

## Alternativas Descartadas

- **Manter sub-lotes concorrentes por página e prefetch automático:** descartado por multiplicar chamadas simultâneas e provocar bloqueios `429` no tradutor gratuito.
- **Persistir entradas sem tradução (`source_lang: null`) no cache do navegador:** descartado por cristalizar falhas temporárias e impedir tradução após recuperação.

## Consequências

- **Positivas:** Cada busca gera no máximo 1 chamada em lote `POST /translate` para os cards (e no máximo 1 chamada pontual sob demanda no modal para descrições longas), com atualização imediata dos cards em tela, preservação garantida ao trocar de aba/filtrar e resiliência automática via MyMemory quando Google limita requisições.
- **Negativas / Pontos de atenção:** Em buscas de até 50 vagas com títulos/resumos inéditos em cold start via MyMemory, a única chamada em lote pode levar alguns segundos até retornar todos os cards de uma vez e atualizar a grade simultaneamente.
