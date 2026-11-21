# Huntly

Buscador web de vagas públicas em tecnologia no LinkedIn, desenvolvido em Python e Flask, com filtros avançados, interface em 8 idiomas, tema claro/escuro, tradução local offline e exportação em CSV e JSON.

## Funcionalidades

- **Busca Flexível e Filtros Avançados:** Pesquise por cargo, palavra-chave ou apenas combinando filtros — localização em cascata (país, estado e cidade), data de publicação, nível de experiência (incluindo Estágio, Trainee, Júnior, Pleno, Sênior, Tech Lead e Diretor), modalidade de trabalho (remoto, híbrido e presencial), ordenação e candidatura simplificada.
- **Classificação em Abas:** Organiza automaticamente os resultados entre **Correspondentes** e **Talvez você goste**, com filtro rápido em tempo real para incluir ou excluir termos na aba ativa.
- **Tradução 100% Local e Offline:** Traduz títulos e descrições das vagas localmente usando `argostranslate` (sem depender de APIs pagas ou chaves externas) e adapta termos de busca para o idioma do país selecionado em pesquisas internacionais.
- **Interface Multilíngue e Responsiva:** Suporte a 8 idiomas (Português, Inglês, Espanhol, Francês, Italiano, Alemão, Russo e Chinês), alternância entre tema claro e escuro, paginação, modal de detalhes e marcação de vagas já visualizadas.
- **Exportação:** Download dos resultados da aba atual em **CSV** ou **JSON**.

## Tecnologias

- **Back-end:** Python 3.10+, Flask, Requests, BeautifulSoup4, Argos Translate
- **Front-end:** HTML5, CSS3, JavaScript (Vanilla)
- **Testes:** Pytest

## Como Executar Localmente

1. Clone o repositório e acesse a pasta do projeto:

```bash
git clone https://github.com/Janderson-Mota/Huntly.git
cd Huntly
```

2. Crie e ative um ambiente virtual:

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Baixe os modelos locais de tradução offline (executado apenas uma vez):

```bash
python scripts/setup_translation.py
```

5. Inicie a aplicação:

```bash
python app.py
```

6. Abra no navegador:

```text
http://localhost:5000
```

## Estrutura do Projeto

```text
huntly/
├── app.py                        # Servidor Flask e rotas da aplicação
├── scraper.py                    # Coleta de vagas públicas e filtragem
├── state.py                      # Controle de estado da busca em andamento
├── translator.py                 # Tradução offline local com cache
├── scripts/
│   └── setup_translation.py      # Download dos pacotes de idioma do Argos Translate
├── templates/
│   └── index.html                # Interface principal
├── static/
│   ├── i18n.js                   # Traduções da interface em 8 idiomas
│   ├── script.js                 # Interações, filtros, paginação e tema
│   └── styles.css                # Estilos e responsividade
└── tests/                        # Suíte de testes automatizados
```

## Testes

```bash
python -m pytest -v
```

## Aviso

O Huntly consulta exclusivamente páginas públicas de vagas e não possui qualquer vínculo com o LinkedIn.

## Licença

Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
