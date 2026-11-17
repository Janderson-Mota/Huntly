# Huntly — Buscador de Vagas LinkedIn

Aplicação web em Flask para buscar oportunidades em TI no LinkedIn, com filtros avançados por localização (país, estado e cidade), nível de experiência, modalidade, tipo de contrato, candidatura simplificada e exportação em CSV/JSON.

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

## Funcionalidades

- **Localização em Cascata**: Selecione País → Estado/Região → Cidade (opcional) com sugestões automáticas.
- **Filtros Avançados**: Data de publicação, nível de experiência, modalidade (`Remoto`, `Híbrido`, `Presencial`), tipo de contrato, distância máxima, ordenação e candidatura simplificada.
- **Cards Paginados e Abertura Direta**: Visualização em cards (9 por página) com preview da descrição em modal, link direto para a vaga oficial no LinkedIn e marcação automática de vagas já vistas.
- **Filtro Rápido e Exportação**: Filtragem instantânea nos resultados carregados e download em **CSV** (UTF-8 BOM para Excel) ou **JSON**.

## Testes

Execute a suíte de testes unitários com:

```bash
pytest
```
