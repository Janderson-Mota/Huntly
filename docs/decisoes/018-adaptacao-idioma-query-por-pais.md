# ADR 018 — Adaptação Automática da Query de Busca para o Idioma do País Selecionado

**Status:** Aceito  
**Data:** 2026-11-21

## Contexto

Ao buscar vagas em mercados internacionais (ex.: digitar `"Desenvolvedor Backend"` ou filtrar `"Estágio"` ao pesquisar nos **Estados Unidos**, **Alemanha**, **Espanha**, **França**, **Itália**, **Japão** ou **China**), enviar o cargo em português ao endpoint público do LinkedIn retornava resultados escassos ou irrelevantes, pois os anúncios locais utilizam o idioma predominante daquele país (ou termos equivalentes locais como `Internship`, `Praktikum`, `Prácticas`, `Stage`, `Tirocinio`, `インターン` e `实习`).

## Decisão

1. **Mapeamento País → Idioma Predominante (`scraper.py`):**
   - Adicionado `COUNTRY_LANGUAGE_MAP` e `_EXTRA_LOCATION_COUNTRY_MAP` mapeando países e regiões suportadas (`Brazil`/`Portugal` → `pt`; `United States`/`United Kingdom`/`Canada`/`Australia`/`Ireland`/`New Zealand` → `en`; `Spain`/`Mexico`/`Argentina`/`Colombia`/`Chile`/`Peru`/`Uruguay` → `es`; `Germany`/`Austria`/`Switzerland` → `de`; `France`/`Belgium` → `fr`; `Italy` → `it`; `Japan` → `ja`; `China` → `zh`; `Russia` → `ru`).
   - Expandido `_EXP_SEARCH_TERMS_BY_LOCALE` com termos equivalentes de senioridade nos 9 idiomas (incluindo fallback em inglês em mercados multilíngues no Pass 2).

2. **Tradução Local da Palavra-chave Antes da Coleta (`adapt_keywords_for_location` em `scraper.py`):**
   - Antes de construir as queries em `build_experience_search_queries()`, detecta-se de forma estrita (`detect_source_language(..., strict=True)`) o idioma da palavra-chave após mascarar siglas técnicas universais (`Tech Lead`, `DevOps`, `SRE`, `QA`, `Scrum Master`, `Product Owner`, `PHP`, `Python`, etc.).
   - Quando a palavra-chave possui idioma diferente do país selecionado (ex.: `"Desenvolvedor Backend"` buscado em `"United States"`), `translator.translate_text_with_meta()` traduz localmente via `argostranslate` para o idioma alvo (`"Backend Developer"`), mantendo fallback seguro para o termo original no Pass 2 dentro do limite de `25–50` vagas para mercados bilíngues ou caso o modelo falhe.

3. **Classificação Semântica Multilíngue Pós-Coleta (`scraper.py`):**
   - Expandidos `_TITLE_EXP_PATTERNS` e `_TITLE_EXP_NON_LATIN` para reconhecer também `Werkstudent`, `Offre Stage Développeur`, `Confirmé`, `Lead Technique` e termos em japonês (`インターン`, `ジュニア`, `シニア`, `テックリード`, `ディレクター`) na classificação da Aba 1 (`Correspondentes`) sem interferir em falsos cognatos como `"Early Stage"`.

## Alternativas Descartadas

- **Substituir a query original sem guardar fallback no Pass 2:** descartado porque países como Canadá e mercados europeus publicam vagas tanto no idioma local quanto em inglês.
- **Traduzir siglas técnicas isoladas (`PHP`, `Python`, `Tech Lead`):** descartado via detecção `strict=True` e máscara `_UNIVERSAL_TECH_PHRASES_RE` para preservar termos universais de tecnologia.

## Consequências

- **Positivas:** Buscas em português para vagas internacionais passam a alcançar anúncios nativos no idioma do país alvo e seus níveis equivalentes, mantendo a classificação precisa na Aba 1 para títulos em múltiplos idiomas.
- **Negativas / Pontos de atenção:** Caso algum pacote de país específico ainda não tenha sido baixado via `scripts/setup_translation.py`, o sistema recai de forma segura para a query original digitada pelo usuário sem interromper a busca.
