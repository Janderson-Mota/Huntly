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
- **Filtros Neutros por Padrão:** Nenhum filtro começa pré-selecionado. Suporte a **Data de publicação**, **Nível de experiência**, **Modalidade de trabalho** (`Remoto`, `Híbrido`, `Presencial`) e **Tipo de contrato**, além de sugestões de cargos em TI por idioma.
- **Internacionalização (8 Idiomas):** Português (`pt`), Inglês (`en`), Espanhol (`es`), Francês (`fr`), Italiano (`it`), Alemão (`de`), Russo (`ru`) e Chinês (`zh`). Rótulos, datas relativas, metadados estruturados, status de busca, erros e sugestões de cargos seguem o idioma escolhido (e o cabeçalho `Accept-Language` acompanha a busca), preservando título e descrição originais das vagas.
- **Tema Claro/Escuro e Responsividade:** Alternância de tema persistida em `localStorage`, marcação de vagas já visualizadas (`huntly_seen_jobs`, até 300 IDs), paginação (9 cards por página), modal de detalhes e layout adaptado para `360px`, `768px`, `1024px` e `1440px`.
- **Filtro Rápido e Exportação:** Filtragem instantânea nos cards carregados e download em **CSV** (UTF-8 com BOM e proteção contra fórmula injection CWE-1236) ou **JSON**.

## Arquitetura e Estrutura

```text
huntly/
├── app.py              # Servidor Flask, validação de payload, cabeçalhos de segurança e rotas HTTP
├── scraper.py          # Coleta paginada (10 vagas/página) no LinkedIn, geoId, pós-filtro e detalhes
├── state.py            # SearchState thread-safe em memória com isolamento de execuções por run_id
├── templates/
│   └── index.html      # Interface principal (com suporte a data-i18n e tema)
├── static/
│   ├── i18n.js         # Dicionários completos nos 8 idiomas
│   ├── script.js       # Estado da UI, polling otimizado, modal, paginação e parser de metadados/datas
│   └── styles.css      # Estilos e breakpoints responsivos (640px, 900px, 1120px+)
├── tests/              # Suíte de testes unitários (pytest)
└── docs/
    ├── analise/        # Relatórios de auditoria (@auditor e @frontend) e prints de referência
    └── decisoes/       # Registros de Decisão Arquitetural (ADRs 001 a 004)
```

## Rotas HTTP

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/` | Renderiza a interface principal (`templates/index.html`). |
| `POST` | `/search` | Valida parâmetros (`type`, `keywords`, `location`, `max_date`, `job_type`, `place`, `experience_level`, `limit_jobs`, `lang`), inicia uma nova execução isolada por `run_id` e retorna `message` / `message_code`. |
| `POST` | `/stop` | Interrompe a busca ativa (`jobs_state.stop()`). |
| `GET` | `/status` | Retorna o progresso e metadados de `SearchState` (`status`, `status_code`, `status_params`, `progress`, `collected_jobs`). Aceita `?include_results=0` para omitir a lista completa `results` durante o polling. |
| `GET` | `/results` | Retorna a lista atual de vagas coletadas em memória. |
| `GET` | `/job/<job_id>` | Retorna os detalhes de uma vaga específica presente nos resultados atuais (`404` se não encontrada). |
| `GET` | `/export/csv` | Exporta os resultados válidos em CSV (UTF-8 BOM), aceitando `?lang=` para localizar o prefixo do nome do arquivo. |
| `GET` | `/export/json` | Exporta os resultados válidos em JSON, aceitando `?lang=` para localizar o prefixo do nome do arquivo. |

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
