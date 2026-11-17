from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import math
from time import sleep
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup
import requests

from state import SearchState

INIT_URL = "https://www.linkedin.com/jobs/search"
PAGE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
POST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
PUBLIC_JOB_URL = "https://www.linkedin.com/jobs/view/"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

MAX_RETRIES = 3
REQUEST_TIMEOUT = 20
DETAIL_WORKERS = 2

jobs_state = SearchState(total_key="total_jobs", collected_key="collected_jobs")


def calculate_time_range(max_date: Optional[str]) -> str:
    """Convert relative, LinkedIn, or YYYY-MM-DD date strings to LinkedIn f_TPR format."""
    if not max_date:
        return "r604800"

    valid_relative = {
        "r24h": "r86400",
        "r3d": "r259200",
        "r7d": "r604800",
        "r1m": "r2592000",
    }
    if max_date in valid_relative:
        return valid_relative[max_date]

    linkedin_formats = {
        "past-24-hours": "r86400",
        "past-3-days": "r259200",
        "past-week": "r604800",
        "past-month": "r2592000",
    }
    if max_date in linkedin_formats:
        return linkedin_formats[max_date]

    try:
        if "-" in max_date and len(max_date.split("-")) == 3:
            date_obj = datetime.strptime(max_date, "%Y-%m-%d")
            delta_seconds = max(3600, int((datetime.now() - date_obj).total_seconds()))
            return f"r{delta_seconds}"
    except ValueError:
        pass

    return "r604800"


def build_params(
    keywords: str,
    location: str,
    time_range: str,
    distance: str,
    job_type: List[str],
    place: List[str],
    start: int = 0,
    experience_level: Optional[List[str]] = None,
    sort_by: str = "DD",
    easy_apply: bool = False,
) -> str:
    """Build properly URL-encoded query string for LinkedIn job search."""
    valid_sort = sort_by if sort_by in ("DD", "R") else "DD"
    params: List[tuple[str, str]] = [
        ("f_TPR", time_range),
        ("position", "1"),
        ("pageNum", "0"),
        ("start", str(start)),
        ("sortBy", valid_sort),
    ]

    if keywords:
        cleaned = keywords.strip().replace('"', "")
        cleaned = cleaned.replace("jr", "junior").replace("Jr", "Junior")
        if " " in cleaned:
            cleaned = f'"{cleaned}"'
        params.append(("keywords", cleaned))

    if location:
        loc = location.strip()
        if loc:
            params.append(("location", loc))

    if distance:
        params.append(("distance", str(distance)))
    if job_type:
        params.append(("f_JT", ",".join(job_type)))
    if place:
        params.append(("f_WT", ",".join(place)))
    if experience_level:
        params.append(("f_E", ",".join(experience_level)))
    if easy_apply:
        params.append(("f_AL", "true"))

    return "?" + urlencode(params)


def get_job_count(
    session: requests.Session,
    keywords: str,
    location: str,
    time_range: str,
    distance: str,
    job_type: List[str],
    place: List[str],
    limit_jobs: int,
    experience_level: Optional[List[str]] = None,
    sort_by: str = "DD",
    easy_apply: bool = False,
) -> int:
    if limit_jobs > 0:
        return limit_jobs

    try:
        uri = INIT_URL + build_params(
            keywords,
            location,
            time_range,
            distance,
            job_type,
            place,
            experience_level=experience_level,
            sort_by=sort_by,
            easy_apply=easy_apply,
        )
        jobs_state.log(f"Consultando: {uri}")
        res = session.get(uri, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(res.text, "html.parser")

        job_count_element = (
            soup.find("span", {"class": "results-context-header__job-count"})
            or soup.find("span", {"class": "results-context-header__new-jobs"})
        )

        if job_count_element:
            raw_count = job_count_element.get_text(strip=True).replace(",", "").replace(".", "").replace("+", "")
            return min(int(raw_count), 1000)
        return 1000
    except Exception as exc:
        jobs_state.log(f"Erro ao obter contagem de vagas: {exc}")
        return 1000


def get_job_ids_per_page(
    session: requests.Session,
    keywords: str,
    location: str,
    time_range: str,
    distance: str,
    job_type: List[str],
    place: List[str],
    start: int,
    experience_level: Optional[List[str]] = None,
    sort_by: str = "DD",
    easy_apply: bool = False,
    summaries_out: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    uri = PAGE_URL + build_params(
        keywords,
        location,
        time_range,
        distance,
        job_type,
        place,
        start,
        experience_level=experience_level,
        sort_by=sort_by,
        easy_apply=easy_apply,
    )

    for attempt in range(MAX_RETRIES):
        if not jobs_state.is_searching:
            return []

        try:
            res = session.get(uri, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)

            if res.status_code == 404:
                return []

            if res.status_code in (429, 403, 999):
                wait_time = 2 ** (attempt + 1)
                jobs_state.log(
                    f"Rate limit/bloqueio (HTTP {res.status_code}) na página {start}. "
                    f"Aguardando {wait_time}s (tentativa {attempt + 1}/{MAX_RETRIES})..."
                )
                sleep(wait_time)
                continue

            if not res.ok:
                jobs_state.log(f"HTTP {res.status_code} na página {start} (tentativa {attempt + 1}/{MAX_RETRIES})")
                sleep(2)
                continue

            if summaries_out is not None:
                summaries_out.update(_parse_job_summaries(res.text))

            soup = BeautifulSoup(res.text, "html.parser")
            ids: List[str] = []
            for li in soup.find_all("li"):
                div = li.find("div")
                if div and div.has_attr("data-entity-urn"):
                    ids.append(str(div["data-entity-urn"]).split(":")[-1])
            return ids

        except requests.RequestException as exc:
            jobs_state.log(f"Erro de rede na página {start} (tentativa {attempt + 1}/{MAX_RETRIES}): {exc}")
            sleep(1.5)

    jobs_state.log(f"Desistindo da página {start} após {MAX_RETRIES} tentativas.")
    return []


def _parse_job_summaries(html: str) -> Dict[str, Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    summaries: Dict[str, Dict[str, Any]] = {}
    for li in soup.find_all("li"):
        div = li.find("div")
        if not div or not div.has_attr("data-entity-urn"):
            continue
        job_id = str(div["data-entity-urn"]).split(":")[-1]
        link_el = li.find("a", {"class": "base-card__full-link"})
        title_el = li.find("h3", {"class": "base-search-card__title"})
        company_el = li.find("h4", {"class": "base-search-card__subtitle"})
        loc_el = li.find("span", {"class": "job-search-card__location"})
        time_el = li.find("time")

        raw_href = link_el.get("href", "").strip() if link_el else ""
        clean_href = raw_href.split("?")[0] if raw_href else f"{PUBLIC_JOB_URL}{job_id}/"

        summaries[job_id] = {
            "id": job_id,
            "title": title_el.get_text(strip=True) if title_el else None,
            "company": company_el.get_text(strip=True) if company_el else None,
            "location": loc_el.get_text(strip=True) if loc_el else None,
            "time": time_el.get_text(strip=True) if time_el else None,
            "link": clean_href,
        }
    return summaries


def get_job_detail(
    session: requests.Session,
    job_id: str,
    fallback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not jobs_state.is_searching:
        return {}

    uri = POST_URL + job_id
    for attempt in range(2):
        try:
            sleep(0.35)
            res = session.get(uri, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
            if res.status_code == 429 and attempt == 0:
                sleep(2.0)
                continue
            res.raise_for_status()

            soup = BeautifulSoup(res.text, "html.parser")

            def text_of(tag: str, cls: str) -> Optional[str]:
                el = soup.find(tag, {"class": cls})
                return el.get_text(strip=True) if el else None

            base = fallback or {}
            detail: Dict[str, Any] = {
                "id": job_id,
                "title": text_of("h2", "top-card-layout__title") or base.get("title"),
                "company": text_of("a", "topcard__org-name-link") or base.get("company"),
                "location": text_of("span", "topcard__flavor--bullet") or base.get("location"),
                "link": base.get("link") or f"{PUBLIC_JOB_URL}{job_id}/",
                "description": text_of("div", "show-more-less-html__markup"),
                "time": text_of("span", "posted-time-ago__text") or base.get("time"),
            }

            for crit in soup.find_all("li", {"class": "description__job-criteria-item"}):
                h3 = crit.find("h3")
                span = crit.find("span")
                if h3 and span:
                    detail[h3.get_text(strip=True)] = span.get_text(strip=True)

            return detail
        except Exception as exc:
            if attempt == 1 or not fallback:
                jobs_state.log(f"Falha na vaga {job_id}: {exc}")
                if fallback and fallback.get("title"):
                    return fallback
                return {"id": job_id, "error": str(exc)}
    return fallback or {"id": job_id, "error": "Falha ao obter detalhes"}


def search_jobs_thread(
    keywords: str,
    location: str,
    max_date: str,
    distance: str,
    job_type: List[str],
    place: List[str],
    limit_jobs: int,
    experience_level: Optional[List[str]] = None,
    sort_by: str = "DD",
    easy_apply: bool = False,
) -> None:
    if not jobs_state.start():
        return

    try:
        with requests.Session() as session:
            time_range = calculate_time_range(max_date)

            jobs_state.log("Obtendo número total de vagas...")
            total_jobs = get_job_count(
                session,
                keywords,
                location,
                time_range,
                distance,
                job_type,
                place,
                limit_jobs,
                experience_level=experience_level,
                sort_by=sort_by,
                easy_apply=easy_apply,
            )
            num_pages = max(1, math.ceil(total_jobs / 25))
            jobs_state.set_total(total_jobs)
            jobs_state.log(f"Buscando até ~{total_jobs} vagas ({num_pages} páginas)")

            job_ids: List[str] = []
            seen_ids: set[str] = set()
            summaries: Dict[str, Dict[str, Any]] = {}
            for page in range(num_pages):
                if not jobs_state.is_searching:
                    jobs_state.stop()
                    return

                new_ids = get_job_ids_per_page(
                    session,
                    keywords,
                    location,
                    time_range,
                    distance,
                    job_type,
                    place,
                    page * 25,
                    experience_level=experience_level,
                    sort_by=sort_by,
                    easy_apply=easy_apply,
                    summaries_out=summaries,
                )
                for jid in new_ids:
                    if jid not in seen_ids:
                        seen_ids.add(jid)
                        job_ids.append(jid)

                progress = (page + 1) / num_pages * 50
                jobs_state.update_progress(
                    progress, f"Coletando páginas: {page + 1}/{num_pages} ({len(job_ids)} IDs)"
                )
                if not new_ids:
                    break
                sleep(0.2)

            if not jobs_state.is_searching:
                jobs_state.stop()
                return

            if limit_jobs > 0:
                job_ids = job_ids[:limit_jobs]

            if not job_ids:
                jobs_state.finish("Nenhuma vaga encontrada para os filtros informados.")
                return

            jobs: List[Dict[str, Any]] = []
            total_to_fetch = len(job_ids)

            with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
                future_map = {
                    executor.submit(get_job_detail, session, jid, summaries.get(jid)): jid
                    for jid in job_ids
                }
                for completed, future in enumerate(as_completed(future_map), start=1):
                    if not jobs_state.is_searching:
                        executor.shutdown(wait=False, cancel_futures=True)
                        jobs_state.stop()
                        return

                    detail = future.result()
                    if detail and not detail.get("error"):
                        jobs.append(detail)
                        jobs_state.set_results(jobs)

                    progress = 50 + (completed / total_to_fetch) * 50
                    jobs_state.update_progress(
                        progress, f"Obtendo detalhes: {completed}/{total_to_fetch} ({len(jobs)} vagas)"
                    )

            jobs_state.finish(f"Concluído: {len(jobs)} vagas encontradas")

    except Exception as exc:
        jobs_state.fail(f"Erro na busca de vagas: {exc}")
