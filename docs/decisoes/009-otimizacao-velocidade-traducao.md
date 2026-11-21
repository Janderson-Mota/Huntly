# ADR 009 — Otimização de Velocidade da Tradução (Modo Preview, Keep-Alive e Fast-Path)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Com a tradução automática habilitada para todos os 8 idiomas (incluindo Português, ADR 008), cada página com até 9 cards podia disparar dezenas de requisições HTTP sequenciais ou pouco paralelas no endpoint público do Google Translate:

1. `requests.post(...)` abria uma nova conexão TCP+TLS a cada chamada em `translator.py`.
2. Descrições longas (3.000–10.000 caracteres) eram fatiadas em chunks de `1800` caracteres traduzidos em sequência por vaga, com apenas `TRANSLATE_WORKERS = 4`.
3. Os cards exibem apenas um resumo de 3 linhas (`.card-excerpt`), mas aguardavam a tradução integral da descrição antes de atualizar a página.
4. Textos longos já redigidos no idioma-alvo e títulos idênticos repetidos no mesmo lote ainda realizavam chamadas HTTP redundantes.

## Decisão

1. **Pool HTTP Keep-Alive + Paralelismo Plano em `translator.py`:**
   - Adicionado pool thread-safe de `requests.Session` (`_session_pool`, com `HTTPAdapter` montado em `https://` e `http://`) via `_post_translation()`, mantendo fallback automático para `requests.post` quando mocks de teste interceptam `translator.requests.post`.
   - Elevados `MAX_CHUNK_CHARS` de `1800` para `4500` e `TRANSLATE_WORKERS` de `4` para `8`.
   - Implementada `_translate_texts_parallel()` com deduplicação intra-lote (títulos/textos repetidos no mesmo batch geram no máximo 1 conjunto de chamadas) e execução paralela plana de todos os chunks únicos do lote.

2. **Fast-Path Conservador para Idioma-Alvo (`_is_already_target_language`):**
   - Textos longos (`>= 120` caracteres) claramente escritos no idioma de destino são identificados localmente antes da chamada HTTP (`ru` por razão cirílica, `zh` por ideogramas CJK, e `pt`/`en`/`es`/`fr`/`it`/`de` por conjuntos mutuamente exclusivos de stopwords com margens rigorosas para nunca pular textos curtos, bilíngues ou espanhol ↔ português).

3. **Tradução em Dois Níveis (`mode="preview" | "full"`) e Prefetch (`app.py`, `static/script.js`):**
   - `translate_jobs_batch(..., mode="preview")` e `POST /translate` (`mode` opcional, padrão `"full"`) permitem traduzir apenas os primeiros `PREVIEW_DESC_CHARS = 450` caracteres (cortados em fronteira de palavra via `_build_preview_snippet`) para renderização rápida dos cards, retornando `is_full: false` e `excerpt`.
   - O cliente (`huntly_translations_cache_v3` no `sessionStorage`) solicita `mode: "preview"` para a página visível, agenda prefetch silencioso (180 ms, cancelável) da próxima página após o fim da busca, e solicita `mode: "full"` apenas para a vaga cujo modal de detalhes for aberto (`openJobModal`). Entradas já completas (`is_full: true`) nunca são rebaixadas por respostas `preview`.

## Alternativas Descartadas

- **Limitar permanentemente todas as traduções a 450 caracteres:** descartado pois prejudicaria a leitura completa dentro do modal da vaga.
- **Usar detecção heurística agressiva sem margem de segurança:** descartado pelo risco de deixar anúncios em espanhol ou bilíngues sem tradução quando a interface estivesse em português.

## Consequências

- **Positivas:** Redução expressiva do número de round-trips HTTP, eliminação de handshakes TLS repetidos, exibição rápida dos cards e paginação instantânea nas páginas pré-carregadas.
- **Negativas / Pontos de atenção:** Abrir o modal de uma vaga com descrição > 450 caracteres dispara 1 chamada pontual `mode: "full"` na primeira abertura naquele idioma (armazenada em cache em seguida).
