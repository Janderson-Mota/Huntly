from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import math
import re
import threading
from time import sleep
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
from urllib.parse import urlencode, urlparse

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
PAGE_SIZE = 10

COUNTRY_ALIASES: Dict[str, str] = {
    "brasil": "Brazil",
    "brazil": "Brazil",
    "bresil": "Brazil",
    "brasile": "Brazil",
    "brasilien": "Brazil",
    "бразилия": "Brazil",
    "巴西": "Brazil",
    "portugal": "Portugal",
    "portogallo": "Portugal",
    "португалия": "Portugal",
    "葡萄牙": "Portugal",
    "united states": "United States",
    "estados unidos": "United States",
    "etats-unis": "United States",
    "etats unis": "United States",
    "stati uniti": "United States",
    "vereinigte staaten": "United States",
    "eua": "United States",
    "usa": "United States",
    "us": "United States",
    "сша": "United States",
    "美国": "United States",
    "canada": "Canada",
    "kanada": "Canada",
    "канада": "Canada",
    "加拿大": "Canada",
    "united kingdom": "United Kingdom",
    "reino unido": "United Kingdom",
    "royaume-uni": "United Kingdom",
    "royaume uni": "United Kingdom",
    "regno unito": "United Kingdom",
    "vereinigtes konigreich": "United Kingdom",
    "grossbritannien": "United Kingdom",
    "uk": "United Kingdom",
    "великобритания": "United Kingdom",
    "英国": "United Kingdom",
    "germany": "Germany",
    "alemanha": "Germany",
    "alemania": "Germany",
    "allemagne": "Germany",
    "germania": "Germany",
    "deutschland": "Germany",
    "германия": "Germany",
    "德国": "Germany",
    "spain": "Spain",
    "espanha": "Spain",
    "espana": "Spain",
    "espagne": "Spain",
    "spagna": "Spain",
    "spanien": "Spain",
    "испания": "Spain",
    "西班牙": "Spain",
    "ireland": "Ireland",
    "irlanda": "Ireland",
    "irlande": "Ireland",
    "irland": "Ireland",
    "ирландия": "Ireland",
    "爱尔兰": "Ireland",
}

COUNTRY_GEO_IDS: Dict[str, str] = {
    "Brazil": "106057199",
    "Portugal": "100364837",
    "United States": "103644278",
    "Canada": "101174742",
    "United Kingdom": "101165590",
    "Germany": "101282230",
    "Spain": "105646813",
    "Ireland": "104738515",
}

COUNTRY_TOKENS: Dict[str, Tuple[str, ...]] = {
    "Brazil": ("brazil", "brasil", "brasile", "brasilien", "bresil", "бразилия", "巴西"),
    "Portugal": ("portugal", "portogallo", "португалия", "葡萄牙"),
    "United States": (
        "united states",
        "estados unidos",
        "etats-unis",
        "etats unis",
        "stati uniti",
        "vereinigte staaten",
        "usa",
        "сша",
        "美国",
    ),
    "Canada": ("canada", "kanada", "канада", "加拿大"),
    "United Kingdom": (
        "united kingdom",
        "reino unido",
        "royaume-uni",
        "royaume uni",
        "regno unito",
        "vereinigtes konigreich",
        "grossbritannien",
        "великобритания",
        "英国",
    ),
    "Germany": ("germany", "alemanha", "alemania", "allemagne", "germania", "deutschland", "германия", "德国"),
    "Spain": ("spain", "espanha", "espana", "espagne", "spagna", "spanien", "испания", "西班牙"),
    "Ireland": ("ireland", "irlanda", "irlande", "irland", "ирландия", "爱尔兰"),
}

COUNTRY_SUFFIX_CODES: Dict[str, Tuple[str, ...]] = {
    "United States": ("us",),
    "United Kingdom": ("uk",),
}

OTHER_COUNTRY_TOKENS: Tuple[str, ...] = (
    "argentina",
    "mexico",
    "colombia",
    "chile",
    "peru",
    "uruguay",
    "uruguai",
    "paraguay",
    "paraguai",
    "ecuador",
    "equador",
    "venezuela",
    "bolivia",
    "costa rica",
    "panama",
    "france",
    "franca",
    "francia",
    "frankreich",
    "italy",
    "italia",
    "italie",
    "italien",
    "netherlands",
    "holanda",
    "paises baixos",
    "poland",
    "polonia",
    "india",
    "china",
    "japan",
    "japao",
    "australia",
    "switzerland",
    "suica",
    "belgium",
    "belgica",
    "austria",
    "sweden",
    "suecia",
    "norway",
    "noruega",
    "denmark",
    "dinamarca",
    "finland",
    "finlandia",
    "russia",
    "ukraine",
    "ucrania",
    "romania",
    "romenia",
    "czechia",
    "czech republic",
    "singapore",
    "cingapura",
    "israel",
    "latin america",
    "america latina",
    "latam",
    "emea",
    "apac",
    "worldwide",
    "global",
    "european union",
    "europe",
    "europa",
    "north america",
    "america do norte",
)

BRAZIL_UNAMBIGUOUS_UF_RE = re.compile(
    r",\s*(?:ac|ap|am|ba|ce|df|go|mg|pb|pr|pe|pi|rj|rn|rs|ro|rr|sp|se|to)$"
)
BRAZIL_AMBIGUOUS_UF_RE = re.compile(r",\s*(?:al|es|ma|ms|mt|pa|sc)$")

COUNTRY_REGION_TOKENS: Dict[str, Tuple[str, ...]] = {
    "Brazil": (
        "acre",
        "alagoas",
        "amapa",
        "amazonas",
        "bahia",
        "ceara",
        "distrito federal",
        "espirito santo",
        "goias",
        "maranhao",
        "mato grosso",
        "mato grosso do sul",
        "minas gerais",
        "para",
        "paraiba",
        "parana",
        "pernambuco",
        "piaui",
        "rio de janeiro",
        "rio grande do norte",
        "rio grande do sul",
        "rondonia",
        "roraima",
        "santa catarina",
        "sao paulo",
        "san pablo",
        "sergipe",
        "tocantins",
        "rio branco",
        "maceio",
        "macapa",
        "manaus",
        "salvador",
        "feira de santana",
        "vitoria da conquista",
        "fortaleza",
        "juazeiro do norte",
        "brasilia",
        "vitoria",
        "vila velha",
        "serra",
        "goiania",
        "anapolis",
        "aparecida de goiania",
        "sao luis",
        "cuiaba",
        "campo grande",
        "belo horizonte",
        "uberlandia",
        "contagem",
        "juiz de fora",
        "betim",
        "montes claros",
        "manhuacu",
        "belem",
        "joao pessoa",
        "campina grande",
        "curitiba",
        "londrina",
        "maringa",
        "cascavel",
        "recife",
        "jaboatao dos guararapes",
        "olinda",
        "teresina",
        "niteroi",
        "duque de caxias",
        "nova iguacu",
        "natal",
        "porto alegre",
        "caxias do sul",
        "canoas",
        "pelotas",
        "porto velho",
        "boa vista",
        "florianopolis",
        "joinville",
        "blumenau",
        "itajai",
        "campinas",
        "sao jose dos campos",
        "ribeirao preto",
        "sorocaba",
        "santos",
        "barueri",
        "aracaju",
        "palmas",
    ),
    "Portugal": ("lisboa", "lisbon", "porto", "braga", "coimbra", "aveiro", "setubal", "faro", "cascais", "oeiras", "sintra", "matosinhos", "almada", "guimaraes"),
    "United States": (
        "california",
        "new york",
        "texas",
        "washington",
        "florida",
        "massachusetts",
        "colorado",
        "virginia",
        "north carolina",
        "arizona",
        "new jersey",
        "san francisco",
        "los angeles",
        "san jose",
        "san diego",
        "brooklyn",
        "austin",
        "dallas",
        "houston",
        "seattle",
        "bellevue",
        "miami",
        "orlando",
        "tampa",
        "boston",
        "cambridge",
        "aurora",
        "pittsburgh",
        "philadelphia",
        "chicago",
        "atlanta",
        "denver",
        "phoenix",
    ),
    "Canada": ("ontario", "british columbia", "quebec", "alberta", "toronto", "ottawa", "waterloo", "vancouver", "victoria", "montreal", "calgary", "edmonton"),
    "United Kingdom": ("england", "inglaterra", "scotland", "escocia", "london", "londres", "manchester", "birmingham", "bristol", "edinburgh", "edimburgo", "glasgow"),
    "Germany": ("berlin", "berlim", "bavaria", "baviera", "hesse", "hamburg", "hamburgo", "munich", "munique", "munchen", "nuremberg", "frankfurt", "stuttgart", "saarland", "north rhine-westphalia"),
    "Spain": ("madrid", "madri", "catalonia", "catalunha", "cataluna", "valencia", "andalusia", "andaluzia", "barcelona", "seville", "sevilha", "sevilla", "malaga"),
    "Ireland": ("dublin", "cork", "galway"),
}

jobs_state = SearchState(total_key="total_jobs", collected_key="collected_jobs")


def _normalize_text(text: str) -> str:
    """Return lowercase text with combining diacritics stripped."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.lower().strip()


def _contains_token(norm_loc: str, raw_lower: str, token: str) -> bool:
    if any(ord(ch) > 127 for ch in token):
        return token in raw_lower
    return bool(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", norm_loc))


def normalize_location_for_linkedin(location: str) -> Tuple[str, str, str]:
    """Normalize country names to canonical English and infer country geoId when only country is given."""
    if not location or not location.strip():
        return "", "", ""

    parts = [part.strip() for part in location.split(",") if part.strip()]
    if not parts:
        return "", "", ""

    last_norm = _normalize_text(parts[-1])
    canonical_country = COUNTRY_ALIASES.get(last_norm, "")
    if not canonical_country:
        return location.strip(), "", ""

    parts[-1] = canonical_country
    geo_id = COUNTRY_GEO_IDS.get(canonical_country, "") if len(parts) == 1 else ""
    return ", ".join(parts), canonical_country, geo_id


def job_matches_country(job_location: Optional[str], canonical_country: str) -> bool:
    """Verify whether a job location belongs to the requested canonical country."""
    if not canonical_country:
        return True
    if not job_location or not job_location.strip():
        return False

    raw_lower = job_location.lower()
    norm_loc = _normalize_text(job_location)

    # Reject if another known country or supra-national region is explicitly named.
    for other_country, tokens in COUNTRY_TOKENS.items():
        if other_country == canonical_country:
            continue
        if any(_contains_token(norm_loc, raw_lower, tok) for tok in tokens):
            return False
    for other_country, suffixes in COUNTRY_SUFFIX_CODES.items():
        if other_country == canonical_country:
            continue
        if any(re.search(rf"(?:^|,\s*){re.escape(sfx)}$", norm_loc) for sfx in suffixes):
            return False
    if any(_contains_token(norm_loc, raw_lower, tok) for tok in OTHER_COUNTRY_TOKENS):
        return False

    # Accept if the target country name is explicitly present.
    target_tokens = COUNTRY_TOKENS.get(canonical_country, ())
    if any(_contains_token(norm_loc, raw_lower, tok) for tok in target_tokens):
        return True
    target_suffixes = COUNTRY_SUFFIX_CODES.get(canonical_country, ())
    if any(re.search(rf"(?:^|,\s*){re.escape(sfx)}$", norm_loc) for sfx in target_suffixes):
        return True

    # Reject if an explicit region/city from another supported country matches.
    for other_country, region_tokens in COUNTRY_REGION_TOKENS.items():
        if other_country == canonical_country:
            continue
        if any(_contains_token(norm_loc, raw_lower, tok) for tok in region_tokens):
            return False

    if canonical_country == "Brazil":
        if BRAZIL_UNAMBIGUOUS_UF_RE.search(norm_loc):
            return True
        if BRAZIL_AMBIGUOUS_UF_RE.search(norm_loc):
            has_pt_diacritics = any(ch in raw_lower for ch in "áàâãéêíóôõúç")
            has_br_region = any(_contains_token(norm_loc, raw_lower, tok) for tok in COUNTRY_REGION_TOKENS["Brazil"])
            if has_pt_diacritics or has_br_region:
                return True

    target_regions = COUNTRY_REGION_TOKENS.get(canonical_country, ())
    if any(_contains_token(norm_loc, raw_lower, tok) for tok in target_regions):
        return True

    return False


def calculate_time_range(max_date: Optional[str]) -> str:
    """Convert relative, LinkedIn, or YYYY-MM-DD date strings to LinkedIn f_TPR format."""
    if not max_date:
        return ""

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

    return ""


def build_params(
    keywords: str,
    location: str,
    time_range: str,
    distance: str,
    job_type: List[str],
    place: List[str],
    start: int = 0,
    experience_level: Optional[List[str]] = None,
    sort_by: str = "",
    easy_apply: bool = False,
    geo_id: str = "",
) -> str:
    """Build properly URL-encoded query string for LinkedIn job search."""
    params: List[tuple[str, str]] = [
        ("position", "1"),
        ("pageNum", "0"),
        ("start", str(start)),
    ]

    if time_range:
        params.append(("f_TPR", time_range))
    if sort_by in ("DD", "R"):
        params.append(("sortBy", sort_by))

    if keywords:
        cleaned = keywords.strip()
        cleaned = re.sub(r"\bjr\.?\b", "junior", cleaned, flags=re.IGNORECASE)
        params.append(("keywords", cleaned))

    if location:
        norm_loc, _canonical_country, inferred_geo_id = normalize_location_for_linkedin(location)
        if norm_loc:
            params.append(("location", norm_loc))
        effective_geo_id = geo_id or inferred_geo_id
        if effective_geo_id:
            params.append(("geoId", effective_geo_id))
    elif geo_id:
        params.append(("geoId", geo_id))

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

            ids, summaries = _parse_page_jobs(res.text)
            if summaries_out is not None:
                summaries_out.update(summaries)
            return ids

        except requests.RequestException as exc:
            jobs_state.log(f"Erro de rede na página {start} (tentativa {attempt + 1}/{MAX_RETRIES}): {exc}")
            sleep(1.5)

    jobs_state.log(f"Desistindo da página {start} após {MAX_RETRIES} tentativas.")
    return []


def _sanitize_job_url(raw_href: str, job_id: str) -> str:
    """Allow only HTTPS LinkedIn URLs; fall back to canonical job view URL."""
    fallback = f"{PUBLIC_JOB_URL}{job_id}/"
    if not raw_href:
        return fallback
    cleaned = raw_href.split("?")[0].strip()
    parsed = urlparse(cleaned)
    if parsed.scheme == "https" and parsed.netloc.endswith("linkedin.com"):
        return cleaned
    return fallback


def _parse_page_jobs(html: str) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Parse job IDs and card summaries from a LinkedIn search page in a single pass."""
    soup = BeautifulSoup(html, "html.parser")
    ids: List[str] = []
    summaries: Dict[str, Dict[str, Any]] = {}
    for li in soup.find_all("li"):
        div = li.find("div")
        if not div or not div.has_attr("data-entity-urn"):
            continue
        job_id = str(div["data-entity-urn"]).split(":")[-1]
        ids.append(job_id)
        link_el = li.find("a", {"class": "base-card__full-link"})
        title_el = li.find("h3", {"class": "base-search-card__title"})
        company_el = li.find("h4", {"class": "base-search-card__subtitle"})
        loc_el = li.find("span", {"class": "job-search-card__location"})
        time_el = li.find("time")

        raw_href = link_el.get("href", "").strip() if link_el else ""
        clean_href = _sanitize_job_url(raw_href, job_id)

        summaries[job_id] = {
            "id": job_id,
            "title": title_el.get_text(strip=True) if title_el else None,
            "company": company_el.get_text(strip=True) if company_el else None,
            "location": loc_el.get_text(strip=True) if loc_el else None,
            "time": time_el.get_text(strip=True) if time_el else None,
            "link": clean_href,
        }
    return ids, summaries


def _parse_job_summaries(html: str) -> Dict[str, Dict[str, Any]]:
    return _parse_page_jobs(html)[1]


def _extract_description_text(soup: BeautifulSoup) -> Optional[str]:
    """Extract job description preserving paragraph/list line breaks."""
    el = soup.find("div", {"class": "show-more-less-html__markup"})
    if not el:
        return None
    raw = el.get_text(separator="\n", strip=True)
    cleaned = re.sub(r"\n{3,}", "\n\n", raw).strip()
    return cleaned or None


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
                "description": _extract_description_text(soup),
                "time": text_of("span", "posted-time-ago__text") or base.get("time"),
            }

            for crit in soup.find_all("li", {"class": "description__job-criteria-item"}):
                h3 = crit.find("h3")
                span = crit.find("span")
                if h3 and span:
                    detail[h3.get_text(strip=True)] = span.get_text(strip=True)

            return detail
        except Exception as exc:
            if attempt == 0:
                sleep(1.5)
                continue
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
    sort_by: str = "",
    easy_apply: bool = False,
    already_started: bool = False,
) -> None:
    if not already_started and not jobs_state.start():
        return

    try:
        with requests.Session() as session:
            time_range = calculate_time_range(max_date)
            _, canonical_country, _ = normalize_location_for_linkedin(location)

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
            num_pages = max(1, math.ceil(total_jobs / PAGE_SIZE)) + (3 if canonical_country else 0)
            jobs_state.set_total(total_jobs)
            jobs_state.log(f"Buscando até ~{total_jobs} vagas ({num_pages} páginas)")

            job_ids: List[str] = []
            seen_ids: set[str] = set()
            summaries: Dict[str, Dict[str, Any]] = {}
            start_offset = 0
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
                    start_offset,
                    experience_level=experience_level,
                    sort_by=sort_by,
                    easy_apply=easy_apply,
                    summaries_out=summaries,
                )
                for jid in new_ids:
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    summary_loc = summaries.get(jid, {}).get("location")
                    if canonical_country and summary_loc and not job_matches_country(summary_loc, canonical_country):
                        continue
                    job_ids.append(jid)

                progress = (page + 1) / num_pages * 50
                jobs_state.update_progress(
                    progress, f"Coletando páginas: {page + 1}/{num_pages} ({len(job_ids)} IDs)"
                )
                if not new_ids or (limit_jobs > 0 and len(job_ids) >= limit_jobs):
                    break
                start_offset += max(len(new_ids), PAGE_SIZE)
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

            thread_local = threading.local()
            worker_sessions: List[requests.Session] = []
            sessions_lock = threading.Lock()

            def fetch_detail_threadsafe(jid: str) -> Dict[str, Any]:
                if not hasattr(thread_local, "session"):
                    s = requests.Session()
                    thread_local.session = s
                    with sessions_lock:
                        worker_sessions.append(s)
                return get_job_detail(thread_local.session, jid, summaries.get(jid))

            try:
                with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
                    future_map = {
                        executor.submit(fetch_detail_threadsafe, jid): jid
                        for jid in job_ids
                    }
                    for completed, future in enumerate(as_completed(future_map), start=1):
                        if not jobs_state.is_searching:
                            executor.shutdown(wait=False, cancel_futures=True)
                            jobs_state.stop()
                            return

                        detail = future.result()
                        if (
                            detail
                            and not detail.get("error")
                            and (not canonical_country or job_matches_country(detail.get("location"), canonical_country))
                        ):
                            jobs.append(detail)
                            jobs_state.set_results(jobs)

                        progress = 50 + (completed / total_to_fetch) * 50
                        jobs_state.update_progress(
                            progress, f"Obtendo detalhes: {completed}/{total_to_fetch} ({len(jobs)} vagas)"
                        )
            finally:
                for ws in worker_sessions:
                    ws.close()

            jobs_state.finish(f"Concluído: {len(jobs)} vagas encontradas")

    except Exception as exc:
        jobs_state.fail(f"Erro na busca de vagas: {exc}")
