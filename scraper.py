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
import translator

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

WORK_MODE_HEADERS = {
    "tipo de local de trabalho",
    "modalidade de trabalho",
    "workplace type",
    "workplace",
    "tipo de lugar de trabajo",
    "modalidad",
    "type de lieu de travail",
    "mode de travail",
    "tipo di sede di lavoro",
    "modalita di lavoro",
    "arbeitsort",
    "arbeitsmodell",
    "формат работы",
    "тип занятости на месте",
    "工作模式",
    "工作地点类型",
}

WORK_MODE_VALUE_CODES: Dict[str, str] = {
    "remoto": "remote",
    "remote": "remote",
    "teletrabalho": "remote",
    "teletrabajo": "remote",
    "teletravail": "remote",
    "lavoro da remoto": "remote",
    "homeoffice": "remote",
    "удаленно": "remote",
    "удаленная работа": "remote",
    "远程": "remote",
    "hibrido": "hybrid",
    "hibrida": "hybrid",
    "hybrid": "hybrid",
    "hybride": "hybrid",
    "ibrido": "hybrid",
    "гибрид": "hybrid",
    "гибридный формат": "hybrid",
    "混合办公": "hybrid",
    "presencial": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "onsite": "onsite",
    "sur site": "onsite",
    "in sede": "onsite",
    "vor ort": "onsite",
    "в офисе": "onsite",
    "очно": "onsite",
    "现场办公": "onsite",
}

WORK_MODE_FILTER_TO_CODE: Dict[str, str] = {
    "2": "remote",
    "3": "hybrid",
    "1": "onsite",
}

STATE_ALIASES: Dict[str, Tuple[str, ...]] = {
    "acre": ("acre", "ac"),
    "alagoas": ("alagoas", "al"),
    "amapa": ("amapa", "ap"),
    "amazonas": ("amazonas", "am"),
    "bahia": ("bahia", "ba"),
    "ceara": ("ceara", "ce"),
    "distrito federal": ("distrito federal", "df", "brasilia"),
    "espirito santo": ("espirito santo", "es"),
    "goias": ("goias", "go"),
    "maranhao": ("maranhao", "ma"),
    "mato grosso": ("mato grosso", "mt"),
    "mato grosso do sul": ("mato grosso do sul", "ms"),
    "minas gerais": ("minas gerais", "mg"),
    "para": ("para", "pa"),
    "paraiba": ("paraiba", "pb"),
    "parana": ("parana", "pr"),
    "pernambuco": ("pernambuco", "pe"),
    "piaui": ("piaui", "pi"),
    "rio de janeiro": ("rio de janeiro", "rj"),
    "rio grande do norte": ("rio grande do norte", "rn"),
    "rio grande do sul": ("rio grande do sul", "rs"),
    "rondonia": ("rondonia", "ro"),
    "roraima": ("roraima", "rr"),
    "santa catarina": ("santa catarina", "sc"),
    "sao paulo": ("sao paulo", "san pablo", "sp"),
    "sergipe": ("sergipe", "se"),
    "tocantins": ("tocantins", "to"),
    "california": ("california", "ca"),
    "new york": ("new york", "ny"),
    "texas": ("texas", "tx"),
    "washington": ("washington", "wa"),
    "florida": ("florida", "fl"),
    "massachusetts": ("massachusetts", "ma"),
    "ontario": ("ontario", "on"),
    "british columbia": ("british columbia", "bc"),
    "quebec": ("quebec", "qc"),
    "alberta": ("alberta", "ab"),
    "lisboa": ("lisboa", "lisbon"),
    "bavaria": ("bavaria", "baviera", "bayern"),
    "berlin": ("berlin", "berlim"),
    "hamburg": ("hamburg", "hamburgo"),
    "catalonia": ("catalonia", "cataluna", "catalunha"),
    "andalusia": ("andalusia", "andalucia", "andaluzia"),
    "munich": ("munich", "munchen", "munique"),
    "seville": ("seville", "sevilla", "sevilha"),
}

_EXP_TOKEN_TO_LINKEDIN_FE: Dict[str, Tuple[str, ...]] = {
    "1": ("1",),
    "trainee": ("1", "2"),
    "2": ("2",),
    "3": ("3",),
    "3,4": ("3", "4"),
    "4": ("4",),
    "tech_lead": ("4",),
    "5": ("5",),
    "6": ("6",),
    "5,6": ("5", "6"),
}

_EXP_TOKEN_TO_TARGETS: Dict[str, Tuple[str, ...]] = {
    "1": ("internship",),
    "trainee": ("trainee",),
    "2": ("entry_level",),
    "3": ("mid",),
    "3,4": ("mid",),
    "4": ("senior",),
    "tech_lead": ("tech_lead",),
    "5": ("director",),
    "6": ("director",),
    "5,6": ("director",),
}

_META_TO_TARGETS: Dict[str, set[str]] = {
    "internship": {"internship", "trainee"},
    "entry_level": {"entry_level", "trainee"},
    "associate": {"mid", "trainee"},
    "mid_senior": {"mid", "senior", "tech_lead"},
    "director": {"director"},
    "executive": {"director"},
}

_TITLE_REQUIRED_TARGETS: set[str] = {"trainee", "tech_lead"}

_EXP_SEARCH_TERMS_BY_LOCALE: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "pt": {
        "internship": ("Estágio", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Júnior", "Junior"),
        "mid": ("Pleno", "Mid Level"),
        "senior": ("Sênior", "Senior"),
        "tech_lead": ("Tech Lead", "Líder Técnico"),
        "director": ("Diretor", "Head"),
    },
    "es": {
        "internship": ("Prácticas", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Semi Senior", "Mid Level"),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead", "Líder Técnico"),
        "director": ("Director", "Head"),
    },
    "en": {
        "internship": ("Internship", "Intern"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Mid Level",),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead", "Technical Lead"),
        "director": ("Director", "Head"),
    },
    "de": {
        "internship": ("Praktikum", "Werkstudent", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Mid Level",),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead",),
        "director": ("Director", "Head"),
    },
    "fr": {
        "internship": ("Stage", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Confirmé", "Mid Level"),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead", "Lead Technique"),
        "director": ("Directeur", "Head"),
    },
    "it": {
        "internship": ("Stage", "Tirocinio", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Mid Level",),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead",),
        "director": ("Direttore", "Head"),
    },
    "ja": {
        "internship": ("インターン", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("ジュニア", "Junior"),
        "mid": ("Mid Level",),
        "senior": ("シニア", "Senior"),
        "tech_lead": ("テックリード", "Tech Lead"),
        "director": ("ディレクター", "Director"),
    },
    "zh": {
        "internship": ("实习", "Internship"),
        "trainee": ("管培生", "Trainee"),
        "entry_level": ("初级", "Junior"),
        "mid": ("中级", "Mid Level"),
        "senior": ("高级", "Senior"),
        "tech_lead": ("技术负责人", "Tech Lead"),
        "director": ("总监", "Director"),
    },
    "ru": {
        "internship": ("Стажировка", "Internship"),
        "trainee": ("Trainee",),
        "entry_level": ("Junior",),
        "mid": ("Middle",),
        "senior": ("Senior",),
        "tech_lead": ("Tech Lead",),
        "director": ("Директор", "Head"),
    },
}

_TARGET_DEFAULT_EXP_TOKEN: Dict[str, str] = {
    "internship": "1",
    "trainee": "trainee",
    "entry_level": "2",
    "mid": "3,4",
    "senior": "4",
    "tech_lead": "tech_lead",
    "director": "5,6",
}

COUNTRY_LANGUAGE_MAP: Dict[str, str] = {
    "Brazil": "pt",
    "Portugal": "pt",
    "United States": "en",
    "United Kingdom": "en",
    "Canada": "en",
    "Australia": "en",
    "Ireland": "en",
    "New Zealand": "en",
    "Spain": "es",
    "Mexico": "es",
    "Argentina": "es",
    "Colombia": "es",
    "Chile": "es",
    "Peru": "es",
    "Uruguay": "es",
    "Germany": "de",
    "Austria": "de",
    "Switzerland": "de",
    "France": "fr",
    "Belgium": "fr",
    "Italy": "it",
    "Japan": "ja",
    "China": "zh",
    "Russia": "ru",
}

_EXTRA_LOCATION_COUNTRY_MAP: Dict[str, str] = {
    "australia": "Australia",
    "new zealand": "New Zealand",
    "nova zelandia": "New Zealand",
    "mexico": "Mexico",
    "argentina": "Argentina",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    "uruguay": "Uruguay",
    "uruguai": "Uruguay",
    "austria": "Austria",
    "switzerland": "Switzerland",
    "suica": "Switzerland",
    "france": "France",
    "franca": "France",
    "francia": "France",
    "frankreich": "France",
    "france metropolitaine": "France",
    "paris": "France",
    "lyon": "France",
    "belgium": "Belgium",
    "belgica": "Belgium",
    "belgique": "Belgium",
    "italy": "Italy",
    "italia": "Italy",
    "italie": "Italy",
    "italien": "Italy",
    "milan": "Italy",
    "milao": "Italy",
    "rome": "Italy",
    "roma": "Italy",
    "japan": "Japan",
    "japao": "Japan",
    "japon": "Japan",
    "tokyo": "Japan",
    "toquio": "Japan",
    "日本": "Japan",
    "china": "China",
    "chine": "China",
    "cina": "China",
    "shanghai": "China",
    "beijing": "China",
    "中国": "China",
    "russia": "Russia",
    "rossiya": "Russia",
    "russie": "Russia",
    "russland": "Russia",
    "moscow": "Russia",
    "moscou": "Russia",
    "россия": "Russia",
}

_UNIVERSAL_TECH_PHRASES_RE = re.compile(
    r"\b(?:tech[\s-]?lead|scrum\s+master|product\s+owner|devops|site\s+reliability|sre|qa|ui/ux)\b",
    re.IGNORECASE,
)

_NEGATED_WORK_MODE_RE = re.compile(
    r"\b(?:nao\s+e|nao\s+sera|not|no\s+es|non\s+e|pas)\s+(?:100%\s+)?(?:remot[oae]|h[ií]brid[oa]|hybrid|presencial|on[\s-]?site|remote)\b",
    re.IGNORECASE,
)

_HYBRID_PATTERNS = (
    re.compile(r"\bhibrid[oa]s?\b|\bhybrid(?:e|ed)?\b|\bibrid[oa]\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:dias?|days?)\s*(?:no\s+escritorio|in[\s-]?office|on[\s-]?site|presencia(?:l|is))\b", re.IGNORECASE),
)
_REMOTE_PATTERNS = (
    re.compile(r"\bremot[oae]s?\b|\bhome[\s-]?office\b|\bteletrabalho\b|\bteletrabajo\b|\bteletravail\b|\bwork\s+from\s+home\b|\bwfh\b", re.IGNORECASE),
)
_ONSITE_PATTERNS = (
    re.compile(r"\bpresencial(?:mente)?\b|\bon[\s-]?site\b|\bonsite\b|\bin[\s-]?person\b|\bin[\s-]?office\b|\bsur\s+site\b|\bin\s+sede\b|\bvor\s+ort\b", re.IGNORECASE),
)

_TITLE_EXP_PATTERNS: Tuple[Tuple[str, Tuple[re.Pattern, ...]], ...] = (
    (
        "internship",
        (
            re.compile(r"\bestagi(?:o|ari[oa])\b|\bintern(?:ship)?\b|\bpracticas\b|\bbecari[oa]\b|\btirocinio\b|\bpraktikum\b|\bpraktikant(?:in)?\b|\bwerkstudent(?:in)?\b", re.IGNORECASE),
            re.compile(r"\bstagiaire\b|\bstage\s+(?:de|en|em|it|ti|dev|data|tech|software|developp\w*|ingenieur|informatique|backend|frontend|web|mobile)\b|^\s*stage\b|\(\s*stage\s*\)", re.IGNORECASE),
        ),
    ),
    (
        "trainee",
        (
            re.compile(r"\btrainee\b|\bgraduate\s+program\b|\bprograma\s+(?:de\s+)?trainee\b", re.IGNORECASE),
        ),
    ),
    (
        "entry_level",
        (
            re.compile(r"\bjunior\b|\bjr\.?(?!\w)|\bentry[\s-]?level\b|\bgraduate\b(?!\s+program)|\b(?:dev|developer|desenvolvedor|engenheiro|engineer|analista|analyst|qa|sre)\s+i\b|\bnivel\s+i\b|\blevel\s+1\b", re.IGNORECASE),
        ),
    ),
    (
        "mid",
        (
            re.compile(r"\bpleno\b|\bconfirme(?:e)?\b|\bmid[\s-]?level\b|\bsemi[\s-]?senior\b|\bssr\.?(?!\w)|\bmiddle\b|\b(?:dev|developer|desenvolvedor|engenheiro|engineer|analista|analyst|qa|sre)\s+ii\b|\bnivel\s+ii\b|\blevel\s+2\b", re.IGNORECASE),
        ),
    ),
    (
        "senior",
        (
            re.compile(r"\bsenior\b|\bsr\.?(?!\w)|\bespecialista\b|\bspecialist\b|\bstaff\b|\bprincipal\b|\barquitet[oa]\b|\barchitect\b|\b(?:dev|developer|desenvolvedor|engenheiro|engineer|analista|analyst|qa|sre)\s+iii\b|\bnivel\s+iii\b|\blevel\s+3\b", re.IGNORECASE),
        ),
    ),
    (
        "tech_lead",
        (
            re.compile(
                r"\btech[\s-]?lead(?:er)?\b|\btechlead\b|\btechnical\s+lead(?:er)?\b|\bteam\s+lead(?:er)?\b"
                r"|\blider\s+(?:tecnic[oa]|de\s+tecnologia)\b|\blideranca\s+tecnica\b|\blead\s+technique\b|\bengineering\s+lead\b"
                r"|\bdev\s+lead\b|\blead\s+(?:dev|engineer|developer|architect|analyst|designer|scientist|qa|sre|devops)\b"
                r"|\b(?:software|backend|back-end|frontend|front-end|full[\s-]?stack|mobile|data|qa|devops|cloud|platform|security|php|python|java|node|react|angular|vue|go|golang|rust|ruby|dotnet|ios|android|flutter)\s+lead\b"
                r"|(?<!\w)\.net\s+lead\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "director",
        (
            re.compile(
                r"\bdiretor(?:a)?\b|\bdirector\b|\bdirettore\b|\bdirektor\b|\bdirecteur\b"
                r"|^\s*head\b|\bhead\s+(?:of|de|em)\b|\bhead\s+(?:tecnologia|engenharia|ti|it|tech|engineering|dados|data|produto|product|software|arquitetura|seguranca|security|cloud|infraestrutura)\b"
                r"|\bvp\b|\bvice\s+president\b|\bchief\b|\bcto\b|\bcio\b|\bciso\b|\bcpo\b|\bceo\b|\bcfo\b|\bexecutiv[oa]\b|\bexecutive\b|\bengineering\s+manager\b",
                re.IGNORECASE,
            ),
        ),
    ),
)

_DESC_ROLE_PREFIX = r"(?:vaga|cargo|posicao|oportunidade|nivel|senioridade|buscamos|procuramos|contratamos|atuar(?:a)?\s+como|hiring|seeking|looking\s+for)"

_DESC_EXP_PATTERNS: Tuple[Tuple[str, Tuple[re.Pattern, ...]], ...] = (
    (
        "internship",
        (
            re.compile(
                r"\b(?:vaga|oportunidade|programa)\s+(?:de|para)\s+estagi(?:o|ari[oa])\b"
                r"|\bbolsa[\s-]?auxilio\b|\bcursando\s+(?:o\s+)?(?:ensino\s+)?superior\b"
                r"|\b(?:buscamos|procuramos|contratamos)\s+(?:um|uma)?\s*estagiari[oa]\b"
                r"|\binternship\s+(?:position|role|program|opportunity)\b"
                r"|\b(?:hiring|seeking|looking\s+for)\s+(?:an?\s+)?intern\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "trainee",
        (
            re.compile(
                r"\b(?:programa|vaga|oportunidade)\s+(?:de\s+)?trainee\b|\bgraduate\s+program\b|\btrainee\s+(?:program|position|role)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "entry_level",
        (
            re.compile(
                rf"\b{_DESC_ROLE_PREFIX}\b[^.\n]{{0,45}}\b(?:junior|jr\.?(?!\w)|entry[\s-]?level)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "mid",
        (
            re.compile(
                rf"\b{_DESC_ROLE_PREFIX}\b[^.\n]{{0,45}}\b(?:pleno|mid[\s-]?level|semi[\s-]?senior|ssr\.?(?!\w))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "senior",
        (
            re.compile(
                rf"\b{_DESC_ROLE_PREFIX}\b[^.\n]{{0,45}}\b(?:senior|sr\.?(?!\w))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "tech_lead",
        (
            re.compile(
                rf"\b{_DESC_ROLE_PREFIX}\b[^.\n]{{0,45}}\b(?:tech[\s-]?lead|techlead|technical\s+lead|lider\s+(?:tecnic[oa]|de\s+tecnologia))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "director",
        (
            re.compile(
                rf"\b{_DESC_ROLE_PREFIX}\b[^.\n]{{0,45}}\b(?:diretor(?:a)?|director|head\s+(?:of|de))\b",
                re.IGNORECASE,
            ),
        ),
    ),
)

_TITLE_EXP_NON_LATIN: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("internship", ("стажировк", "стажер", "стажёр", "实习", "インターン")),
    ("trainee", ("стажер-программа", "管培生")),
    ("entry_level", ("начальн", "младш", "初级", "ジュニア")),
    ("mid", ("средн", "中级")),
    ("senior", ("старш", "архитектор", "ведущ", "高级", "资深", "架构师", "专家", "シニア")),
    ("tech_lead", ("тимлид", "техлид", "技术负责人", "テックリード")),
    ("director", ("директор", "руководител", "总监", "高管", "ディレクター")),
)

_WORK_MODE_NON_LATIN: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("hybrid", ("гибрид", "混合")),
    ("remote", ("удаленн", "удалённ", "远程")),
    ("onsite", ("в офисе", "очно", "现场办公")),
)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 20
DETAIL_WORKERS = 2
MIN_LIMIT_JOBS = 25
MAX_LIMIT_JOBS = 50
UNLIMITED_JOBS_CAP = MAX_LIMIT_JOBS
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


def _match_work_mode_text(text: str) -> Optional[str]:
    if not text:
        return None
    raw_lower = text.lower()
    norm = _NEGATED_WORK_MODE_RE.sub(" ", _normalize_text(raw_lower))

    for mode, patterns in (("hybrid", _HYBRID_PATTERNS), ("remote", _REMOTE_PATTERNS), ("onsite", _ONSITE_PATTERNS)):
        if any(pat.search(norm) for pat in patterns):
            return mode
    for mode, tokens in _WORK_MODE_NON_LATIN:
        if any(tok in raw_lower for tok in tokens):
            return mode
    return None


def detect_work_mode(job: Dict[str, Any]) -> Optional[str]:
    """Detect job work mode ('remote', 'hybrid', 'onsite') from metadata, title, location, and description."""
    existing = job.get("work_mode_code")
    if existing in ("remote", "hybrid", "onsite"):
        return existing

    high_priority = " ".join(
        str(val)
        for val in (
            job.get("work_mode_raw"),
            job.get("title"),
            job.get("location"),
        )
        if val
    )
    detected = _match_work_mode_text(high_priority)
    if detected:
        return detected

    desc = job.get("description") or ""
    return _match_work_mode_text(str(desc))


def detect_title_experience_levels(title: Optional[str]) -> set[str]:
    """Infer experience level buckets semantically from a job title."""
    if not title:
        return set()
    raw_lower = str(title).lower()
    norm = _normalize_text(str(title))
    detected: set[str] = set()
    for level, patterns in _TITLE_EXP_PATTERNS:
        if any(pat.search(norm) for pat in patterns):
            detected.add(level)
    for level, tokens in _TITLE_EXP_NON_LATIN:
        if any(tok in raw_lower for tok in tokens):
            detected.add(level)
    return detected


def detect_description_experience_levels(description: Optional[str]) -> set[str]:
    """Infer role-declaring experience buckets conservatively from a job description."""
    if not description:
        return set()
    norm = _normalize_text(str(description))
    detected: set[str] = set()
    for level, patterns in _DESC_EXP_PATTERNS:
        if any(pat.search(norm) for pat in patterns):
            detected.add(level)
    return detected


def normalize_experience_targets(experience_level: Optional[Union[str, List[str]]]) -> set[str]:
    """Normalize selected experience filter tokens into semantic buckets."""
    if not experience_level:
        return set()
    items = [experience_level] if isinstance(experience_level, str) else list(experience_level)
    targets: set[str] = set()
    for item in items:
        if item is None:
            continue
        raw = str(item).strip()
        if not raw:
            continue
        if raw in _EXP_TOKEN_TO_TARGETS:
            targets.update(_EXP_TOKEN_TO_TARGETS[raw])
        else:
            for part in raw.split(","):
                tok = part.strip()
                if tok in _EXP_TOKEN_TO_TARGETS:
                    targets.update(_EXP_TOKEN_TO_TARGETS[tok])
    return targets


def job_matches_experience(job: Dict[str, Any], experience_level: Optional[Union[str, List[str]]]) -> bool:
    """Verify whether a job matches selected experience levels via title, description, and metadata."""
    targets = normalize_experience_targets(experience_level)
    if not targets:
        return True

    title_levels = detect_title_experience_levels(job.get("title"))
    if title_levels:
        if title_levels & targets:
            # Explicit title recognition overrides noisy or 'not_applicable' LinkedIn metadata.
            return True
        return False

    meta_code = job.get("experience_level_code")
    desc_levels = detect_description_experience_levels(job.get("description"))
    if desc_levels:
        if desc_levels & targets:
            if not meta_code or meta_code == "not_applicable":
                return True
            if meta_code in _META_TO_TARGETS:
                return bool((_META_TO_TARGETS[meta_code] & targets) or (targets & _TITLE_REQUIRED_TARGETS))
            return True
        return False

    if not meta_code or meta_code == "not_applicable":
        return False

    if targets <= _TITLE_REQUIRED_TARGETS:
        return False

    if meta_code in _META_TO_TARGETS:
        non_title_only_targets = targets - _TITLE_REQUIRED_TARGETS
        return bool(_META_TO_TARGETS[meta_code] & non_title_only_targets)

    return False


def job_matches_work_mode(job: Dict[str, Any], work_mode: Optional[Union[str, List[str]]]) -> bool:
    """Strictly verify if a job matches at least one selected work mode."""
    codes = _flatten_filter_codes(work_mode)
    if not codes:
        return True
    selected_modes = {WORK_MODE_FILTER_TO_CODE[c] for c in codes if c in WORK_MODE_FILTER_TO_CODE}
    if not selected_modes:
        return True
    detected = detect_work_mode(job)
    return detected in selected_modes if detected else False


def _location_part_matches(norm_job_loc: str, requested_part: str) -> bool:
    norm_part = _normalize_text(requested_part)
    if not norm_part:
        return True
    candidates = STATE_ALIASES.get(norm_part, (norm_part,))
    return any(bool(re.search(rf"(?<!\w){re.escape(cand)}(?!\w)", norm_job_loc)) for cand in candidates)


def job_matches_location(job_location: Optional[str], requested_location: str) -> bool:
    """Strictly validate country plus requested city or state/region."""
    if not requested_location or not requested_location.strip():
        return True

    _norm_req, canonical_country, _ = normalize_location_for_linkedin(requested_location)
    if canonical_country and not job_matches_country(job_location, canonical_country):
        return False

    if not job_location or not job_location.strip():
        return False

    req_parts = [part.strip() for part in requested_location.split(",") if part.strip()]
    if canonical_country and req_parts and COUNTRY_ALIASES.get(_normalize_text(req_parts[-1])) == canonical_country:
        subparts = req_parts[:-1]
    else:
        subparts = req_parts

    if not subparts:
        return True

    norm_job_loc = _normalize_text(job_location)
    if len(subparts) >= 2:
        city_part, _state_part = subparts[0], subparts[1]
        return _location_part_matches(norm_job_loc, city_part)
    return _location_part_matches(norm_job_loc, subparts[0])


def classify_job_match(
    job: Dict[str, Any],
    requested_location: str = "",
    experience_level: Optional[Union[str, List[str]]] = None,
    work_mode: Optional[Union[str, List[str]]] = None,
) -> str:
    """Return 'matched' when a job satisfies all active filters strictly, otherwise 'recommended'."""
    loc_ok = job_matches_location(job.get("location"), requested_location)
    exp_ok = job_matches_experience(job, experience_level)
    wt_ok = job_matches_work_mode(job, work_mode)
    return "matched" if (loc_ok and exp_ok and wt_ok) else "recommended"


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


def _expand_experience_linkedin_codes(values: Optional[Union[str, List[str]]]) -> List[str]:
    """Translate semantic and numeric experience filter tokens into unique LinkedIn f_E numeric codes."""
    if not values:
        return []
    raw_items = [values] if isinstance(values, str) else list(values)
    seen: set[str] = set()
    codes: List[str] = []

    def add_code(code: str) -> None:
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    for item in raw_items:
        if item is None:
            continue
        raw = str(item).strip()
        if not raw:
            continue
        if raw in _EXP_TOKEN_TO_LINKEDIN_FE:
            for fe_code in _EXP_TOKEN_TO_LINKEDIN_FE[raw]:
                add_code(fe_code)
            continue
        for part in raw.split(","):
            tok = part.strip()
            if not tok:
                continue
            for fe_code in _EXP_TOKEN_TO_LINKEDIN_FE.get(tok, (tok,)):
                if fe_code.isdigit():
                    add_code(fe_code)
    return codes


def _resolve_location_country_for_language(location: str = "") -> str:
    """Resolve country name from location string for search-language adaptation."""
    if not location or not location.strip():
        return ""
    _norm_loc, canonical_country, _ = normalize_location_for_linkedin(location)
    if canonical_country in COUNTRY_LANGUAGE_MAP:
        return canonical_country

    raw_lower = location.lower()
    norm_loc = _normalize_text(location)
    parts = [p.strip() for p in location.split(",") if p.strip()]
    for part in reversed(parts):
        part_norm = _normalize_text(part)
        if part_norm in _EXTRA_LOCATION_COUNTRY_MAP:
            return _EXTRA_LOCATION_COUNTRY_MAP[part_norm]
        raw_part = part.lower().strip()
        if raw_part in _EXTRA_LOCATION_COUNTRY_MAP:
            return _EXTRA_LOCATION_COUNTRY_MAP[raw_part]

    for country_name, region_tokens in COUNTRY_REGION_TOKENS.items():
        if country_name in COUNTRY_LANGUAGE_MAP and any(
            _contains_token(norm_loc, raw_lower, tok) for tok in region_tokens
        ):
            return country_name

    for tok, country_name in _EXTRA_LOCATION_COUNTRY_MAP.items():
        if _contains_token(norm_loc, raw_lower, tok):
            return country_name
    return ""


def _infer_search_locale(location: str = "", lang: str = "en") -> str:
    """Infer preferred search term locale from country/location and fallback UI language."""
    country = _resolve_location_country_for_language(location)
    if country and country in COUNTRY_LANGUAGE_MAP:
        return COUNTRY_LANGUAGE_MAP[country]

    norm_lang = translator.normalize_target_lang(lang)
    return norm_lang if (norm_lang and norm_lang in _EXP_SEARCH_TERMS_BY_LOCALE) else "en"


def adapt_keywords_for_location(
    keywords: str, location: str = "", lang: str = "en"
) -> Tuple[str, str, str]:
    """Translate user keywords into the selected country's predominant job language when different.

    Returns (adapted_keywords, target_locale, original_keywords).
    """
    cleaned = (keywords or "").strip()
    country = _resolve_location_country_for_language(location)
    target_locale = COUNTRY_LANGUAGE_MAP[country] if country in COUNTRY_LANGUAGE_MAP else _infer_search_locale(location, lang)
    if not cleaned or not country:
        return cleaned, target_locale, cleaned

    # Keep universal IT acronyms/phrases untouched while detecting genuine natural language
    masked = _UNIVERSAL_TECH_PHRASES_RE.sub(" ", cleaned).strip()
    if not masked:
        return cleaned, target_locale, cleaned

    detected_src = translator.detect_source_language(masked, target_locale, strict=True)
    if not detected_src or detected_src == target_locale:
        return cleaned, target_locale, cleaned

    try:
        translated_kw, _ = translator.translate_text_with_meta(
            cleaned, target_locale, source_lang=detected_src
        )
    except Exception:
        translated_kw = cleaned

    final_kw = (translated_kw or "").strip() or cleaned
    return final_kw, target_locale, cleaned


def _combine_keyword_with_term(keywords: str, term: str) -> str:
    """Append an experience term to keywords without duplicating existing phrasing."""
    cleaned_kw = (keywords or "").strip()
    cleaned_term = (term or "").strip()
    if not cleaned_term:
        return cleaned_kw
    if not cleaned_kw:
        return cleaned_term

    norm_kw = _normalize_text(cleaned_kw)
    norm_term = _normalize_text(cleaned_term)
    if re.search(rf"(?<!\w){re.escape(norm_term)}(?!\w)", norm_kw):
        return cleaned_kw
    return f"{cleaned_kw} {cleaned_term}"


def _extract_ordered_experience_targets(
    experience_level: Optional[Union[str, List[str]]],
) -> Tuple[List[Tuple[str, List[str]]], List[str]]:
    """Return ordered (target, [token]) pairs plus normalized original filter tokens."""
    if not experience_level:
        return [], []

    raw_items = [experience_level] if isinstance(experience_level, str) else list(experience_level)
    target_to_tokens: Dict[str, List[str]] = {}
    ordered_targets: List[str] = []
    original_tokens: List[str] = []

    def _register(token: str) -> None:
        if token not in original_tokens:
            original_tokens.append(token)
        for target in _EXP_TOKEN_TO_TARGETS.get(token, ()):
            if target not in target_to_tokens:
                target_to_tokens[target] = []
                ordered_targets.append(target)
            if token not in target_to_tokens[target]:
                target_to_tokens[target].append(token)

    for item in raw_items:
        if item is None:
            continue
        raw = str(item).strip()
        if not raw:
            continue
        if raw in _EXP_TOKEN_TO_TARGETS:
            _register(raw)
        else:
            for part in raw.split(","):
                tok = part.strip()
                if tok in _EXP_TOKEN_TO_TARGETS:
                    _register(tok)

    paired = [
        (target, target_to_tokens[target] or [_TARGET_DEFAULT_EXP_TOKEN[target]])
        for target in ordered_targets
    ]
    return paired, original_tokens


def build_experience_search_queries(
    keywords: str,
    experience_level: Optional[Union[str, List[str]]] = None,
    location: str = "",
    lang: str = "en",
) -> List[Tuple[str, Optional[List[str]], bool]]:
    """Build ordered (keywords, experience_tokens, is_primary) queries adapted to country language & levels."""
    adapted_kw, locale, original_kw = adapt_keywords_for_location(keywords, location=location, lang=lang)
    has_adapted_alt = bool(adapted_kw and original_kw and _normalize_text(adapted_kw) != _normalize_text(original_kw))

    ordered_targets, original_tokens = _extract_ordered_experience_targets(experience_level)
    if not ordered_targets:
        if has_adapted_alt:
            return [(adapted_kw, None, True), (original_kw, None, False)]
        return [(adapted_kw, None, True)]

    terms_by_target = _EXP_SEARCH_TERMS_BY_LOCALE.get(locale, _EXP_SEARCH_TERMS_BY_LOCALE["en"])
    existing_kw_targets = detect_title_experience_levels(adapted_kw)

    primary_queries: List[Tuple[str, Optional[List[str]], bool]] = []
    secondary_queries: List[Tuple[str, Optional[List[str]], bool]] = []

    for target, target_tokens in ordered_targets:
        terms = terms_by_target.get(target, ())
        if not terms or target in existing_kw_targets:
            primary_queries.append((adapted_kw, target_tokens, True))
        else:
            primary_kw = _combine_keyword_with_term(adapted_kw, terms[0])
            primary_queries.append((primary_kw, target_tokens, True))
            for alt_term in terms[1:]:
                alt_kw = _combine_keyword_with_term(adapted_kw, alt_term)
                secondary_queries.append((alt_kw, target_tokens, False))

        # LinkedIn frequently tags Tech Lead and Trainee roles as "Not applicable";
        # keep an unfiltered f_E pass in reserve to catch them if Pass 1 needs more jobs.
        if target in _TITLE_REQUIRED_TARGETS:
            lead_term_list = terms if (terms and target not in existing_kw_targets) else ()
            if lead_term_list:
                secondary_queries.append((_combine_keyword_with_term(adapted_kw, lead_term_list[0]), None, False))
            elif adapted_kw:
                secondary_queries.append((adapted_kw, None, False))

    if original_tokens:
        secondary_queries.append((adapted_kw, original_tokens, False))
        if has_adapted_alt:
            secondary_queries.append((original_kw, original_tokens, False))

    deduped: List[Tuple[str, Optional[List[str]], bool]] = []
    seen_keys: set[Tuple[str, Tuple[str, ...]]] = set()
    for q_kw, q_tokens, is_primary in primary_queries + secondary_queries:
        key = (_normalize_text(q_kw), tuple(q_tokens or []))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append((q_kw, q_tokens, is_primary))

    return deduped


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
    exp_codes = _expand_experience_linkedin_codes(experience_level)
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
    place: Union[List[str], str],
    limit_jobs: int,
    experience_level: Optional[Union[List[str], str]] = None,
    sort_by: str = "DD",
    easy_apply: bool = False,
    lang: str = "en",
) -> int:
    """Return configured job limit clamped to [MIN_LIMIT_JOBS, MAX_LIMIT_JOBS]."""
    if limit_jobs <= 0:
        return MIN_LIMIT_JOBS
    return max(MIN_LIMIT_JOBS, min(limit_jobs, MAX_LIMIT_JOBS))


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
                    elif norm_h3 in WORK_MODE_HEADERS:
                        wt_code = WORK_MODE_VALUE_CODES.get(norm_val)
                        if wt_code:
                            detail["work_mode_code"] = wt_code

            if "work_mode_code" not in detail:
                inferred_wt = detect_work_mode(detail)
                if inferred_wt:
                    detail["work_mode_code"] = inferred_wt

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
            effective_limit = (
                max(MIN_LIMIT_JOBS, min(limit_jobs, MAX_LIMIT_JOBS))
                if limit_jobs > 0
                else MIN_LIMIT_JOBS
            )
            search_queries = build_experience_search_queries(
                keywords,
                experience_level=experience_level,
                location=location,
                lang=lang,
            )
            primary_kw = search_queries[0][0] if search_queries else keywords
            total_jobs = get_job_count(
                session,
                primary_kw,
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
            jobs_state.set_total(total_jobs, run_id=run_id)

            primary_count = max(1, sum(1 for _, _, is_primary in search_queries if is_primary))
            per_primary_quota = (
                max(1, math.ceil(effective_limit / primary_count))
                if primary_count > 1
                else effective_limit
            )
            jobs_state.log(
                f"Buscando até ~{total_jobs} vagas ({len(search_queries)} consulta(s) direcionada(s))",
                run_id=run_id,
            )

            job_ids: List[str] = []
            seen_ids: set[str] = set()
            summaries: Dict[str, Dict[str, Any]] = {}

            for q_idx, (q_keywords, q_exp_tokens, is_primary) in enumerate(search_queries):
                if len(job_ids) >= effective_limit:
                    break
                if not jobs_state.is_run_active(run_id):
                    jobs_state.stop(run_id=run_id)
                    return

                remaining_total = effective_limit - len(job_ids)
                query_quota = (
                    min(remaining_total, per_primary_quota)
                    if (primary_count > 1 and is_primary)
                    else remaining_total
                )
                query_pages = max(1, math.ceil(query_quota / PAGE_SIZE)) + (3 if canonical_country else 0)
                added_for_query = 0
                start_offset = 0

                for page in range(query_pages):
                    if not jobs_state.is_run_active(run_id):
                        jobs_state.stop(run_id=run_id)
                        return

                    new_ids = get_job_ids_per_page(
                        session,
                        q_keywords,
                        location,
                        time_range,
                        distance,
                        job_type,
                        place,
                        start_offset,
                        experience_level=q_exp_tokens,
                        sort_by=sort_by,
                        easy_apply=easy_apply,
                        summaries_out=summaries,
                        run_id=run_id,
                        lang=lang,
                    )
                    added_on_page = 0
                    unseen_in_page = 0
                    for jid in new_ids:
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        unseen_in_page += 1
                        summary_loc = summaries.get(jid, {}).get("location")
                        if canonical_country and summary_loc and not job_matches_country(summary_loc, canonical_country):
                            continue
                        job_ids.append(jid)
                        added_on_page += 1
                        added_for_query += 1
                        if len(job_ids) >= effective_limit or added_for_query >= query_quota:
                            break

                    progress = min(
                        50.0,
                        max(
                            ((q_idx + (page + 1) / query_pages) / max(1, len(search_queries))) * 50.0,
                            (len(job_ids) / max(1, effective_limit)) * 50.0,
                        ),
                    )
                    jobs_state.update_progress(
                        progress,
                        f"Coletando páginas: {page + 1}/{query_pages} ({len(job_ids)} IDs)",
                        run_id=run_id,
                        status_code="statusCollectingPages",
                        status_params={"page": page + 1, "pages": query_pages, "count": len(job_ids)},
                    )
                    if (
                        not new_ids
                        or unseen_in_page == 0
                        or len(job_ids) >= effective_limit
                        or added_for_query >= query_quota
                    ):
                        break
                    start_offset += max(len(new_ids), PAGE_SIZE)
                    sleep(0.2)

            if not jobs_state.is_run_active(run_id):
                jobs_state.stop(run_id=run_id)
                return

            job_ids = job_ids[:effective_limit]

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
                            inferred_wt = detect_work_mode(detail)
                            if inferred_wt and not detail.get("work_mode_code"):
                                detail["work_mode_code"] = inferred_wt
                            detail["match_category"] = classify_job_match(
                                detail,
                                requested_location=location,
                                experience_level=experience_level,
                                work_mode=place,
                            )
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
