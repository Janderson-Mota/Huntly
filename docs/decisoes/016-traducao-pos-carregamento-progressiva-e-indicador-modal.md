# ADR 016 — Tradução Pós-Carregamento em Lote Único, Cache SQLite, Execução Paralela e Mapeamento Completo

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Para que a tradução assíncrona funcione de maneira consistente em todos os idiomas da interface (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`/`zh-CN`, além de variantes regionais e `ja`), reaja instantaneamente ao trocar o seletor de idioma sem perder os textos originais da vaga e elimine gargalos de ~10 segundos em lotes de `25–50` cards, era necessário:

1. Normalizar explicitamente os códigos de idioma na rota `POST /translate` (`app.py`) e em `translator.py` (`zh-CN`, `pt-BR`, `ja`, etc.).
2. Preservar `original_title`, `original_excerpt` e `original_description` separados das traduções em memória (`item._translations[lang]`) em `static/script.js`.
3. Reduzir drasticamente a latência do lote com consulta em lote ao cache persistente antes da rede, agrupamento em blocos com delimitador seguro e fallback paralelo com `ThreadPoolExecutor(max_workers=10)`.

## Decisão

1. **Mapeamento explícito de idiomas e detecção (`translator.py`, `app.py`):**
   - Expandido `TARGET_LANG_MAP` com `"pt"`, `"en"`, `"es"`, `"fr"`, `"it"`, `"de"`, `"ru"`, `"zh": "zh-CN"` e `"ja": "ja"`, com normalizador público `normalize_target_lang()` consumido diretamente em `POST /translate` (aceitando variantes como `pt-BR`, `en-US`, `zh-CN`, `zh-Hans`, `ja-JP` e rejeitando apenas códigos inválidos com HTTP 400).
   - Adicionada detecção específica de japonês (Hiragana/Katakana `\u3040-\u30ff`) distinta de caracteres CJK chineses.

2. **Preservação de originais e re-tradução imediata na troca de idioma (`static/script.js`):**
   - `normalizeJobRecord()` fixa `original_title`, `original_excerpt` e `original_description` em cada vaga carregada em `searchResults`, mantendo as traduções isoladas em `item._translations[lang]` e `localStorage` (`huntly_translations_cache_v4`).
   - Ao alterar `#lang-select`, `applyLanguage()` hidrata imediatamente qualquer tradução já em cache para o novo idioma e dispara **1 única chamada em lote `POST /translate`** apenas para as vagas ainda não cacheadas naquele idioma, mantendo o filtro rápido operando simultaneamente sobre originais e traduzidos.
   - Respostas falhas sem tradução válida nunca são gravadas no cache; trocar de aba (`matched` / `recommended`) ou filtrar localmente não dispara novas requisições.

3. **Cache persistente SQLite + empacotamento por delimitador + 10 workers (`translator.py`):**
   - Substituído o JSON temporário por banco SQLite persistente em `huntly_translation_cache.sqlite3` (modo WAL, limite `5000` entradas, configurável via `configure_cache_db()`), consultado em lote (`_sqlite_batch_get`) **antes** de qualquer chamada HTTP e atualizado em bloco (`_sqlite_batch_put`) ao final do lote.
   - Para chamadas vivas ao Google `gtx`, textos curtos são empacotados em blocos com delimitador indexado (`[[[HUNTLY_SEP_n]]]`, até 12 textos / 3.600 caracteres por bloco) e validados por contagem e ordem exata dos marcadores; em caso de delimitador corrompido ou execução individual, o pipeline executa em paralelo com `ThreadPoolExecutor(max_workers=10)`.
   - Mantidos cooldown de 300s após `HTTP 429`/`403` do Google e fallbacks para MyMemory REST (suportando `MYMEMORY_EMAIL` opcional para maior cota diária) e `LIBRETRANSLATE_URL` opcional.

## Alternativas Descartadas

- **Loop sequencial por vaga em `POST /translate`:** descartado pois `25–50` requisições em série levavam ~10 segundos e saturavam o endpoint síncrono.
- **Sobrescrever `job.title` / `job.description` in-place no objeto recebido:** descartado pois corrompia a comparação original ao alternar para múltiplos idiomas seguidos ou aplicar o filtro rápido sobre termos originais.

## Consequências

- **Positivas:** Suporte completo a todos os idiomas com códigos normalizados, alternância fluida entre idiomas no cabeçalho reaproveitando o cache local sem custo de rede, filtro preservado em textos originais/traduzidos e aceleração paralela (`10` workers) somada a cache SQLite em lote.
- **Negativas / Pontos de atenção:** Provedores gratuitos públicos sem chave (Google `gtx` anônimo e cota anônima do MyMemory) ainda podem aplicar `HTTP 429` por IP compartilhado após muitas requisições no mesmo dia; quando ocorre, o aplicativo preserva os textos originais com segurança sem envenenar o cache e permite ampliar cota via variáveis de ambiente (`MYMEMORY_EMAIL` ou `LIBRETRANSLATE_URL`).
