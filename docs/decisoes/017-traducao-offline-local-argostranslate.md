# ADR 017 — Tradução 100% Local e Offline com Argos Translate (Pivô em Inglês)

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Os provedores externos gratuitos anteriormente usados (`translate.googleapis.com` sem chave e cota anônima da API pública do MyMemory) aplicavam bloqueios `HTTP 429 Too Many Requests` após múltiplas requisições no mesmo IP compartilhado, degradando a confiabilidade da tradução de cards em ambiente local e em VPS.

## Decisão

1. **Dependência e Script Idempotente de Instalação (`requirements.txt`, `scripts/setup_translation.py`):**
   - Adicionado `argostranslate>=1.9.6` em `requirements.txt`.
   - Criado `scripts/setup_translation.py` (`ensure_argos_packages`, `build_required_pairs`), que atualiza o índice do Argos Translate e baixa/instala apenas pacotes ausentes no formato bidirecional com o Inglês (`en`) como pivô para os demais idiomas (`en <-> {pt, es, fr, it, de, ru, zh, ja}` — evitando combinações N×N desnecessárias).

2. **Motor Offline em `translator.py` (Zero Chamadas HTTP de Tradução):**
   - Removidas todas as requisições HTTP externas, pools de sessão e controles de cooldown para APIs terceiras.
   - `TARGET_LANG_MAP` e `normalize_target_lang()` mapeiam os 8 idiomas da interface e variantes regionais (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`/`zh-CN`, `ja`, `pt-BR`, `en-US`, etc.) para os códigos ISO-639-1 do Argos.
   - Tradutores resolvidos via `argostranslate.translate.get_installed_languages()` e `from_lang.get_translation(to_lang)` ficam em cache em `_argos_translators`, aproveitando o roteamento automático por pivô em Inglês do próprio Argos (ex.: `pt -> en -> de`, `pt -> en -> zh`, `pt -> en -> ja`).
   - Adicionada detecção conservadora de idioma-fonte (`detect_source_language()`, diferenciando inclusive `ja` por Hiragana/Katakana vs `zh` por caracteres CJK e aplicando heurística para textos bilíngues) e dica contextual por vaga combinando título + descrição.
   - Mantido o cache em duas camadas (RAM `OrderedDict` + SQLite persistente em modo WAL `huntly_translation_cache.sqlite3`, até 5.000 entradas) consultado em lote antes de invocar o modelo CTranslate2, além de fallback seguro para o texto original quando algum pacote ainda não estiver instalado (sem gravar falhas em cache).

3. **Preservação de Originais e Troca Reativa de Idioma (`static/script.js`):**
   - Atualizada a chave de cache persistente no navegador (`huntly_translations_cache_v5`) e mantidos `original_title`, `original_excerpt` e `original_description` separados de `_translations[lang]` para que trocas de idioma no seletor disparem 1 lote único `POST /translate` apenas para vagas ainda não cacheadas no idioma escolhido.

## Alternativas Descartadas

- **Baixar todos os 56+ pares diretos N×N entre todos os idiomas:** descartado por consumo excessivo de disco e banda quando o pivô bidirecional em `en` atende todos os pares.
- **Depender de API pública gratuita ou chave paga obrigatória:** descartado por sujeição a rate limit (`429`) e custo externo recorrente.

## Consequências

- **Positivas:** Tradução 100% offline, privada e imune a bloqueios `429` ou falhas de rede após executar `python scripts/setup_translation.py`; leituras repetidas em SQLite/RAM respondem em poucos milissegundos.
- **Negativas / Pontos de atenção:** Exige instalação prévia dos modelos locais (`python scripts/setup_translation.py`) no ambiente e consome memória RAM adicional para os pesos CTranslate2/Stanza durante a primeira tradução de cada par.
