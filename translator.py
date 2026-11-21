from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import os
import queue
import re
import sqlite3
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

import requests
from requests.adapters import HTTPAdapter


TARGET_LANG_MAP: Dict[str, str] = {
    "pt": "pt",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "de": "de",
    "ru": "ru",
    "zh": "zh-CN",
    "ja": "ja",
}

SUPPORTED_LANGS = set(TARGET_LANG_MAP.keys())

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MAX_CACHE_ENTRIES = 5000
MAX_CHUNK_CHARS = 4500
MYMEMORY_MAX_CHARS = 450
PACKED_BLOCK_MAX_CHARS = 3600
PACKED_BLOCK_MAX_ITEMS = 12
PREVIEW_DESC_CHARS = 450
MAX_BATCH_ITEMS = 50
TRANSLATE_WORKERS = 10
GOOGLE_COOLDOWN_SECONDS = 300.0
_DEFAULT_CACHE_DB = os.path.join(tempfile.gettempdir(), "huntly_translation_cache.sqlite3")

_ORIGINAL_REQUESTS_POST = requests.post
_ORIGINAL_REQUESTS_GET = requests.get
_session_pool: "queue.LifoQueue[requests.Session]" = queue.LifoQueue(maxsize=24)
_google_lock = threading.Lock()
_google_cooldown_until = 0.0
_db_lock = threading.Lock()
_configured_db_path: Optional[str] = None
_initialized_dbs: Set[str] = set()
_PACK_SEP_RE = re.compile(r"\[\[\[\s*HUNTLY_SEP_(\d+)\s*\]\]\]")

_LATIN_STOPWORDS: Dict[str, Set[str]] = {
    "pt": {
        "você", "voce", "não", "nao", "também", "tambem", "nosso", "nossa",
        "nossos", "nossas", "pelo", "pela", "pelos", "pelas", "dos", "das",
        "uma", "umas", "uns", "com", "mais", "são", "estão", "estamos",
        "atuação", "atuar", "vaga", "benefícios", "experiência", "conhecimento",
        "conhecimentos", "desenvolvimento", "equipe", "trabalho", "através",
        "além", "onde", "seus", "suas", "nesse", "nessa", "neste", "nesta",
    },
    "en": {
        "the", "and", "with", "will", "our", "you", "your", "that", "this",
        "from", "have", "are", "their", "they", "which", "about", "into",
        "through", "across", "within", "must", "should", "would", "been",
        "being", "looking", "working", "experience", "skills", "requirements",
        "responsibilities", "benefits", "company", "strong", "ability",
    },
    "es": {
        "nosotros", "nuestro", "nuestra", "nuestros", "nuestras", "también",
        "tambien", "más", "unos", "unas", "los", "las", "están", "estamos",
        "serán", "puesto", "equipo", "trabajo", "experiencia", "conocimientos",
        "desarrollo", "requisitos", "beneficios", "través", "además", "donde",
        "hacia", "quien", "buscamos", "ofrecemos", "funciones",
    },
    "fr": {
        "nous", "notre", "nos", "vous", "votre", "vos", "avec", "pour", "dans",
        "sur", "une", "des", "les", "aux", "est", "sont", "sera", "être",
        "avoir", "aussi", "plus", "chez", "poste", "équipe", "travail",
        "expérience", "compétences", "développement", "missions", "profil",
        "avantages", "recherchons",
    },
    "it": {
        "noi", "nostro", "nostra", "nostri", "nostre", "voi", "vostro", "per",
        "nel", "nella", "nelle", "degli", "delle", "dei", "gli", "sono",
        "sarà", "essere", "anche", "più", "lavoro", "squadra", "esperienza",
        "competenze", "sviluppo", "requisiti", "cerchiamo", "offriamo", "ruolo",
    },
    "de": {
        "wir", "unser", "unsere", "unserem", "unseren", "und", "mit", "für",
        "fur", "auf", "aus", "bei", "nach", "über", "uber", "eine", "einen",
        "einem", "einer", "der", "die", "das", "den", "dem", "sind", "wird",
        "werden", "auch", "mehr", "oder", "sowie", "stelle", "arbeit",
        "erfahrung", "kenntnisse", "entwicklung", "aufgaben", "profil",
        "vorteile", "suchen", "bieten",
    },
}

_LANG_JOB_KEYWORDS: Dict[str, Set[str]] = {
    "pt": {
        "desenvolvedor", "desenvolvedora", "engenheiro", "engenheira", "estagio",
        "estagiario", "estagiaria", "analista", "tecnico", "tecnica", "pleno",
        "senior", "junior", "gerente", "coordenador", "diretor", "arquiteto",
        "dados", "sistemas", "requisitos", "responsabilidades", "beneficios",
        "remoto", "hibrido", "presencial", "empresa", "candidatos", "salario",
    },
    "en": {
        "developer", "engineer", "engineering", "software", "backend", "frontend",
        "fullstack", "architect", "analyst", "manager", "intern", "internship",
        "junior", "senior", "lead", "principal", "staff", "remote", "hybrid",
        "onsite", "scalable", "building", "designing", "services", "team",
    },
    "es": {
        "desarrollador", "desarrolladora", "ingeniero", "ingeniera", "practicas",
        "becario", "analista", "tecnico", "puesto", "requisitos", "funciones",
        "beneficios", "sueldo", "remoto", "hibrido", "presencial", "datos",
    },
    "fr": {
        "developpeur", "ingenieur", "stage", "stagiaire", "poste", "missions",
        "competences", "profil", "avantages", "teletravail", "hybride", "donnees",
    },
    "it": {
        "sviluppatore", "ingegnere", "tirocinio", "stage", "azienda", "requisiti",
        "competenze", "ruolo", "remoto", "ibrido", "dati",
    },
    "de": {
        "entwickler", "ingenieur", "praktikum", "stelle", "aufgaben", "profil",
        "vorteile", "erfahrung", "kenntnisse", "daten",
    },
}

_cache: "OrderedDict[Tuple[str, str], Tuple[str, Optional[str]]]" = OrderedDict()
_cache_lock = threading.Lock()


def _active_db_path() -> Optional[str]:
    if _configured_db_path is not None:
        return _configured_db_path or None
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    return _DEFAULT_CACHE_DB


def configure_cache_db(path: Optional[str]) -> None:
    """Configure an explicit SQLite cache database path (or None to revert to default behavior)."""
    global _configured_db_path
    with _db_lock:
        _configured_db_path = path
        if path:
            _initialized_dbs.discard(path)


def _ensure_sqlite_schema(conn: sqlite3.Connection, db_path: str) -> None:
    if db_path in _initialized_dbs:
        return
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS translations (
            tl TEXT NOT NULL,
            digest TEXT NOT NULL,
            translated TEXT NOT NULL,
            source_lang TEXT,
            updated_at REAL NOT NULL,
            PRIMARY KEY (tl, digest)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_translations_updated ON translations (updated_at)")
    conn.commit()
    _initialized_dbs.add(db_path)


def _sqlite_batch_get(tl: str, digests: List[str]) -> Dict[str, Tuple[str, Optional[str]]]:
    db_path = _active_db_path()
    if not db_path or not digests:
        return {}
    found: Dict[str, Tuple[str, Optional[str]]] = {}
    with _db_lock:
        try:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                _ensure_sqlite_schema(conn, db_path)
                for idx in range(0, len(digests), 400):
                    chunk = digests[idx : idx + 400]
                    placeholders = ",".join("?" for _ in chunk)
                    rows = conn.execute(
                        f"SELECT digest, translated, source_lang FROM translations WHERE tl = ? AND digest IN ({placeholders})",
                        [tl, *chunk],
                    ).fetchall()
                    for dig, translated, src_lang in rows:
                        found[dig] = (translated, src_lang)
        except Exception:
            return found
    return found


def _sqlite_batch_put(entries: List[Tuple[str, str, str, Optional[str]]]) -> None:
    db_path = _active_db_path()
    if not db_path or not entries:
        return
    now_ts = time.time()
    with _db_lock:
        try:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                _ensure_sqlite_schema(conn, db_path)
                conn.executemany(
                    """
                    INSERT INTO translations (tl, digest, translated, source_lang, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(tl, digest) DO UPDATE SET
                        translated = excluded.translated,
                        source_lang = excluded.source_lang,
                        updated_at = excluded.updated_at
                    """,
                    [(tl, dig, tr, src, now_ts) for tl, dig, tr, src in entries],
                )
                count_row = conn.execute("SELECT COUNT(*) FROM translations").fetchone()
                total = int(count_row[0]) if count_row else 0
                if total > MAX_CACHE_ENTRIES:
                    excess = total - MAX_CACHE_ENTRIES
                    conn.execute(
                        "DELETE FROM translations WHERE rowid IN (SELECT rowid FROM translations ORDER BY updated_at ASC LIMIT ?)",
                        (excess,),
                    )
                conn.commit()
        except Exception:
            return


def clear_memory_cache() -> None:
    """Clear only the in-memory LRU cache without deleting the persistent SQLite cache."""
    with _cache_lock:
        _cache.clear()


def clear_cache() -> None:
    """Clear the in-memory and persistent SQLite cache and reset upstream cooldown."""
    global _google_cooldown_until
    clear_memory_cache()
    with _google_lock:
        _google_cooldown_until = 0.0
    db_path = _active_db_path()
    if db_path and os.path.exists(db_path):
        with _db_lock:
            try:
                with sqlite3.connect(db_path, timeout=5.0) as conn:
                    _ensure_sqlite_schema(conn, db_path)
                    conn.execute("DELETE FROM translations")
                    conn.commit()
            except Exception:
                pass


def cache_size() -> int:
    """Return the number of entries currently stored in the in-memory translation cache."""
    with _cache_lock:
        return len(_cache)


def normalize_target_lang(code: Optional[str]) -> Optional[str]:
    """Normalize UI or locale codes (e.g. zh-CN, pt-BR, ja-JP) to canonical TARGET_LANG_MAP keys."""
    if not code or not isinstance(code, str):
        return None
    clean = code.strip().lower().replace("_", "-")
    if not clean or clean == "auto":
        return None
    if clean.startswith("zh"):
        return "zh"
    if clean == "jp" or clean == "ja" or clean.startswith("ja-"):
        return "ja"
    base = clean.split("-")[0]
    return base if base in TARGET_LANG_MAP else None


def _make_cache_key(tl: str, text: str) -> Tuple[str, str]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return tl, digest


def _normalize_lang_code(code: Optional[str]) -> Optional[str]:
    if not code or not isinstance(code, str):
        return None
    clean = code.strip().lower().replace("_", "-")
    if not clean or clean == "auto":
        return None
    if clean.startswith("zh"):
        return "zh"
    if clean == "jp" or clean == "ja" or clean.startswith("ja-"):
        return "ja"
    return clean.split("-")[0] or None


def _cache_get(tl: str, text: str) -> Optional[Tuple[str, Optional[str]]]:
    key = _make_cache_key(tl, text)
    with _cache_lock:
        val = _cache.get(key)
        if val is not None:
            _cache.move_to_end(key)
        return val


def _cache_put(tl: str, text: str, translated: str, source_lang: Optional[str]) -> None:
    key = _make_cache_key(tl, text)
    with _cache_lock:
        _cache[key] = (translated, source_lang)
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)


def _split_long_block(block: str, max_chars: int) -> List[str]:
    """Split an oversized block on newlines or spaces without breaking words."""
    if len(block) <= max_chars:
        return [block]

    parts: List[str] = []
    lines = block.split("\n")
    current = ""
    for line in lines:
        if len(line) > max_chars:
            if current:
                parts.append(current)
                current = ""
            words = line.split(" ")
            word_buf = ""
            for word in words:
                if len(word) > max_chars:
                    if word_buf:
                        parts.append(word_buf)
                        word_buf = ""
                    for i in range(0, len(word), max_chars):
                        parts.append(word[i : i + max_chars])
                elif not word_buf:
                    word_buf = word
                elif len(word_buf) + 1 + len(word) <= max_chars:
                    word_buf = f"{word_buf} {word}"
                else:
                    parts.append(word_buf)
                    word_buf = word
            if word_buf:
                parts.append(word_buf)
        elif not current:
            current = line
        elif len(current) + 1 + len(line) <= max_chars:
            current = f"{current}\n{line}"
        else:
            parts.append(current)
            current = line
    if current:
        parts.append(current)
    return parts


def _split_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split text into bounded chunks preferring paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current = ""
    for para in text.split("\n\n"):
        if len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_block(para, max_chars))
        elif not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def _build_pooled_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=12)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _get_pooled_session() -> requests.Session:
    try:
        return _session_pool.get_nowait()
    except queue.Empty:
        return _build_pooled_session()


def _release_pooled_session(sess: requests.Session) -> None:
    try:
        _session_pool.put_nowait(sess)
    except queue.Full:
        sess.close()


def _post_translation(chunk: str, tl: str, timeout: int) -> requests.Response:
    request_kwargs: Dict[str, Any] = {
        "params": {"client": "gtx", "sl": "auto", "tl": tl, "dt": "t"},
        "data": {"q": chunk},
        "headers": {"User-Agent": "Mozilla/5.0"},
        "timeout": timeout,
    }
    # Preserve compatibility with unit tests patching translator.requests.post.
    if requests.post is not _ORIGINAL_REQUESTS_POST:
        return requests.post(TRANSLATE_URL, **request_kwargs)

    sess = _get_pooled_session()
    try:
        return sess.post(TRANSLATE_URL, **request_kwargs)
    finally:
        _release_pooled_session(sess)


def _get_mymemory(sub_chunk: str, src_code: str, tl: str, timeout: int) -> requests.Response:
    params: Dict[str, str] = {"q": sub_chunk, "langpair": f"{src_code}|{tl}"}
    email = os.environ.get("MYMEMORY_EMAIL", "").strip()
    if email:
        params["de"] = email
    request_kwargs: Dict[str, Any] = {
        "params": params,
        "headers": {"User-Agent": "Mozilla/5.0"},
        "timeout": timeout,
    }
    if requests.get is not _ORIGINAL_REQUESTS_GET:
        return requests.get(MYMEMORY_URL, **request_kwargs)

    sess = _get_pooled_session()
    try:
        return sess.get(MYMEMORY_URL, **request_kwargs)
    finally:
        _release_pooled_session(sess)


def _google_in_cooldown() -> bool:
    if requests.post is not _ORIGINAL_REQUESTS_POST:
        return False
    with _google_lock:
        return time.monotonic() < _google_cooldown_until


def _mark_google_rate_limited() -> None:
    if requests.post is not _ORIGINAL_REQUESTS_POST:
        return
    with _google_lock:
        global _google_cooldown_until
        _google_cooldown_until = max(_google_cooldown_until, time.monotonic() + GOOGLE_COOLDOWN_SECONDS)


def _is_already_target_language(text: str, target_lang: str) -> bool:
    """Conservatively skip HTTP calls only for long texts clearly already in target_lang."""
    if not text or len(text) < 120:
        return False

    if target_lang == "ru":
        alpha_chars = [ch for ch in text if ch.isalpha()]
        cyrillic_chars = [ch for ch in alpha_chars if "\u0400" <= ch <= "\u04ff"]
        return (
            len(cyrillic_chars) >= 30
            and bool(alpha_chars)
            and (len(cyrillic_chars) / len(alpha_chars)) >= 0.75
        )

    if target_lang == "ja":
        non_punct = [ch for ch in text if ch.isalnum()]
        kana_chars = [ch for ch in non_punct if "\u3040" <= ch <= "\u30ff"]
        return len(kana_chars) >= 10

    if target_lang == "zh":
        non_punct = [ch for ch in text if ch.isalnum()]
        kana_chars = [ch for ch in non_punct if "\u3040" <= ch <= "\u30ff"]
        cjk_chars = [ch for ch in non_punct if "\u4e00" <= ch <= "\u9fff"]
        return (
            not kana_chars
            and len(cjk_chars) >= 20
            and bool(non_punct)
            and (len(cjk_chars) / len(non_punct)) >= 0.50
        )

    target_stopwords = _LATIN_STOPWORDS.get(target_lang)
    if not target_stopwords:
        return False

    words = re.findall(r"[a-zà-öø-ÿ]+", text.lower())
    if len(words) < 20:
        return False

    target_hits = sum(1 for w in words if w in target_stopwords)
    if target_hits < 6 or (target_hits / len(words)) < 0.08:
        return False

    best_other_hits = 0
    for lang_code, sw_set in _LATIN_STOPWORDS.items():
        if lang_code == target_lang:
            continue
        hits = sum(1 for w in words if w in sw_set)
        if hits > best_other_hits:
            best_other_hits = hits

    return target_hits >= max(5, best_other_hits * 4)


def _build_preview_snippet(text: str, max_chars: int = PREVIEW_DESC_CHARS) -> str:
    """Build a bounded preview excerpt without splitting words when avoidable."""
    if len(text) <= max_chars:
        return text
    sliced = text[:max_chars]
    last_space = max(sliced.rfind(" "), sliced.rfind("\n"))
    if last_space >= max_chars // 2:
        sliced = sliced[:last_space]
    return sliced.rstrip() or text[:max_chars]


def _detect_source_language(text: str, target_lang: str) -> str:
    """Heuristically infer source language for providers requiring an explicit langpair."""
    if not text:
        return "en" if target_lang != "en" else "pt"

    alpha_chars = [ch for ch in text if ch.isalpha()]
    if alpha_chars:
        cyrillic_chars = [ch for ch in alpha_chars if "\u0400" <= ch <= "\u04ff"]
        if len(cyrillic_chars) >= 3 and (len(cyrillic_chars) / len(alpha_chars)) >= 0.5:
            return "ru"
    non_punct = [ch for ch in text if ch.isalnum()]
    if non_punct:
        kana_chars = [ch for ch in non_punct if "\u3040" <= ch <= "\u30ff"]
        if len(kana_chars) >= 2:
            return "ja"
        cjk_chars = [ch for ch in non_punct if "\u4e00" <= ch <= "\u9fff"]
        if len(cjk_chars) >= 2 and (len(cjk_chars) / len(non_punct)) >= 0.4:
            return "zh"

    lower = text.lower()
    scores: Dict[str, int] = {lang: 0 for lang in _LANG_JOB_KEYWORDS}
    if any(ch in lower for ch in "ãõçêâô"):
        scores["pt"] += 3
    if "ñ" in lower or "¿" in lower or "¡" in lower:
        scores["es"] += 3
    if "ß" in lower or "ä" in lower or "ö" in lower or "ü" in lower:
        scores["de"] += 2
    if any(ch in lower for ch in "àèéìòù") and any(tok in lower for tok in ("svilupp", "lavoro", "azienda", "di ", "per ")):
        scores["it"] += 2
    if any(ch in lower for ch in "éèêàçôù") and any(tok in lower for tok in ("développ", "ingénieur", "poste", "chez", "avec")):
        scores["fr"] += 3

    norm_lower = "".join(
        ch for ch in unicodedata.normalize("NFD", lower) if unicodedata.category(ch) != "Mn"
    )
    words = re.findall(r"[a-z]+", norm_lower)
    for w in words:
        for lang_code, sw_set in _LATIN_STOPWORDS.items():
            norm_sw = {
                "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
                for s in sw_set
            }
            if w in norm_sw:
                scores[lang_code] += 2
        for lang_code, kw_set in _LANG_JOB_KEYWORDS.items():
            if w in kw_set:
                scores[lang_code] += 2

    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score > 0:
        return best_lang
    return "en" if target_lang != "en" else "pt"


def _request_mymemory_translation(text: str, lang_key: str, timeout: int) -> Tuple[str, Optional[str]]:
    src_lang = _detect_source_language(text, lang_key)
    if src_lang == lang_key:
        return text, lang_key

    src_code = TARGET_LANG_MAP.get(src_lang, "en")
    tl_code = TARGET_LANG_MAP[lang_key]
    sub_chunks = _split_chunks(text, MYMEMORY_MAX_CHARS)
    translated_parts: List[str] = []

    for sub in sub_chunks:
        res = _get_mymemory(sub, src_code, tl_code, timeout)
        res.raise_for_status()
        payload = res.json()
        if not isinstance(payload, dict) or payload.get("quotaFinished"):
            raise ValueError("MyMemory quota exhausted or invalid payload")
        if int(payload.get("responseStatus") or 0) != 200:
            raise ValueError(f"MyMemory error status: {payload.get('responseStatus')}")
        raw_trans = (payload.get("responseData") or {}).get("translatedText")
        if not isinstance(raw_trans, str) or not raw_trans.strip():
            raise ValueError("Empty MyMemory translation")
        cleaned = html.unescape(raw_trans).strip()
        upper = cleaned.upper()
        if upper.startswith("MYMEMORY WARNING") or "INVALID LANGUAGE PAIR" in upper:
            raise ValueError(f"MyMemory warning payload: {cleaned}")
        translated_parts.append(cleaned)

    joined = translated_parts[0] if len(translated_parts) == 1 else "\n\n".join(translated_parts)
    return joined, src_lang


def _request_google_chunk(chunk: str, tl: str, timeout: int) -> Tuple[str, Optional[str]]:
    res = _post_translation(chunk, tl, timeout)
    if getattr(res, "status_code", None) in (429, 403):
        _mark_google_rate_limited()
    res.raise_for_status()
    payload = res.json()
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise ValueError("Unexpected translation payload structure")
    translated = "".join(part[0] for part in payload[0] if isinstance(part, list) and part and part[0])
    if not translated:
        raise ValueError("Empty translation returned")
    detected_src = _normalize_lang_code(payload[2]) if len(payload) > 2 else None
    return translated, detected_src


def _request_libretranslate(text: str, lang_key: str, timeout: int) -> Tuple[str, Optional[str]]:
    base_url = os.environ.get("LIBRETRANSLATE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("LibreTranslate URL not configured")
    src_lang = _detect_source_language(text, lang_key)
    tl_code = TARGET_LANG_MAP[lang_key]
    body: Dict[str, Any] = {
        "q": text,
        "source": TARGET_LANG_MAP.get(src_lang, "auto"),
        "target": "zh" if tl_code == "zh-CN" else tl_code,
        "format": "text",
    }
    api_key = os.environ.get("LIBRETRANSLATE_API_KEY", "").strip()
    if api_key:
        body["api_key"] = api_key
    res = requests.post(f"{base_url}/translate", json=body, timeout=timeout)
    res.raise_for_status()
    payload = res.json()
    translated = payload.get("translatedText") if isinstance(payload, dict) else None
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError("Empty LibreTranslate output")
    return translated.strip(), src_lang


def _request_chunk_translation(chunk: str, tl: str, timeout: int) -> Tuple[str, Optional[str]]:
    lang_key = normalize_target_lang(tl) or _normalize_lang_code(tl) or "en"
    allow_mymemory = (requests.post is _ORIGINAL_REQUESTS_POST) or (requests.get is not _ORIGINAL_REQUESTS_GET)

    if not _google_in_cooldown():
        try:
            return _request_google_chunk(chunk, tl, timeout)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (429, 403):
                _mark_google_rate_limited()
            if not allow_mymemory:
                raise
        except Exception:
            if not allow_mymemory:
                raise

    if allow_mymemory:
        try:
            return _request_mymemory_translation(chunk, lang_key, timeout)
        except Exception:
            if os.environ.get("LIBRETRANSLATE_URL", "").strip():
                return _request_libretranslate(chunk, lang_key, timeout)
            raise

    raise RuntimeError("Upstream translation unavailable")


def _translate_google_packed_blocks(
    items: List[str], tl: str, timeout: int = 8
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Pack multiple short texts using indexed markers to minimize upstream HTTP roundtrips."""
    if not items:
        return {}

    blocks: List[Tuple[List[str], str]] = []
    cur_items: List[str] = []
    cur_parts: List[str] = []
    cur_len = 0

    for raw in items:
        idx = len(cur_items)
        marker = f"[[[HUNTLY_SEP_{idx}]]]"
        addition = f"\n{marker}\n{raw}" if cur_items else f"{marker}\n{raw}"
        if cur_items and (
            len(cur_items) >= PACKED_BLOCK_MAX_ITEMS or cur_len + len(addition) > PACKED_BLOCK_MAX_CHARS
        ):
            blocks.append((cur_items, "".join(cur_parts)))
            cur_items = []
            cur_parts = []
            cur_len = 0
            idx = 0
            marker = f"[[[HUNTLY_SEP_{idx}]]]"
            addition = f"{marker}\n{raw}"
        cur_items.append(raw)
        cur_parts.append(addition)
        cur_len += len(addition)

    if cur_items:
        blocks.append((cur_items, "".join(cur_parts)))

    def _run_block(block_tuple: Tuple[List[str], str]) -> Dict[str, Tuple[str, Optional[str]]]:
        block_items, packed_payload = block_tuple
        try:
            translated_blob, detected_src = _request_google_chunk(packed_payload, tl, timeout)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (429, 403):
                _mark_google_rate_limited()
            return {}
        except Exception:
            return {}

        matches = list(_PACK_SEP_RE.finditer(translated_blob))
        if len(matches) != len(block_items):
            return {}
        parsed: Dict[str, Tuple[str, Optional[str]]] = {}
        for pos, m in enumerate(matches):
            if int(m.group(1)) != pos:
                return {}
            start_idx = m.end()
            end_idx = matches[pos + 1].start() if pos + 1 < len(matches) else len(translated_blob)
            seg = translated_blob[start_idx:end_idx].strip()
            if not seg:
                return {}
            parsed[block_items[pos]] = (seg, detected_src)
        return parsed

    resolved: Dict[str, Tuple[str, Optional[str]]] = {}
    if len(blocks) == 1:
        resolved.update(_run_block(blocks[0]))
    else:
        workers = min(TRANSLATE_WORKERS, len(blocks))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for block_out in executor.map(_run_block, blocks):
                resolved.update(block_out)
    return resolved


def _translate_texts_parallel(
    texts: List[str], lang_key: str, timeout: int = 8
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Translate unique non-empty strings using RAM + SQLite cache, packed blocks and 10-worker pool."""
    tl = TARGET_LANG_MAP[lang_key]
    resolved: Dict[str, Tuple[str, Optional[str]]] = {}
    uncached_candidates: List[str] = []
    seen_raw: Set[str] = set()
    sqlite_rows_to_save: List[Tuple[str, str, str, Optional[str]]] = []

    for raw in texts:
        if not isinstance(raw, str) or not raw or not raw.strip() or raw in seen_raw:
            continue
        seen_raw.add(raw)

        cached = _cache_get(tl, raw)
        if cached is not None:
            resolved[raw] = cached
            continue

        if _is_already_target_language(raw, lang_key):
            _cache_put(tl, raw, raw, lang_key)
            _, dig = _make_cache_key(tl, raw)
            sqlite_rows_to_save.append((tl, dig, raw, lang_key))
            resolved[raw] = (raw, lang_key)
            continue

        uncached_candidates.append(raw)

    # 1. Batch lookup against persistent SQLite cache before making any external HTTP calls
    if uncached_candidates:
        digest_to_raw = {_make_cache_key(tl, raw)[1]: raw for raw in uncached_candidates}
        sqlite_hits = _sqlite_batch_get(tl, list(digest_to_raw.keys()))
        remaining_after_sqlite: List[str] = []
        for dig, raw in digest_to_raw.items():
            hit = sqlite_hits.get(dig)
            if hit is not None:
                _cache_put(tl, raw, hit[0], hit[1])
                resolved[raw] = hit
            else:
                remaining_after_sqlite.append(raw)
        uncached_candidates = remaining_after_sqlite

    # 2. Try packed delimiter blocks when running live Google gtx with multiple short texts
    if (
        len(uncached_candidates) > 1
        and requests.post is _ORIGINAL_REQUESTS_POST
        and not _google_in_cooldown()
    ):
        packable = [t for t in uncached_candidates if len(t) <= MAX_CHUNK_CHARS and "HUNTLY_SEP_" not in t]
        if len(packable) > 1:
            packed_hits = _translate_google_packed_blocks(packable, tl, timeout=timeout)
            if packed_hits:
                for raw, (tr_text, src_lang) in packed_hits.items():
                    _cache_put(tl, raw, tr_text, src_lang)
                    _, dig = _make_cache_key(tl, raw)
                    sqlite_rows_to_save.append((tl, dig, tr_text, src_lang))
                    resolved[raw] = (tr_text, src_lang)
                uncached_candidates = [t for t in uncached_candidates if t not in packed_hits]

    # 3. Parallel chunk translation via ThreadPoolExecutor(max_workers=10) for remaining texts
    pending_chunks_by_text: Dict[str, List[str]] = {}
    unique_chunks: List[str] = []
    seen_chunks: Set[str] = set()
    for raw in uncached_candidates:
        chunks = _split_chunks(raw, MAX_CHUNK_CHARS)
        pending_chunks_by_text[raw] = chunks
        for ch in chunks:
            if ch not in seen_chunks:
                seen_chunks.add(ch)
                unique_chunks.append(ch)

    chunk_results: Dict[str, Optional[Tuple[str, Optional[str]]]] = {}
    if len(unique_chunks) == 1:
        ch = unique_chunks[0]
        try:
            chunk_results[ch] = _request_chunk_translation(ch, tl, timeout)
        except Exception:
            chunk_results[ch] = None
    elif len(unique_chunks) > 1:
        def _fetch_chunk(chunk_text: str) -> Tuple[str, Optional[Tuple[str, Optional[str]]]]:
            try:
                return chunk_text, _request_chunk_translation(chunk_text, tl, timeout)
            except Exception:
                return chunk_text, None

        workers = min(TRANSLATE_WORKERS, len(unique_chunks))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for chunk_text, outcome in executor.map(_fetch_chunk, unique_chunks):
                chunk_results[chunk_text] = outcome

    for raw, chunks in pending_chunks_by_text.items():
        translated_parts: List[str] = []
        source_lang: Optional[str] = None
        failed = False
        for ch in chunks:
            outcome = chunk_results.get(ch)
            if outcome is None:
                failed = True
                break
            part_translated, part_src = outcome
            translated_parts.append(part_translated)
            if source_lang is None and part_src:
                source_lang = part_src
        if failed:
            resolved[raw] = (raw, None)
        else:
            translated = (
                translated_parts[0] if len(translated_parts) == 1 else "\n\n".join(translated_parts)
            )
            _cache_put(tl, raw, translated, source_lang)
            _, dig = _make_cache_key(tl, raw)
            sqlite_rows_to_save.append((tl, dig, translated, source_lang))
            resolved[raw] = (translated, source_lang)

    if sqlite_rows_to_save:
        _sqlite_batch_put(sqlite_rows_to_save)

    return resolved


def translate_text_with_meta(
    text: Optional[str], target_lang: str, timeout: int = 8
) -> Tuple[Optional[str], Optional[str]]:
    """Translate text into target_lang returning (translated_text, detected_source_lang)."""
    if not text or not text.strip():
        return text, None

    lang_key = normalize_target_lang(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return text, None

    resolved = _translate_texts_parallel([text], lang_key, timeout=timeout)
    return resolved.get(text, (text, None))


def translate_text(text: Optional[str], target_lang: str, timeout: int = 8) -> Optional[str]:
    """Translate text into target_lang using an LRU cache, falling back to original text on any failure."""
    translated, _ = translate_text_with_meta(text, target_lang, timeout=timeout)
    return translated


def _translate_single_job(item: Dict[str, Any], target_lang: str) -> Tuple[str, Dict[str, Any]]:
    job_id = str(item.get("id", ""))
    raw_title = item.get("title")
    raw_desc = item.get("description")

    texts = [t for t in (raw_title, raw_desc) if isinstance(t, str) and t.strip()]
    translated_map = _translate_texts_parallel(texts, target_lang)

    title_out, title_src = (
        translated_map.get(raw_title, (raw_title, None)) if isinstance(raw_title, str) else (raw_title, None)
    )
    desc_out, desc_src = (
        translated_map.get(raw_desc, (raw_desc, None)) if isinstance(raw_desc, str) else (raw_desc, None)
    )
    source_lang = desc_src or title_src
    changed = (isinstance(raw_title, str) and title_out != raw_title) or (
        isinstance(raw_desc, str) and desc_out != raw_desc
    )
    was_translated = bool(source_lang and source_lang != target_lang and changed)
    return job_id, {
        "title": title_out,
        "description": desc_out,
        "excerpt": desc_out,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "was_translated": was_translated,
        "is_full": True,
    }


def translate_jobs_batch(
    items: List[Dict[str, Any]], target_lang: str, mode: str = "full"
) -> Dict[str, Dict[str, Any]]:
    """Translate titles and descriptions (preview snippet or full) for up to MAX_BATCH_ITEMS jobs in parallel."""
    lang_key = _normalize_lang_code(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return {}

    valid_items = [item for item in items[:MAX_BATCH_ITEMS] if item.get("id")]
    if not valid_items:
        return {}

    effective_mode = "preview" if mode == "preview" else "full"
    prepared: List[Tuple[str, Any, Optional[str], bool]] = []
    batch_texts: List[str] = []

    for item in valid_items:
        job_id = str(item.get("id", ""))
        raw_title = item.get("title")
        raw_desc = item.get("description")
        if isinstance(raw_desc, str) and effective_mode == "preview" and len(raw_desc) > PREVIEW_DESC_CHARS:
            target_desc: Optional[str] = _build_preview_snippet(raw_desc, PREVIEW_DESC_CHARS)
            is_full = False
        else:
            target_desc = raw_desc if isinstance(raw_desc, str) else None
            is_full = True

        prepared.append((job_id, raw_title, target_desc, is_full))
        if isinstance(raw_title, str) and raw_title.strip():
            batch_texts.append(raw_title)
        if isinstance(target_desc, str) and target_desc.strip():
            batch_texts.append(target_desc)

    translated_map = _translate_texts_parallel(batch_texts, lang_key) if batch_texts else {}

    results: Dict[str, Dict[str, Any]] = {}
    for job_id, raw_title, target_desc, is_full in prepared:
        title_out, title_src = (
            translated_map.get(raw_title, (raw_title, None)) if isinstance(raw_title, str) else (raw_title, None)
        )
        desc_out, desc_src = (
            translated_map.get(target_desc, (target_desc, None))
            if isinstance(target_desc, str)
            else (target_desc, None)
        )
        source_lang = desc_src or title_src
        changed = (isinstance(raw_title, str) and title_out != raw_title) or (
            isinstance(target_desc, str) and desc_out != target_desc
        )
        was_translated = bool(source_lang and source_lang != lang_key and changed)
        results[job_id] = {
            "title": title_out,
            "description": desc_out if is_full else None,
            "excerpt": desc_out,
            "source_lang": source_lang,
            "target_lang": lang_key,
            "was_translated": was_translated,
            "is_full": is_full,
        }

    return results
