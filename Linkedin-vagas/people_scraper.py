import math
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote as encode
from datetime import datetime
from time import sleep

PEOPLE_URL = 'https://www.linkedin.com/search/results/people/'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

people_status = {
    "is_searching": False,
    "progress": 0,
    "status_message": "Pronto para iniciar",
    "log_messages": [],
    "results": [],
    "total_people": 0,
    "collected_people": 0
}

def log_message(message: str) -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    entry = f"{timestamp} - {message}"
    people_status["log_messages"].append(entry)
    print(entry)

def update_progress(progress: float, message: str) -> None:
    people_status["progress"] = int(progress)
    people_status["status_message"] = message
    log_message(message)

def build_people_params(keywords: str, start: int = 0) -> str:
    params = {
        'keywords': keywords or '',
        'origin': 'SWITCH_SEARCH_VERTICAL',
    }
    if start:
        params['page'] = str(start // 10 + 1)
    query = '&'.join([f"{k}={encode(v)}" for k, v in params.items() if v is not None])
    return f"?{query}"

def fetch_people_page(keywords: str, start: int = 0):
    uri = PEOPLE_URL + build_people_params(keywords, start)
    log_message(f"Buscando: {uri}")
    try:
        res = requests.get(uri, headers=HEADERS, timeout=30)
        if not res.ok:
            log_message(f"HTTP {res.status_code}; retornando vazio")
            return []
        soup = BeautifulSoup(res.text, 'html.parser')
        people = []
        # Heurística: coletar anchors para perfis '/in/'
        links = soup.find_all('a', href=lambda h: isinstance(h, str) and '/in/' in h)
        seen = set()
        for a in links:
            href = a.get('href')
            if not href or href in seen:
                continue
            seen.add(href)
            # Tentar extrair nome do texto do anchor ou vizinhos
            name = (a.get_text(strip=True) or '').strip()
            if not name:
                parent_text = a.parent.get_text(" ", strip=True) if a.parent else ''
                name = parent_text[:80]
            # Construir card básico
            person = {
                'name': name or 'Nome não disponível',
                'headline': '',
                'location': '',
                'link': 'https://www.linkedin.com' + href if href.startswith('/') else href,
                'type': 'person'
            }
            # Heurísticas adicionais: procurar headline/location próximas
            container = a.find_parent(['div','li'])
            if container:
                headline_el = container.find(['div','span'], string=lambda s: isinstance(s, str) and len(s) > 0)
                if headline_el:
                    txt = headline_el.get_text(" ", strip=True)
                    if txt and (len(txt) > 0) and txt != name:
                        person['headline'] = txt[:140]
            people.append(person)
            if len(people) >= 10:
                break
        return people
    except Exception as e:
        log_message(f"Erro ao buscar página: {e}")
        return []

def simulate_people(keywords: str, hiring_only: bool, hiring_keywords: list[str]):
    base = [
        {
            'name': 'CTO - Tech Company',
            'headline': 'CTO | Liderança de engenharia | contratando devs',
            'location': 'Brasil',
            'link': 'https://www.linkedin.com/in/exemplo-cto',
            'type': 'person'
        },
        {
            'name': 'Head de Tecnologia',
            'headline': 'Head de Engenharia | hiring software engineers',
            'location': 'São Paulo, SP',
            'link': 'https://www.linkedin.com/in/exemplo-head',
            'type': 'person'
        },
        {
            'name': 'Tech Recruiter',
            'headline': 'Tech Recruiter | recrutando para vagas frontend e backend',
            'location': 'Remoto',
            'link': 'https://www.linkedin.com/in/exemplo-recruiter',
            'type': 'person'
        },
        {
            'name': 'CTO - Startup Fintech',
            'headline': 'CTO | Growth | inovação | time em expansão',
            'location': 'Rio de Janeiro, RJ',
            'link': 'https://www.linkedin.com/in/exemplo-fintech',
            'type': 'person'
        },
    ]
    if hiring_only:
        kws = [k.lower() for k in hiring_keywords]
        def is_hiring(p):
            h = (p.get('headline') or '').lower()
            return any(k in h for k in kws)
        base = list(filter(is_hiring, base))
    # Adaptar ao termo de busca no título/headline
    out = []
    for p in base:
        cp = dict(p)
        if keywords:
            cp['headline'] = f"{cp['headline']} | relacionado a {keywords}"
        out.append(cp)
    return out

def search_people_thread(keywords: str, location: str, hiring_only: bool, hiring_keywords: list[str], limit_people: int):
    people_status["is_searching"] = True
    people_status["progress"] = 0
    people_status["log_messages"] = []
    people_status["results"] = []

    try:
        update_progress(5, "Preparando busca de pessoas...")
        collected = []

        # Tentativa de busca real (pode exigir login do LinkedIn)
        pages = 2
        for page in range(pages):
            if not people_status["is_searching"]:
                break
            update_progress(10 + int(70 * (page / max(1, pages))), f"Coletando página {page+1}/{pages}")
            real = fetch_people_page(keywords, start=page * 10)
            collected.extend(real)
            sleep(1.5)

        # Fallback simulado se vazio
        if not collected:
            update_progress(80, "Usando resultados simulados")
            default_hiring_keywords = hiring_keywords or ["contratando", "hiring", "recrutando"]
            collected = simulate_people(keywords, hiring_only, default_hiring_keywords)

        # Filtro por hiring_only nas capturas reais
        if hiring_only and collected:
            kws = [k.lower() for k in (hiring_keywords or ["contratando","hiring","recrutando"])]
            def is_hiring(p):
                h = (p.get('headline') or '').lower()
                return any(k in h for k in kws)
            collected = list(filter(is_hiring, collected))

        if limit_people > 0:
            collected = collected[:limit_people]

        people_status["results"] = collected
        people_status["collected_people"] = len(collected)
        update_progress(100, f"Concluído: {len(collected)} pessoas encontradas")
    except Exception as e:
        people_status["status_message"] = f"Erro: {e}"
        log_message(f"Erro: {e}")
    finally:
        people_status["is_searching"] = False
