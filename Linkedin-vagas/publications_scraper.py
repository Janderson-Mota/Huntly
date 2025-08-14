import math
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote as encode
from datetime import datetime
from time import sleep

# URLs e headers
PUBLICATIONS_URL = 'https://www.linkedin.com/search/results/content/'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# Estado da busca
publications_status = {
    "is_searching": False,
    "progress": 0,
    "status_message": "Pronto para iniciar",
    "log_messages": [],
    "results": [],
    "total_publications": 0,
    "collected_publications": 0
}

def log_message(message: str) -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    entry = f"{timestamp} - {message}"
    publications_status["log_messages"].append(entry)
    print(entry)

def update_progress(progress: float, message: str) -> None:
    publications_status["progress"] = int(progress)
    publications_status["status_message"] = message
    log_message(message)

# Converte parâmetro de data aceitando múltiplos formatos
# Aceitos (conteúdo): past-24-hours | past-3-days | past-week | past-month
# Aceitos (legado): r24h | r3d | r7d | r1m
# Aceita também YYYY-MM-DD

def calculate_time_range(max_date: str) -> str:
    if not max_date:
        return "past-week"

    linkedin_formats = {"past-24-hours", "past-3-days", "past-week", "past-month"}
    if max_date in linkedin_formats:
        return max_date

    mapping_rel = {
        "r24h": "past-24-hours",
        "r3d": "past-3-days",
        "r7d": "past-week",
        "r1m": "past-month",
    }
    if max_date in mapping_rel:
        return mapping_rel[max_date]

    try:
        if '-' in max_date and len(max_date.split('-')) == 3:
            date_obj = datetime.strptime(max_date, '%Y-%m-%d')
            delta = datetime.now() - date_obj
            if delta.days <= 1:
                return "past-24-hours"
            if delta.days <= 3:
                return "past-3-days"
            if delta.days <= 7:
                return "past-week"
            return "past-month"
    except ValueError:
        pass

    return "past-week"

# Monta query string para a página de busca pública de conteúdo

def build_publication_params(keywords: str, time_range: str, start: int = 0) -> str:
    params = {
        'keywords': keywords or '',
        'datePosted': time_range,
        'origin': 'FACETED_SEARCH',
        'sid': '3x-'
    }
    if start > 0:
        params['start'] = str(start)
    query = '&'.join([f"{k}={encode(str(v))}" for k, v in params.items() if v is not None])
    return f"?{query}"

# Estima quantidade (sem login não há contador estável)

def get_publication_count(keywords: str, time_range: str, limit_publications: int) -> int:
    if limit_publications and limit_publications > 0:
        return limit_publications
    weights = {
        "past-24-hours": 10,
        "past-3-days": 25,
        "past-week": 40,
        "past-month": 80,
    }
    return min(weights.get(time_range, 25), 100)

# Busca publicações na página pública (pode ser limitada sem login)

def get_publications_per_page(keywords: str, time_range: str, start: int):
    try:
        if not publications_status["is_searching"]:
            return []

        uri = PUBLICATIONS_URL + build_publication_params(keywords, time_range, start)
        log_message(f"Buscando: {uri}")
        res = requests.get(uri, headers=HEADERS, timeout=30)

        if not res.ok:
            log_message(f"HTTP {res.status_code}; retornando vazio")
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        publications = []

        # Heurística: procurar links que contenham '/posts/' ou blocos de feed
        cards = []
        post_links = soup.find_all('a', href=lambda h: isinstance(h, str) and '/posts/' in h)
        for link in post_links[:10]:
            try:
                title_elem = link.find('span') or link.find('div')
                title = title_elem.get_text(strip=True) if title_elem else (link.get_text(strip=True) or 'Publicação LinkedIn')
                item = {
                    'title': title[:120],
                    'author': 'Autor LinkedIn',
                    'content': f'Publicação relacionada a {keywords}',
                    'time': 'recente',
                    'link': 'https://www.linkedin.com' + link.get('href') if link.get('href', '').startswith('/') else link.get('href'),
                    'type': 'publication'
                }
                publications.append(item)
            except Exception as e:
                log_message(f"Erro ao processar link: {e}")
                continue

        log_message(f"Processadas {len(publications)} publicações da página")
        return publications
    except Exception as e:
        log_message(f"Erro ao buscar publicações: {e}")
        return []

# Thread principal de busca

def search_publications_thread(keywords: str, max_date: str, limit_publications: int):
    publications_status["is_searching"] = True
    publications_status["progress"] = 0
    publications_status["log_messages"] = []
    publications_status["results"] = []

    try:
        time_range = calculate_time_range(max_date)
        log_message(f"Iniciando busca de publicações para: {keywords}")
        log_message(f"Período: {time_range}")

        total_est = get_publication_count(keywords, time_range, limit_publications)
        pages = max(1, min(5, total_est // 10 or 1))
        publications_status["total_publications"] = total_est

        all_items = []
        for page in range(pages):
            if not publications_status["is_searching"]:
                break
            update_progress(10 + int(70 * (page / max(1, pages))), f"Coletando página {page+1}/{pages}")
            start = page * 10
            items = get_publications_per_page(keywords, time_range, start)
            all_items.extend(items)
            sleep(1.5)

        # Limitar e fallback se vazio
        if limit_publications and limit_publications > 0:
            all_items = all_items[:limit_publications]

        if not all_items:
            log_message("Nenhuma publicação pública encontrada; usando fallback com link direto")
            all_items = [{
                'title': f'Buscar publicações por "{keywords}"',
                'author': 'LinkedIn',
                'content': 'Clique para abrir a busca no LinkedIn (login pode ser necessário)'.strip(),
                'time': 'recente',
                'link': PUBLICATIONS_URL + build_publication_params(keywords, time_range, 0),
                'type': 'publication'
            }]

        publications_status["results"] = all_items
        publications_status["collected_publications"] = len(all_items)
        update_progress(100, f"Concluído: {len(all_items)} publicações encontradas")
    except Exception as e:
        log_message(f"Erro: {e}")
        publications_status["status_message"] = f"Erro: {e}"
    finally:
        publications_status["is_searching"] = False
