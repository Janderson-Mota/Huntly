# Huntly — Buscador de Vagas LinkedIn

Aplicação web em Flask para buscar oportunidades em TI no LinkedIn, com filtro de país baseado em `geoId` + pós-validação, cascata de localização (país, estado e cidade), filtros avançados, interface multilíngue em 8 idiomas, alternância de tema claro/escuro e exportação em CSV/JSON.

## Requisitos

- **Python 3.10+**
- Dependências em `requirements.txt` (`Flask>=3.0.0`, `requests>=2.32.3`, `beautifulsoup4>=4.12.3`, `gunicorn>=23.0.0`)

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

3. Execute a aplicação:

```bash
python app.py
```

4. Acesse no navegador:

```text
http://localhost:5000
```

> Para desenvolvimento com reload automático de templates e cache de estáticos desativado:
> `FLASK_DEBUG=true python app.py` (Linux/Mac) ou `$env:FLASK_DEBUG="true"; python app.py` (PowerShell).

## Funcionalidades

- **Filtro de País Confiável (`geoId` + Pós-Validação):** Normaliza o país selecionado (ex.: `"Brasil"` → `"Brazil"` com `geoId=106057199` quando apenas o país é selecionado) e aplica validação pós-coleta garantindo que as vagas exibidas pertençam ao país filtrado.
- **Localização em Cascata:** Selecione **País → Estado/Região → Cidade (opcional)** com sugestões automáticas para 8 países (`Brazil`, `Portugal`, `United States`, `Canada`, `United Kingdom`, `Germany`, `Spain`, `Ireland`). Os nomes dos países acompanham o idioma da interface enquanto estados e cidades permanecem no formato canônico.
- **Palavra-chave Opcional + Filtros Avançados e Multisseleção:** O campo **Cargo ou Palavra-chave (opcional)** permite buscar apenas combinando filtros (ex.: país, data, experiência ou modalidade), exigindo ao menos um filtro ativo ou palavra-chave. Inclui **Data de publicação**, multisseleção com visual de `<select>` para **Nível de experiência** (`Estágio`, `Trainee`, `Júnior`, `Pleno`, `Sênior`, `Tech Lead`, `Diretor`) e **Modalidade de trabalho** (`Remoto`, `Híbrido`, `Presencial`), **Ordenar por** (`Mais relevantes` / `Mais recentes` via `sortBy=R|DD`), **Limite de vagas** alinhado na mesma linha (`25` padrão ou `50` máximo, com trava em `[25, 50]` no back-end para evitar bloqueios) e **51 sugestões de cargos em TI** traduzidas nos 8 idiomas. No desktop (`1024px` e `1440px`), todos os filtros organizam-se em exatamente 2 fileiras.
- **Enriquecimento por Experiência e Validação Semântica Combinada em Duas Abas:** Enriquecimento direcionado da busca com termos dos níveis selecionados por localidade/idioma (ex.: `"PHP Estágio"`, `"PHP Internship"`, `"PHP Tech Lead"`, com consultas separadas e cotas balanceadas em multisseleção dentro da trava de `25–50` vagas) e pós-validação que combina título, declaração explícita na descrição e metadado (`_META_TO_TARGETS`, inclusive reconhecendo `Tech Lead`/`Estágio`/demais níveis quando marcados como `Não aplicável`). Classifica todo o lote em **Correspondentes** e **Talvez você goste**, evitando falsos positivos sem descartar oportunidades.
- **Internacionalização (8 Idiomas) e Tradução em Lote Único Pós-Carregamento:** Português (`pt`), Inglês (`en`), Espanhol (`es`), Francês (`fr`), Italiano (`it`), Alemão (`de`), Russo (`ru`) e Chinês (`zh`). Toda a interface (rótulos, países, abas, datas relativas, metadados estruturados, status, erros, indicador do modal, rodapé e sugestões) segue o idioma escolhido com `Accept-Language` dinâmico. Os cards são exibidos imediatamente após a coleta sem bloquear o scraping e traduzidos em **1 única chamada em lote** (`POST /translate`, até 50 vagas em `mode=preview`), preservando traduções em memória (`_translations`) e `localStorage` ao trocar de aba ou filtrar sem repetir requisições; a descrição completa (`mode=full`) é traduzida sob demanda ao abrir **Ver detalhes** com indicador discreto e fallback seguro. O tradutor conta com Google `gtx`, fallback automático para MyMemory REST (com cooldown em `429`), fast-path local, cache LRU em memória/disco e selo `Traduzido: Origem / Destino`.
- **Tema Claro/Escuro, Cabeçalho e Rodapé Responsivos:** Alternância de tema persistida em `localStorage`, cabeçalho com controles separados e sub-barra de navegação dedicada em telas menores (`<= 640px`), marcação de vagas já visualizadas (`huntly_seen_jobs`, até 300 IDs), paginação (9 cards por página), modal de detalhes, estado vazio compacto, rodapé minimalista sem links repetidos traduzido nos 8 idiomas e layout adaptado para `360px`, `768px`, `1024px` e `1440px`.
- **Filtro Rápido, Exclusão de Termos e Exportação por Aba:** Filtragem instantânea para inclusão e campo negativo em tempo real para **excluir palavras-chave** na aba ativa (insensível a acentos, sobre textos originais e traduzidos), além de download em **CSV** (UTF-8 com BOM e proteção contra fórmula injection CWE-1236) ou **JSON** respeitando a aba ativa (`?tab=`).

## Arquitetura e Estrutura

```text
huntly/
├── app.py              # Servidor Flask, validação de payload, cabeçalhos de segurança e rotas HTTP
├── scraper.py          # Coleta paginada (10 vagas/página) no LinkedIn, geoId, pós-filtro e detalhes
├── state.py            # SearchState thread-safe em memória com isolamento de execuções por run_id
├── translator.py       # Tradução em lote (preview/full), fallback MyMemory, fast-path e cache persistente
├── templates/
│   └── index.html      # Interface principal (com suporte a data-i18n e tema)
├── static/
│   ├── i18n.js         # Dicionários completos nos 8 idiomas (incluindo 51 sugestões de cargos)
│   ├── script.js       # Estado da UI, polling otimizado, modal, paginação, lote único/cache de tradução e i18n
│   └── styles.css      # Estilos, dropdown multi-select, abas, rodapé e breakpoints (640px, 960px, 1120px+)
├── tests/              # Suíte de testes unitários (pytest)
└── docs/
    ├── analise/        # Relatórios de auditoria (@auditor e @frontend) e prints de referência
    └── decisoes/       # Registros de Decisão Arquitetural (ADRs 001 a 016)
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
| `POST` | `/translate` | Traduz sob demanda até 50 vagas em lote único para qualquer um dos 8 idiomas (`pt`, `en`, `es`, `fr`, `it`, `de`, `ru`, `zh`), suportando `mode=preview` (cards) ou `mode=full` (modal, padrão), fallback automático MyMemory em `429`, cache persistente e retorno de `source_lang`, `target_lang`, `was_translated` e `is_full`. |
| `GET` | `/export/csv` | Exporta os resultados válidos em CSV (UTF-8 BOM), aceitando `?lang=`, `?tab=`, `?q=` e `?exclude=`. |
| `GET` | `/export/json` | Exporta os resultados válidos em JSON, aceitando `?lang=`, `?tab=`, `?q=` e `?exclude=`. |

## Testes

Execute a suíte de testes unitários com:

```bash
python -m pytest -v
```

## Deploy na VPS (Gunicorn)

Como o estado de busca (`SearchState` em `state.py`) reside em memória no processo da aplicação, o servidor WSGI **deve rodar com exatamente 1 worker (`-w 1`)** e múltiplas threads para atender polling e requisições concorrentes sem dessincronização entre processos:

```bash
gunicorn -w 1 --threads 4 --bind 0.0.0.0:8000 app:app
```

> Caso deseje escalar para múltiplos workers no futuro (`-w > 1`), será necessário mover o estado das buscas de memória local para um store compartilhado (como Redis ou banco de dados).
