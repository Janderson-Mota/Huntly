# Huntly — Buscador de Vagas LinkedIn

Aplicação web em Flask para buscar oportunidades em TI no LinkedIn, com filtro de país baseado em `geoId` + pós-validação, cascata de localização (país, estado e cidade), filtros avançados, interface multilíngue em 8 idiomas, alternância de tema claro/escuro e exportação em CSV/JSON.

## Requisitos

- **Python 3.10+**
- Dependências em `requirements.txt` (`Flask>=3.0.0`, `requests>=2.32.3`, `beautifulsoup4>=4.12.3`, `gunicorn>=23.0.0`, `argostranslate>=1.9.6`)

## Instalação e Execução Local

1. Crie e ative um ambiente virtual:

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux / Mac
source venv/bin/activate
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Baixe os modelos locais de tradução offline (pivô em inglês para `pt`, `es`, `fr`, `it`, `de`, `ru`, `zh` e `ja`):

```bash
python scripts/setup_translation.py
```

4. Execute a aplicação:

```bash
python app.py
```

5. Acesse no navegador:

```text
http://localhost:5000
```

> Para desenvolvimento com reload automático de templates e cache de estáticos desativado:
> `FLASK_DEBUG=true python app.py` (Linux/Mac) ou `$env:FLASK_DEBUG="true"; python app.py` (PowerShell).

## Funcionalidades

- **Filtro de País Confiável (`geoId` + Pós-Validação):** Normaliza o país selecionado (ex.: `"Brasil"` → `"Brazil"` com `geoId=106057199` quando apenas o país é selecionado) e aplica validação pós-coleta garantindo que as vagas exibidas pertençam ao país filtrado.
- **Localização em Cascata:** Selecione **País → Estado/Região → Cidade (opcional)** com sugestões automáticas para 8 países (`Brazil`, `Portugal`, `United States`, `Canada`, `United Kingdom`, `Germany`, `Spain`, `Ireland`). Os nomes dos países acompanham o idioma da interface enquanto estados e cidades permanecem no formato canônico.
- **Palavra-chave Opcional + Filtros Avançados e Multisseleção:** O campo **Cargo ou Palavra-chave (opcional)** permite buscar apenas combinando filtros (ex.: país, data, experiência ou modalidade), exigindo ao menos um filtro ativo ou palavra-chave. Inclui **Data de publicação**, multisseleção com visual de `<select>` para **Nível de experiência** (`Estágio`, `Trainee`, `Júnior`, `Pleno`, `Sênior`, `Tech Lead`, `Diretor`) e **Modalidade de trabalho** (`Remoto`, `Híbrido`, `Presencial`), **Ordenar por** (`Mais relevantes` / `Mais recentes` via `sortBy=R|DD`), **Limite de vagas** alinhado na mesma linha (`25` padrão ou `50` máximo, com trava em `[25, 50]` no back-end para evitar bloqueios) e **51 sugestões de cargos em TI** traduzidas nos 8 idiomas. No desktop (`1024px` e `1440px`), todos os filtros organizam-se em exatamente 2 fileiras.
- **Enriquecimento por Experiência, Adaptação por País e Validação Semântica Multilíngue:** Adaptação automática da palavra-chave digitada para o idioma predominante do país selecionado (`adapt_keywords_for_location` via `argostranslate`, ex.: `"Desenvolvedor Backend"` nos EUA → `"Backend Developer"`, preservando siglas técnicas universais e mantendo o termo original no Pass 2) combinada com termos de senioridade por país/idioma (`Estágio`, `Internship`, `Praktikum`, `Prácticas`, `Stage`, `Tirocinio`, `インターン`, `实习`, `Tech Lead`) dentro da trava de `25–50` vagas. A pós-validação combina título multilíngue (`Werkstudent`, `Confirmé`, `Lead Technique`, termos japoneses, etc.), declaração explícita na descrição e metadado (`_META_TO_TARGETS`, reconhecendo também níveis marcados como `Não aplicável`) para classificar em **Correspondentes** e **Talvez você goste**.
- **Internacionalização (8 Idiomas) e Tradução 100% Local/Offline em Lote Único:** Português (`pt`), Inglês (`en`), Espanhol (`es`), Francês (`fr`), Italiano (`it`), Alemão (`de`), Russo (`ru`) e Chinês (`zh`/`zh-CN`), além de suporte a variantes de locale e japonês (`ja`) no tradutor. Toda a interface segue o idioma escolhido com `Accept-Language` dinâmico. Os cards preservam `original_title`, `original_excerpt` e `original_description` separados do mapa `_translations[lang]` e são traduzidos em **1 única chamada em lote** (`POST /translate`, até 50 vagas em `mode=preview`), reagindo imediatamente ao trocar `#lang-select` e reaproveitando o cache ao alternar abas ou filtrar; a descrição completa (`mode=full`) é traduzida sob demanda ao abrir **Ver detalhes**. O back-end opera **100% offline via `argostranslate`** (pivô bidirecional em `en`, instalado por `scripts/setup_translation.py`), com cache em duas camadas (RAM + SQLite WAL `huntly_translation_cache.sqlite3`), detecção automática do idioma-fonte e fallback seguro para o texto original quando algum modelo estiver ausente.
- **Tema Claro/Escuro, Cabeçalho e Rodapé Responsivos:** Alternância de tema persistida em `localStorage`, cabeçalho com controles separados e sub-barra de navegação dedicada em telas menores (`<= 640px`), marcação de vagas já visualizadas (`huntly_seen_jobs`, até 300 IDs), paginação (9 cards por página), modal de detalhes, estado vazio compacto, rodapé minimalista sem links repetidos traduzido nos 8 idiomas e layout adaptado para `360px`, `768px`, `1024px` e `1440px`.
- **Filtro Rápido, Exclusão de Termos e Exportação por Aba:** Filtragem instantânea para inclusão e campo negativo em tempo real para **excluir palavras-chave** na aba ativa (insensível a acentos, sobre textos originais e traduzidos), além de download em **CSV** (UTF-8 com BOM e proteção contra fórmula injection CWE-1236) ou **JSON** respeitando a aba ativa (`?tab=`).

## Arquitetura e Estrutura

```text
huntly/
├── app.py              # Servidor Flask, validação de payload, cabeçalhos de segurança e rotas HTTP
├── scraper.py          # Coleta paginada (10 vagas/página), geoId, adaptação por idioma do país e pós-filtro multilíngue
├── state.py            # SearchState thread-safe em memória com isolamento de execuções por run_id
├── translator.py       # Tradução 100% local/offline via argostranslate (pivô en), detecção de idioma e cache SQLite WAL + RAM
├── scripts/
│   └── setup_translation.py  # Script idempotente para baixar modelos bidirecionais (en <-> idiomas) do Argos Translate
├── templates/
│   └── index.html      # Interface principal (com suporte a data-i18n e tema)
├── static/
│   ├── i18n.js         # Dicionários completos nos 8 idiomas (incluindo 51 sugestões de cargos)
│   ├── script.js       # Estado da UI, polling otimizado, modal, paginação, lote único/cache de tradução e i18n
│   └── styles.css      # Estilos, dropdown multi-select, abas, rodapé e breakpoints (640px, 960px, 1120px+)
├── tests/              # Suíte de testes unitários (pytest)
└── docs/
    ├── analise/        # Relatórios de auditoria (@auditor e @frontend) e prints de referência
    └── decisoes/       # Registros de Decisão Arquitetural (ADRs 001 a 018)
```

## Rotas HTTP

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/` | Renderiza a interface principal (`templates/index.html`). |
| `POST` | `/search` | Valida parâmetros (`type`, `keywords` opcional mediante ao menos 1 filtro selecionado, `location`, `max_date`, `sort_by`, `job_type`, `work_mode`/`place`, `experience_level`, `limit_jobs` travado entre `25` e `50` (padrão `25`), `easy_apply`, `lang`), inicia uma nova execução isolada por `run_id` e retorna `message` / `message_code`. |
| `POST` | `/stop` | Interrompe a busca ativa (`jobs_state.stop()`). |
| `GET` | `/status` | Retorna o progresso e metadados de `SearchState` (`status`, `status_code`, `status_params`, `progress`, `collected_jobs`). Aceita `?include_results=0` para omitir a lista completa `results` durante o polling. |
| `GET` | `/results` | Retorna as vagas coletadas; aceita opcionalmente `?tab=matched|recommended|all`, `?q=` e `?exclude=`. |
| `GET` | `/job/<job_id>` | Retorna os detalhes de uma vaga específica presente nos resultados atuais (`404` se não encontrada). |
| `POST` | `/translate` | Traduz localmente (100% offline via `argostranslate`, direto ou por pivô em `en`) até 50 vagas em lote único com normalização de idioma (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`/`zh-CN`, `ja`), cache SQLite WAL + RAM, `mode=preview` ou `mode=full` e fallback seguro para o texto original. |
| `GET` | `/export/csv` | Exporta os resultados válidos em CSV (UTF-8 BOM), aceitando `?lang=`, `?tab=`, `?q=` e `?exclude=`. |
| `GET` | `/export/json` | Exporta os resultados válidos em JSON, aceitando `?lang=`, `?tab=`, `?q=` e `?exclude=`. |

## Testes

Execute a suíte de testes unitários com:

```bash
python -m pytest -v
```

## Deploy na VPS (Gunicorn)

Antes de subir o servidor em uma nova VPS, execute o script idempotente uma única vez para baixar os modelos locais de tradução do Argos Translate (`en <-> idioma`). Como o estado de busca (`SearchState` em `state.py`) reside em memória no processo da aplicação, o servidor WSGI **deve rodar com exatamente 1 worker (`-w 1`)** e múltiplas threads para atender polling e requisições concorrentes sem dessincronização entre processos:

```bash
python scripts/setup_translation.py
gunicorn -w 1 --threads 4 --bind 0.0.0.0:8000 app:app
```

> Caso deseje escalar para múltiplos workers no futuro (`-w > 1`), será necessário mover o estado das buscas de memória local para um store compartilhado (como Redis ou banco de dados).
