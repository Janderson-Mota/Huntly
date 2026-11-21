from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import queue
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

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
}

SUPPORTED_LANGS = set(TARGET_LANG_MAP.keys())

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
MAX_CACHE_ENTRIES = 2000
MAX_CHUNK_CHARS = 4500
PREVIEW_DESC_CHARS = 450
MAX_BATCH_ITEMS = 20
TRANSLATE_WORKERS = 8

_ORIGINAL_REQUESTS_POST = requests.post
_session_pool: "queue.LifoQueue[requests.Session]" = queue.LifoQueue(maxsize=16)

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

_cache: "OrderedDict[Tuple[str, str], Tuple[str, Optional[str]]]" = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Clear the in-memory translation LRU cache."""
    with _cache_lock:
        _cache.clear()


def cache_size() -> int:
    """Return the number of entries currently stored in the translation cache."""
    with _cache_lock:
        return len(_cache)


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
    adapter = HTTPAdapter(pool_connections=1, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


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

    try:
        sess = _session_pool.get_nowait()
    except queue.Empty:
        sess = _build_pooled_session()

    try:
        return sess.post(TRANSLATE_URL, **request_kwargs)
    finally:
        try:
            _session_pool.put_nowait(sess)
        except queue.Full:
            sess.close()


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

    if target_lang == "zh":
        non_punct = [ch for ch in text if ch.isalnum()]
        cjk_chars = [ch for ch in non_punct if "\u4e00" <= ch <= "\u9fff"]
        return (
            len(cjk_chars) >= 20
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


def _request_chunk_translation(chunk: str, tl: str, timeout: int) -> Tuple[str, Optional[str]]:
    res = _post_translation(chunk, tl, timeout)
    res.raise_for_status()
    payload = res.json()
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise ValueError("Unexpected translation payload structure")
    translated = "".join(part[0] for part in payload[0] if isinstance(part, list) and part and part[0])
    if not translated:
        raise ValueError("Empty translation returned")
    detected_src = _normalize_lang_code(payload[2]) if len(payload) > 2 else None
    return translated, detected_src


def _translate_texts_parallel(
    texts: List[str], lang_key: str, timeout: int = 8
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Translate unique non-empty strings using cache, fast-path and flat parallel chunks."""
    tl = TARGET_LANG_MAP[lang_key]
    resolved: Dict[str, Tuple[str, Optional[str]]] = {}
    pending_chunks_by_text: Dict[str, List[str]] = {}
    unique_chunks: List[str] = []
    seen_chunks: Set[str] = set()

    for raw in texts:
        if (
            not isinstance(raw, str)
            or not raw
            or not raw.strip()
            or raw in resolved
            or raw in pending_chunks_by_text
        ):
            continue

        cached = _cache_get(tl, raw)
        if cached is not None:
            resolved[raw] = cached
            continue

        if _is_already_target_language(raw, lang_key):
            _cache_put(tl, raw, raw, lang_key)
            resolved[raw] = (raw, lang_key)
            continue

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
            resolved[raw] = (translated, source_lang)

    return resolved


def translate_text_with_meta(
    text: Optional[str], target_lang: str, timeout: int = 8
) -> Tuple[Optional[str], Optional[str]]:
    """Translate text into target_lang returning (translated_text, detected_source_lang)."""
    if not text or not text.strip():
        return text, None

    lang_key = _normalize_lang_code(target_lang)
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
