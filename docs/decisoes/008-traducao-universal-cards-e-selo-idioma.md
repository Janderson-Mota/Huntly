# ADR 008 — Tradução Automática no Idioma Ativo (Incluindo Português) e Selo de Idioma de Origem

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Na versão anterior (ADR 005), a tradução automática de título e descrição das vagas só ocorria quando o idioma selecionado era diferente de `pt` (`en`, `es`, `fr`, `it`, `de`, `ru`, `zh`). Quando a interface estava em Português (`pt`), vagas coletadas em inglês, espanhol ou outros idiomas permaneciam sem tradução nos cards e no modal, além de não indicarem ao usuário que o texto havia sido traduzido automaticamente e a partir de qual idioma original.

## Decisão

1. **Suporte completo a todos os 8 idiomas em `translator.py` e `app.py` (incluindo `pt`):**
   - Adicionado `"pt": "pt"` em `TARGET_LANG_MAP`, tornando `SUPPORTED_LANGS = set(TARGET_LANG_MAP.keys())`.
   - Removido o retorno precoce `if lang == "pt"` em `translate_jobs_batch()` (`translator.py`) e em `POST /translate` (`app.py`), permitindo traduzir para Português vagas coletadas originalmente em qualquer outro idioma.
   - Em `_request_chunk_translation()`, o idioma de origem detectado pela API pública do Google Translate (`payload[2]`) passou a ser capturado, normalizado via `_normalize_lang_code()` e armazenado junto ao texto traduzido no cache LRU em memória (`_cache: OrderedDict[Tuple[str, str], Tuple[str, Optional[str]]]`).
   - Adicionada `translate_text_with_meta()` mantendo `translate_text()` como wrapper retrocompatível.
   - Cada item retornado por `translate_jobs_batch()` inclui agora `source_lang`, `target_lang` e `was_translated` (`True` apenas quando `source_lang != target_lang` e o texto sofreu alteração efetiva), evitando selos redundantes quando a vaga já está no idioma ativo da interface (ex.: vaga em português com interface em português).

2. **Cache v2 no cliente e selo `Origem → Destino` (`static/script.js`, `static/styles.css`, `static/i18n.js`):**
   - Atualizada a chave de sessão para `huntly_translations_cache_v2` em `sessionStorage`, armazenando título/descrição traduzidos e metadados (`source_lang`, `target_lang`, `was_translated`).
   - Removida a restrição `currentLang === "pt"` de `getDisplayJob()` e `ensureTranslations()`, disparando tradução sob demanda por página exibida e modal aberto em qualquer um dos 8 idiomas.
   - Adicionada a chave `translatedFromTo` e o mapa localizado `langNames` nos 8 idiomas (`static/i18n.js`).
   - Cards (`createJobCard`) e modal (`openJobModal`) passaram a exibir a pílula discreta `.translated-badge` (`<i class="bi bi-translate"></i> Traduzido: Inglês → Português`, por exemplo) quando `was_translated` é verdadeiro.

## Alternativas Descartadas

- **Exibir sempre um selo genérico `"Traduzido"` sem informar o idioma de origem:** descartado pois o usuário solicitou transparência do par `origem → destino` (ex.: `Inglês → Português`).
- **Manter exceção especial para `pt`:** descartado porque buscas em países estrangeiros ou vagas bilíngues no Brasil retornam frequentemente anúncios em inglês mesmo com a interface em Português.

## Consequências

- **Positivas:** Vagas em qualquer idioma estrangeiro passam a ser exibidas automaticamente no idioma ativo da página — incluindo Português — mantendo os originais preservados para alternância de idioma/exportação e sinalizando claramente o par traduzido.
- **Negativas / Pontos de atenção:** Quando a interface estiver em `pt`, lotes com muitos anúncios realizados no Brasil/Portugal já em português ainda executam uma verificação inicial por página exibida antes de preencher o cache LRU e `sessionStorage` com `was_translated: false`.
