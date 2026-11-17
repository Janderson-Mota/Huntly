# Huntly — Buscador de Vagas LinkedIn

Aplicação web em Flask para buscar oportunidades em TI no LinkedIn, **com foco em empresas e vagas do Brasil**, além de suporte a exportação em CSV e JSON.

## Requisitos

- **Python 3.10+**

## Instalação e Execução

1. Crie um ambiente virtual:

```bash
python -m venv venv
```

2. Ative o ambiente virtual:

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute a aplicação:

```bash
python app.py
```

5. Acesse no navegador:

```text
http://localhost:5000
```

> Para rodar em modo debug durante desenvolvimento:
> `FLASK_DEBUG=true python app.py` (Linux/Mac) ou `$env:FLASK_DEBUG="true"; python app.py` (PowerShell).

## Funcionalidades e Limitações

- **Busca de Vagas (`jobs`)**: Utiliza a interface pública de vagas do LinkedIn (`jobs-guest`), coletando título, empresa, localização, descrição e critérios com requisições concorrentes e retentativas com backoff.
- **Publicações e Pessoas (`publications` / `people`)**: O LinkedIn restringe a busca pública de publicações e perfis sem autenticação (authwall). Quando bloqueado, o Huntly informa o status nos logs sem retornar dados fictícios.
- **Exportação**: Exporte os resultados coletados em **CSV** (compatível com Excel UTF-8 BOM) ou **JSON**.

## Testes

Execute a suíte de testes unitários com:

```bash
pytest
```
