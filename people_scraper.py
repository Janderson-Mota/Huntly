from time import sleep
from typing import Any, Dict, List
from urllib.parse import urlencode

from bs4 import BeautifulSoup
import requests

from state import SearchState

PEOPLE_URL = "https://www.linkedin.com/search/results/people/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

people_state = SearchState(total_key="total_people", collected_key="collected_people")


def build_people_params(keywords: str, start: int = 0) -> str:
    params: Dict[str, str] = {
        "keywords": keywords or "",
        "origin": "SWITCH_SEARCH_VERTICAL",
    }
    if start > 0:
        params["page"] = str(start // 10 + 1)
    return "?" + urlencode(params)


def fetch_people_page(session: requests.Session, keywords: str, start: int = 0) -> List[Dict[str, Any]]:
    uri = PEOPLE_URL + build_people_params(keywords, start)
    people_state.log(f"Buscando: {uri}")

    try:
        res = session.get(uri, headers=HEADERS, timeout=20)
        if not res.ok:
            people_state.log(f"HTTP {res.status_code}; LinkedIn bloqueou ou exigiu login.")
            return []

        if "login" in res.url or "authwall" in res.url:
            people_state.log("LinkedIn redirecionou para tela de login (authwall).")
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        people: List[Dict[str, Any]] = []
        links = soup.find_all("a", href=lambda h: isinstance(h, str) and "/in/" in h)
        seen: set[str] = set()

        for anchor in links:
            href = anchor.get("href")
            if not href or href in seen:
                continue
            seen.add(href)

            name = anchor.get_text(strip=True)
            if not name and anchor.parent:
                name = anchor.parent.get_text(" ", strip=True)[:80]

            person: Dict[str, Any] = {
                "name": name or "Nome não disponível",
                "headline": "",
                "location": "",
                "link": f"https://www.linkedin.com{href}" if href.startswith("/") else href,
                "type": "person",
            }

            container = anchor.find_parent(["div", "li"])
            if container:
                headline_el = container.find(
                    ["div", "span"], string=lambda s: isinstance(s, str) and len(s.strip()) > 0
                )
                if headline_el:
                    txt = headline_el.get_text(" ", strip=True)
                    if txt and txt != name:
                        person["headline"] = txt[:140]

            people.append(person)
            if len(people) >= 10:
                break

        return people
    except requests.RequestException as exc:
        people_state.log(f"Erro ao buscar página de pessoas: {exc}")
        return []


def search_people_thread(
    keywords: str,
    location: str,
    hiring_only: bool,
    hiring_keywords: List[str],
    limit_people: int,
) -> None:
    if not people_state.start():
        return

    try:
        with requests.Session() as session:
            people_state.update_progress(5, "Preparando busca de pessoas...")
            collected: List[Dict[str, Any]] = []

            query = f"{keywords} {location}".strip() if location else keywords
            pages = 2
            for page in range(pages):
                if not people_state.is_searching:
                    people_state.stop()
                    return

                people_state.update_progress(
                    10 + int(70 * (page / pages)),
                    f"Coletando página {page + 1}/{pages}",
                )
                real = fetch_people_page(session, query, start=page * 10)
                collected.extend(real)
                if not real:
                    break
                sleep(1.0)

            if hiring_only and collected:
                kws = [k.lower() for k in (hiring_keywords or ["contratando", "hiring", "recrutando"])]
                collected = [
                    p for p in collected if any(k in (p.get("headline") or "").lower() for k in kws)
                ]

            if limit_people > 0:
                collected = collected[:limit_people]

            if not collected:
                people_state.log(
                    "Nenhum perfil público retornado (LinkedIn exige login). Gerando link direto de pesquisa."
                )
                collected = [
                    {
                        "name": f'Abrir busca no LinkedIn por "{query}"',
                        "headline": "A busca de pessoas no LinkedIn exige sessão autenticada. Clique para abrir diretamente no navegador.",
                        "location": location or "Brasil",
                        "link": PEOPLE_URL + build_people_params(query, 0),
                        "type": "person",
                    }
                ]
                people_state.set_results(collected)
                people_state.finish("Link direto gerado para busca de pessoas no LinkedIn")
            else:
                people_state.set_results(collected)
                people_state.finish(f"Concluído: {len(collected)} pessoas encontradas")
    except Exception as exc:
        people_state.fail(f"Erro ao buscar pessoas: {exc}")
