from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests


TARGET_LANG_MAP: Dict[str, str] = {
    "en": "en",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "de": "de",
    "ru": "ru",
    "zh": "zh-CN",
}

SUPPORTED_LANGS = {"pt", *TARGET_LANG_MAP.keys()}

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
MAX_CACHE_ENTRIES = 2000
MAX_CHUNK_CHARS = 1800
MAX_BATCH_ITEMS = 20
TRANSLATE_WORKERS = 4

_cache: "OrderedDict[Tuple[str, str], str]" = OrderedDict()
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


def _cache_get(tl: str, text: str) -> Optional[str]:
    key = _make_cache_key(tl, text)
    with _cache_lock:
        val = _cache.get(key)
        if val is not None:
            _cache.move_to_end(key)
        return val


def _cache_put(tl: str, text: str, translated: str) -> None:
    key = _make_cache_key(tl, text)
    with _cache_lock:
        _cache[key] = translated
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


def _request_chunk_translation(chunk: str, tl: str, timeout: int) -> str:
    res = requests.post(
        TRANSLATE_URL,
        params={"client": "gtx", "sl": "auto", "tl": tl, "dt": "t"},
        data={"q": chunk},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    res.raise_for_status()
    payload = res.json()
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise ValueError("Unexpected translation payload structure")
    translated = "".join(part[0] for part in payload[0] if isinstance(part, list) and part and part[0])
    if not translated:
        raise ValueError("Empty translation returned")
    return translated


def translate_text(text: Optional[str], target_lang: str, timeout: int = 8) -> Optional[str]:
    """Translate text into target_lang using an LRU cache, falling back to original text on any failure."""
    if not text or not text.strip():
        return text

    lang_key = (target_lang or "").strip().lower().split("-")[0]
    if lang_key == "pt" or lang_key not in TARGET_LANG_MAP:
        return text

    tl = TARGET_LANG_MAP[lang_key]
    cached = _cache_get(tl, text)
    if cached is not None:
        return cached

    try:
        chunks = _split_chunks(text, MAX_CHUNK_CHARS)
        translated_chunks = [_request_chunk_translation(chunk, tl, timeout) for chunk in chunks]
        translated = translated_chunks[0] if len(translated_chunks) == 1 else "\n\n".join(translated_chunks)
        _cache_put(tl, text, translated)
        return translated
    except Exception:
        return text


def _translate_single_job(item: Dict[str, Any], target_lang: str) -> Tuple[str, Dict[str, Optional[str]]]:
    job_id = str(item.get("id", ""))
    raw_title = item.get("title")
    raw_desc = item.get("description")
    return job_id, {
        "title": translate_text(raw_title, target_lang) if isinstance(raw_title, str) else raw_title,
        "description": translate_text(raw_desc, target_lang) if isinstance(raw_desc, str) else raw_desc,
    }


def translate_jobs_batch(items: List[Dict[str, Any]], target_lang: str) -> Dict[str, Dict[str, Optional[str]]]:
    """Translate titles and descriptions for up to MAX_BATCH_ITEMS jobs in parallel."""
    lang_key = (target_lang or "").strip().lower().split("-")[0]
    if lang_key == "pt" or lang_key not in TARGET_LANG_MAP:
        return {}

    valid_items = [item for item in items[:MAX_BATCH_ITEMS] if item.get("id")]
    if not valid_items:
        return {}

    results: Dict[str, Dict[str, Optional[str]]] = {}
    with ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS) as executor:
        for job_id, payload in executor.map(lambda it: _translate_single_job(it, lang_key), valid_items):
            results[job_id] = payload
    return results
