from datetime import datetime
from time import sleep
from typing import Any, Dict, List
from urllib.parse import urlencode

from bs4 import BeautifulSoup
import requests

from state import SearchState

PUBLICATIONS_URL = "https://www.linkedin.com/search/results/content/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

publications_state = SearchState(
    total_key="total_publications",
    collected_key="collected_publications",
)


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
        if "-" in max_date and len(max_date.split("-")) == 3:
            date_obj = datetime.strptime(max_date, "%Y-%m-%d")
            delta_days = (datetime.now() - date_obj).days
            if delta_days <= 1:
                return "past-24-hours"
            if delta_days <= 3:
                return "past-3-days"
            if delta_days <= 7:
                return "past-week"
            return "past-month"
    except ValueError:
        pass

    return "past-week"


def build_publication_params(keywords: str, time_range: str, start: int = 0) -> str:
    params: Dict[str, str] = {
        "keywords": keywords or "",
        "datePosted": f'"{time_range}"',
        "sortBy": '"date_posted"',
    }
    if start > 0:
        params["start"] = str(start)
    return "?" + urlencode(params)


def get_publication_count(time_range: str, limit_publications: int) -> int:
    if limit_publications and limit_publications > 0:
        return limit_publications
    weights = {
        "past-24-hours": 10,
        "past-3-days": 25,
        "past-week": 40,
        "past-month": 80,
    }
    return min(weights.get(time_range, 25), 100)


def get_publications_per_page(
    session: requests.Session,
    keywords: str,
    time_range: str,
    start: int,
) -> List[Dict[str, Any]]:
    if not publications_state.is_searching:
        return []

    uri = PUBLICATIONS_URL + build_publication_params(keywords, time_range, start)
    publications_state.log(f"Buscando: {uri}")

    try:
        res = session.get(uri, headers=HEADERS, timeout=20)
        if not res.ok:
            publications_state.log(f"HTTP {res.status_code}; LinkedIn bloqueou ou exigiu login.")
            return []

        if "login" in res.url or "authwall" in res.url:
            publications_state.log("LinkedIn redirecionou para tela de login (authwall).")
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        publications: List[Dict[str, Any]] = []
        post_links = soup.find_all("a", href=lambda h: isinstance(h, str) and "/posts/" in h)

        for link in post_links[:10]:
            href = link.get("href", "")
            title_elem = link.find("span") or link.find("div")
            title = (
                title_elem.get_text(strip=True)
                if title_elem
                else (link.get_text(strip=True) or "Publicação LinkedIn")
            )
            publications.append(
                {
                    "title": title[:120],
                    "author": "Autor LinkedIn",
                    "content": f"Publicação relacionada a {keywords}",
                    "time": "recente",
                    "link": f"https://www.linkedin.com{href}" if href.startswith("/") else href,
                    "type": "publication",
                }
            )

        return publications
    except requests.RequestException as exc:
        publications_state.log(f"Erro ao buscar publicações: {exc}")
        return []


def search_publications_thread(keywords: str, max_date: str, limit_publications: int) -> None:
    if not publications_state.start():
        return

    try:
        with requests.Session() as session:
            time_range = calculate_time_range(max_date)
            publications_state.log(f"Iniciando busca de publicações para: {keywords} ({time_range})")

            total_est = get_publication_count(time_range, limit_publications)
            pages = max(1, min(5, total_est // 10 or 1))
            publications_state.set_total(total_est)

            all_items: List[Dict[str, Any]] = []
            for page in range(pages):
                if not publications_state.is_searching:
                    publications_state.stop()
                    return

                publications_state.update_progress(
                    10 + int(70 * (page / pages)),
                    f"Coletando página {page + 1}/{pages}",
                )
                items = get_publications_per_page(session, keywords, time_range, page * 10)
                all_items.extend(items)
                if not items:
                    break
                sleep(1.0)

            if limit_publications > 0:
                all_items = all_items[:limit_publications]

            if not all_items:
                publications_state.log(
                    "Nenhuma publicação pública coletada (LinkedIn exige login para resultados de conteúdo). "
                    "Gerando link direto de pesquisa."
                )
                all_items = [
                    {
                        "title": f'Abrir busca no LinkedIn por "{keywords}"',
                        "author": "LinkedIn (Acesso Direto)",
                        "content": "A busca de publicações no LinkedIn exige sessão autenticada. Clique para abrir diretamente no navegador.",
                        "time": "recente",
                        "link": PUBLICATIONS_URL + build_publication_params(keywords, time_range, 0),
                        "type": "publication",
                    }
                ]

            publications_state.set_results(all_items)
            publications_state.finish(f"Concluído: {len(all_items)} item(ns) retornado(s)")
    except Exception as exc:
        publications_state.fail(f"Erro ao buscar publicações: {exc}")
