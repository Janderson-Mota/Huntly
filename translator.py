from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests


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
MAX_CHUNK_CHARS = 1800
MAX_BATCH_ITEMS = 20
TRANSLATE_WORKERS = 4

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


def _request_chunk_translation(chunk: str, tl: str, timeout: int) -> Tuple[str, Optional[str]]:
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
    detected_src = _normalize_lang_code(payload[2]) if len(payload) > 2 else None
    return translated, detected_src


def translate_text_with_meta(
    text: Optional[str], target_lang: str, timeout: int = 8
) -> Tuple[Optional[str], Optional[str]]:
    """Translate text into target_lang returning (translated_text, detected_source_lang)."""
    if not text or not text.strip():
        return text, None

    lang_key = _normalize_lang_code(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return text, None

    tl = TARGET_LANG_MAP[lang_key]
    cached = _cache_get(tl, text)
    if cached is not None:
        return cached

    try:
        chunks = _split_chunks(text, MAX_CHUNK_CHARS)
        translated_chunks: List[str] = []
        source_lang: Optional[str] = None
        for chunk in chunks:
            part_translated, part_src = _request_chunk_translation(chunk, tl, timeout)
            translated_chunks.append(part_translated)
            if source_lang is None and part_src:
                source_lang = part_src
        translated = translated_chunks[0] if len(translated_chunks) == 1 else "\n\n".join(translated_chunks)
        _cache_put(tl, text, translated, source_lang)
        return translated, source_lang
    except Exception:
        return text, None


def translate_text(text: Optional[str], target_lang: str, timeout: int = 8) -> Optional[str]:
    """Translate text into target_lang using an LRU cache, falling back to original text on any failure."""
    translated, _ = translate_text_with_meta(text, target_lang, timeout=timeout)
    return translated


def _translate_single_job(item: Dict[str, Any], target_lang: str) -> Tuple[str, Dict[str, Any]]:
    job_id = str(item.get("id", ""))
    raw_title = item.get("title")
    raw_desc = item.get("description")

    title_out, title_src = (
        translate_text_with_meta(raw_title, target_lang) if isinstance(raw_title, str) else (raw_title, None)
    )
    desc_out, desc_src = (
        translate_text_with_meta(raw_desc, target_lang) if isinstance(raw_desc, str) else (raw_desc, None)
    )
    source_lang = desc_src or title_src
    changed = (isinstance(raw_title, str) and title_out != raw_title) or (
        isinstance(raw_desc, str) and desc_out != raw_desc
    )
    was_translated = bool(source_lang and source_lang != target_lang and changed)
    return job_id, {
        "title": title_out,
        "description": desc_out,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "was_translated": was_translated,
    }


def translate_jobs_batch(items: List[Dict[str, Any]], target_lang: str) -> Dict[str, Dict[str, Any]]:
    """Translate titles and descriptions for up to MAX_BATCH_ITEMS jobs in parallel."""
    lang_key = _normalize_lang_code(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return {}

    valid_items = [item for item in items[:MAX_BATCH_ITEMS] if item.get("id")]
    if not valid_items:
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS) as executor:
        for job_id, payload in executor.map(lambda it: _translate_single_job(it, lang_key), valid_items):
            results[job_id] = payload
    return results
