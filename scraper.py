from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import math
import re
import threading
from time import sleep
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup
import requests

from state import SearchState

INIT_URL = "https://www.linkedin.com/jobs/search"
PAGE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
POST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
PUBLIC_JOB_URL = "https://www.linkedin.com/jobs/view/"

ACCEPT_LANGUAGE_MAP: Dict[str, str] = {
    "pt": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "en": "en-US,en;q=0.9",
    "es": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "fr": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "it": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "de": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "ru": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "zh": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def build_headers(lang: str = "en") -> Dict[str, str]:
    """Build LinkedIn request headers aligned to the selected UI language (fallback en-US)."""
    lang_key = (lang or "en").strip().lower().split("-")[0]
    accept_lang = ACCEPT_LANGUAGE_MAP.get(lang_key, "en-US,en;q=0.9")
    return {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept-Language": accept_lang,
    }


EMPLOYMENT_TYPE_HEADERS = {
    "tipo de emprego",
    "employment type",
    "tipo de empleo",
    "type d'emploi",
    "tipo di impiego",
    "beschaftigungsart",
    "тип занятости",
    "雇佣类型",
}

EXPERIENCE_LEVEL_HEADERS = {
    "nivel de experiencia",
    "seniority level",
    "nivel de antiguedad",
    "niveau hierarchique",
    "livello di anzianita",
    "karrierestufe",
    "уровень",
    "уровень опыта",
    "职级",
    "经验级别",
}

EMPLOYMENT_TYPE_VALUE_CODES: Dict[str, str] = {
    "tempo integral": "full_time",
    "full-time": "full_time",
    "full time": "full_time",
    "jornada completa": "full_time",
    "tiempo completo": "full_time",
    "temps plein": "full_time",
    "tempo pieno": "full_time",
    "vollzeit": "full_time",
    "полная занятость": "full_time",
    "全职": "full_time",
    "meio periodo": "part_time",
    "part-time": "part_time",
    "part time": "part_time",
    "media jornada": "part_time",
    "tiempo parcial": "part_time",
    "temps partiel": "part_time",
    "teilzeit": "part_time",
    "частичная занятость": "part_time",
    "兼职": "part_time",
    "contrato": "contract",
    "contract": "contract",
    "contrat": "contract",
    "contratto": "contract",
    "vertrag": "contract",
    "befristet": "contract",
    "контракт": "contract",
    "合同工": "contract",
    "temporario": "temporary",
    "temporary": "temporary",
    "temporal": "temporary",
    "temporaire": "temporary",
    "temporaneo": "temporary",
    "zeitarbeit": "temporary",
    "временная": "temporary",
    "临时工": "temporary",
    "estagio": "internship",
    "internship": "internship",
    "practicas": "internship",
    "stage": "internship",
    "tirocinio": "internship",
    "praktikum": "internship",
    "стажировка": "internship",
    "实习": "internship",
    "voluntario": "volunteer",
    "volunteer": "volunteer",
    "voluntariado": "volunteer",
    "benevolat": "volunteer",
    "volontariato": "volunteer",
    "ehrenamt": "volunteer",
    "волонтерство": "volunteer",
    "志愿者": "volunteer",
    "outro": "other",
    "other": "other",
    "otro": "other",
    "autre": "other",
    "altro": "other",
    "sonstiges": "other",
    "другое": "other",
    "其他": "other",
}

EXPERIENCE_LEVEL_VALUE_CODES: Dict[str, str] = {
    "estagio": "internship",
    "internship": "internship",
    "practicas": "internship",
    "stage": "internship",
    "tirocinio": "internship",
    "praktikum": "internship",
    "стажировка": "internship",
    "实习": "internship",
    "junior": "entry_level",
    "entry level": "entry_level",
    "sin experiencia": "entry_level",
    "sin experiencia previa": "entry_level",
    "debutant": "entry_level",
    "livello base": "entry_level",
    "einstiegsposition": "entry_level",
    "начальный уровень": "entry_level",
    "初级": "entry_level",
    "assistente": "associate",
    "associate": "associate",
    "algo de responsabilidad": "associate",
    "premier emploi": "associate",
    "livello intermedio": "associate",
    "mitarbeiter": "associate",
    "специалист": "associate",
    "助理": "associate",
    "pleno-senior": "mid_senior",
    "mid-senior level": "mid_senior",
    "mid senior level": "mid_senior",
    "intermedio": "mid_senior",
    "confirme": "mid_senior",
    "medio-alto": "mid_senior",
    "mittleres management": "mid_senior",
    "berufserfahren": "mid_senior",
    "руководитель среднего звена": "mid_senior",
    "中高级": "mid_senior",
    "diretor": "director",
    "director": "director",
    "direttore": "director",
    "direktor": "director",
    "директор": "director",
    "总监": "director",
    "executivo": "executive",
    "executive": "executive",
    "ejecutivo": "executive",
    "cadre dirigeant": "executive",
    "dirigente": "executive",
    "geschaftsfuhrung": "executive",
    "руководитель": "executive",
    "高管": "executive",
    "nao aplicavel": "not_applicable",
    "not applicable": "not_applicable",
    "no aplicable": "not_applicable",
    "non applicable": "not_applicable",
    "non applicabile": "not_applicable",
    "nicht zutreffend": "not_applicable",
    "не применимо": "not_applicable",
    "不适用": "not_applicable",
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


def _flatten_filter_codes(values: Optional[Union[str, List[str]]]) -> List[str]:
    """Expand list or comma-separated filter values into unique LinkedIn codes preserving order."""
    if not values:
        return []
    raw_items = [values] if isinstance(values, str) else list(values)
    seen: set[str] = set()
    codes: List[str] = []
    for item in raw_items:
        if item is None:
            continue
        for part in str(item).split(","):
            code = part.strip()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def build_params(
    keywords: str,
    location: str,
    time_range: str,
    distance: str,
    job_type: List[str],
    place: Union[List[str], str],
    start: int = 0,
    experience_level: Optional[Union[List[str], str]] = None,
    sort_by: str = "",
    easy_apply: bool = False,
    geo_id: str = "",
    work_mode: Optional[Union[List[str], str]] = None,
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
    place_codes = _flatten_filter_codes(work_mode if work_mode is not None else place)
    if place_codes:
        params.append(("f_WT", ",".join(place_codes)))
    exp_codes = _flatten_filter_codes(experience_level)
    if exp_codes:
        params.append(("f_E", ",".join(exp_codes)))
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
    lang: str = "en",
) -> int:
    """Return configured job limit or LinkedIn cap when unlimited."""
    return limit_jobs if limit_jobs > 0 else 1000


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
    run_id: Optional[int] = None,
    lang: str = "en",
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
    headers = build_headers(lang)

    for attempt in range(MAX_RETRIES):
        if not jobs_state.is_run_active(run_id):
            return []

        try:
            res = session.get(uri, headers=headers, timeout=REQUEST_TIMEOUT)

            if res.status_code == 404:
                return []

            if res.status_code in (429, 403, 999):
                wait_time = 2 ** (attempt + 1)
                jobs_state.log(
                    f"Rate limit/bloqueio (HTTP {res.status_code}) na página {start}. "
                    f"Aguardando {wait_time}s (tentativa {attempt + 1}/{MAX_RETRIES})...",
                    run_id=run_id,
                )
                sleep(wait_time)
                continue

            if not res.ok:
                jobs_state.log(
                    f"HTTP {res.status_code} na página {start} (tentativa {attempt + 1}/{MAX_RETRIES})",
                    run_id=run_id,
                )
                sleep(2)
                continue

            ids, summaries = _parse_page_jobs(res.text)
            if summaries_out is not None:
                summaries_out.update(summaries)
            return ids

        except requests.RequestException as exc:
            jobs_state.log(
                f"Erro de rede na página {start} (tentativa {attempt + 1}/{MAX_RETRIES}): {exc}",
                run_id=run_id,
            )
            sleep(1.5)

    jobs_state.log(f"Desistindo da página {start} após {MAX_RETRIES} tentativas.", run_id=run_id)
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
    run_id: Optional[int] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    if not jobs_state.is_run_active(run_id):
        return {}

    uri = POST_URL + job_id
    headers = build_headers(lang)
    for attempt in range(2):
        try:
            sleep(0.35)
            res = session.get(uri, headers=headers, timeout=REQUEST_TIMEOUT)
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
                    h3_text = h3.get_text(strip=True)
                    span_text = span.get_text(strip=True)
                    detail[h3_text] = span_text

                    norm_h3 = _normalize_text(h3_text)
                    norm_val = _normalize_text(span_text)
                    if norm_h3 in EMPLOYMENT_TYPE_HEADERS:
                        emp_code = EMPLOYMENT_TYPE_VALUE_CODES.get(norm_val)
                        if emp_code:
                            detail["employment_type_code"] = emp_code
                    elif norm_h3 in EXPERIENCE_LEVEL_HEADERS:
                        lvl_code = EXPERIENCE_LEVEL_VALUE_CODES.get(norm_val)
                        if lvl_code:
                            detail["experience_level_code"] = lvl_code

            return detail
        except Exception as exc:
            if attempt == 0:
                sleep(1.5)
                continue
            jobs_state.log(f"Falha na vaga {job_id}: {exc}", run_id=run_id)
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
    run_id: Optional[int] = None,
    lang: str = "en",
) -> None:
    if not already_started:
        if not jobs_state.start():
            return
        run_id = jobs_state.run_id
    elif run_id is None:
        run_id = jobs_state.run_id

    try:
        with requests.Session() as session:
            time_range = calculate_time_range(max_date)
            _, canonical_country, _ = normalize_location_for_linkedin(location)

            jobs_state.update_progress(
                0,
                "Obtendo número total de vagas...",
                run_id=run_id,
                status_code="statusCounting",
                status_params={},
            )
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
                lang=lang,
            )
            num_pages = max(1, math.ceil(total_jobs / PAGE_SIZE)) + (3 if canonical_country else 0)
            jobs_state.set_total(total_jobs, run_id=run_id)
            jobs_state.log(f"Buscando até ~{total_jobs} vagas ({num_pages} páginas)", run_id=run_id)

            job_ids: List[str] = []
            seen_ids: set[str] = set()
            summaries: Dict[str, Dict[str, Any]] = {}
            start_offset = 0
            for page in range(num_pages):
                if not jobs_state.is_run_active(run_id):
                    jobs_state.stop(run_id=run_id)
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
                    run_id=run_id,
                    lang=lang,
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
                    progress,
                    f"Coletando páginas: {page + 1}/{num_pages} ({len(job_ids)} IDs)",
                    run_id=run_id,
                    status_code="statusCollectingPages",
                    status_params={"page": page + 1, "pages": num_pages, "count": len(job_ids)},
                )
                if not new_ids or (limit_jobs > 0 and len(job_ids) >= limit_jobs):
                    break
                start_offset += max(len(new_ids), PAGE_SIZE)
                sleep(0.2)

            if not jobs_state.is_run_active(run_id):
                jobs_state.stop(run_id=run_id)
                return

            if limit_jobs > 0:
                job_ids = job_ids[:limit_jobs]

            if not job_ids:
                jobs_state.finish(
                    "Nenhuma vaga encontrada para os filtros informados.",
                    run_id=run_id,
                    status_code="statusNoResults",
                    status_params={},
                )
                return

            jobs: List[Dict[str, Any]] = []
            job_order = {jid: idx for idx, jid in enumerate(job_ids)}
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
                return get_job_detail(
                    thread_local.session,
                    jid,
                    summaries.get(jid),
                    run_id=run_id,
                    lang=lang,
                )

            try:
                with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
                    future_map = {
                        executor.submit(fetch_detail_threadsafe, jid): jid
                        for jid in job_ids
                    }
                    for completed, future in enumerate(as_completed(future_map), start=1):
                        if not jobs_state.is_run_active(run_id):
                            executor.shutdown(wait=False, cancel_futures=True)
                            jobs_state.stop(run_id=run_id)
                            return

                        detail = future.result()
                        if (
                            detail
                            and not detail.get("error")
                            and (not canonical_country or job_matches_country(detail.get("location"), canonical_country))
                        ):
                            jobs.append(detail)
                            jobs.sort(key=lambda item: job_order.get(str(item.get("id")), len(job_order)))
                            jobs_state.set_results(list(jobs), run_id=run_id)

                        progress = 50 + (completed / total_to_fetch) * 50
                        jobs_state.update_progress(
                            progress,
                            f"Obtendo detalhes: {completed}/{total_to_fetch} ({len(jobs)} vagas)",
                            run_id=run_id,
                            status_code="statusFetchingDetails",
                            status_params={"completed": completed, "total": total_to_fetch, "found": len(jobs)},
                        )
            finally:
                for ws in worker_sessions:
                    ws.close()

            jobs_state.finish(
                f"Concluído: {len(jobs)} vagas encontradas",
                run_id=run_id,
                status_code="statusComplete",
                status_params={"found": len(jobs)},
            )

    except Exception as exc:
        jobs_state.fail(
            f"Erro na busca de vagas: {exc}",
            run_id=run_id,
            status_code="statusError",
            status_params={"detail": str(exc)},
        )
