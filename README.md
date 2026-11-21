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
- **Filtros Avançados, Multisseleção e Limite de Vagas:** Suporte a **Data de publicação**, multisseleção para **Nível de experiência** (`Estágio`, `Júnior`, `Pleno`, `Sênior`, `Diretor`) e **Modalidade de trabalho** (`Remoto`, `Híbrido`, `Presencial`), **Ordenar por** (`Mais relevantes` / `Mais recentes` via `sortBy=R|DD`), **Limite de vagas** (`25` padrão, `50`, `75` ou `Sem restrição` com teto técnico seguro de `250`) e checkbox de **Candidatura Simplificada** (`easy_apply` → `f_AL=true`), além de **51 sugestões de cargos em TI** traduzidas nos 8 idiomas. No desktop (`1024px` e `1440px`), todos os filtros organizam-se em exatamente 2 fileiras.
- **Validação Rigorosa Pós-Coleta em Duas Abas:** Analisa metadados e semântica de título/descrição para classificar todo o lote coletado em **Correspondentes** (atende estritamente localização, experiência e modalidade selecionadas) e **Talvez você goste** (demais vagas relacionadas retornadas pelo LinkedIn, incluindo `Não aplicável` ou níveis/modalidades distintos), evitando falsos positivos sem descartar oportunidades.
- **Internacionalização (8 Idiomas) e Tradução de Cards:** Português (`pt`), Inglês (`en`), Espanhol (`es`), Francês (`fr`), Italiano (`it`), Alemão (`de`), Russo (`ru`) e Chinês (`zh`). Toda a interface (rótulos, países, abas, datas relativas, metadados estruturados, status, erros e sugestões) segue o idioma escolhido com `Accept-Language` dinâmico. Quando o usuário seleciona um idioma diferente de `pt`, o título e a descrição dos cards/modal são traduzidos automaticamente via `POST /translate` com cache LRU no backend, cache de sessão no navegador (`sessionStorage`) e fallback seguro para o texto original.
- **Tema Claro/Escuro e Responsividade:** Alternância de tema persistida em `localStorage`, marcação de vagas já visualizadas (`huntly_seen_jobs`, até 300 IDs), paginação (9 cards por página), modal de detalhes e layout adaptado para `360px`, `768px`, `1024px` e `1440px`.
- **Filtro Rápido, Exclusão de Termos e Exportação por Aba:** Filtragem instantânea para inclusão e campo negativo em tempo real para **excluir palavras-chave** na aba ativa (insensível a acentos, sobre textos originais e traduzidos), além de download em **CSV** (UTF-8 com BOM e proteção contra fórmula injection CWE-1236) ou **JSON** respeitando a aba ativa (`?tab=`).

## Arquitetura e Estrutura

```text
huntly/
├── app.py              # Servidor Flask, validação de payload, cabeçalhos de segurança e rotas HTTP
├── scraper.py          # Coleta paginada (10 vagas/página) no LinkedIn, geoId, pós-filtro e detalhes
├── state.py            # SearchState thread-safe em memória com isolamento de execuções por run_id
├── translator.py       # Tradução sob demanda (title/description) com cache LRU thread-safe e fallback
├── templates/
│   └── index.html      # Interface principal (com suporte a data-i18n e tema)
├── static/
│   ├── i18n.js         # Dicionários completos nos 8 idiomas (incluindo 51 sugestões de cargos)
│   ├── script.js       # Estado da UI, polling otimizado, modal, paginação, cache de tradução e parser i18n
│   └── styles.css      # Estilos, dropdown multi-select, abas e breakpoints (640px, 960px, 1120px+)
├── tests/              # Suíte de testes unitários (pytest)
└── docs/
    ├── analise/        # Relatórios de auditoria (@auditor e @frontend) e prints de referência
    └── decisoes/       # Registros de Decisão Arquitetural (ADRs 001 a 007)
```

## Rotas HTTP

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/` | Renderiza a interface principal (`templates/index.html`). |
| `POST` | `/search` | Valida parâmetros (`type`, `keywords`, `location`, `max_date`, `sort_by`, `easy_apply`, `job_type`, `work_mode`/`place`, `experience_level`, `limit_jobs` com teto `250`, `lang`), inicia uma nova execução isolada por `run_id` e retorna `message` / `message_code`. |
| `POST` | `/stop` | Interrompe a busca ativa (`jobs_state.stop()`). |
| `GET` | `/status` | Retorna o progresso e metadados de `SearchState` (`status`, `status_code`, `status_params`, `progress`, `collected_jobs`). Aceita `?include_results=0` para omitir a lista completa `results` durante o polling. |
| `GET` | `/results` | Retorna as vagas coletadas; aceita opcionalmente `?tab=matched|recommended|all`, `?q=` e `?exclude=`. |
| `GET` | `/job/<job_id>` | Retorna os detalhes de uma vaga específica presente nos resultados atuais (`404` se não encontrada). |
| `POST` | `/translate` | Traduz sob demanda `title` e `description` de até 20 vagas (`lang` + `job_ids` ou `items`) com cache LRU no servidor e fallback seguro para o original. |
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
