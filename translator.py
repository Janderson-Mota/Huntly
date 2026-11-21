from collections import OrderedDict
from contextlib import closing
import hashlib
import os
import re
import sqlite3
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata


TARGET_LANG_MAP: Dict[str, str] = {
    "pt": "pt",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "de": "de",
    "ru": "ru",
    "zh": "zh",
    "ja": "ja",
}

SUPPORTED_LANGS = set(TARGET_LANG_MAP.keys())

MAX_CACHE_ENTRIES = 5000
MAX_CHUNK_CHARS = 4500
PREVIEW_DESC_CHARS = 450
MAX_BATCH_ITEMS = 50
_DEFAULT_CACHE_DB = os.path.join(tempfile.gettempdir(), "huntly_translation_cache.sqlite3")

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
        "gerente", "coordenador", "diretor", "arquiteto", "dados", "sistemas",
        "requisitos", "responsabilidades", "beneficios", "remoto", "hibrido",
        "presencial", "empresa", "candidatos", "salario", "experiencia", "vagas",
    },
    "en": {
        "developer", "engineer", "engineering", "software", "intern", "internship",
        "lead", "manager", "architect", "architecture", "analyst", "principal",
        "staff", "remote", "hybrid", "onsite", "scalable", "building", "designing",
        "service", "services", "team", "seeking", "hiring", "role", "position",
        "experience", "requirements", "responsibilities", "benefits", "skills",
    },
    "es": {
        "desarrollador", "desarrolladora", "ingeniero", "ingeniera", "practicas",
        "becario", "puesto", "requisitos", "funciones", "beneficios", "sueldo",
        "remoto", "hibrido", "presencial", "datos",
    },
    "fr": {
        "developpeur", "developpeuse", "ingenieur", "stage", "stagiaire", "poste",
        "missions", "competences", "profil", "avantages", "teletravail",
        "hybride", "donnees", "recherche",
    },
    "it": {
        "sviluppatore", "ingegnere", "tirocinio", "stage", "azienda", "requisiti",
        "competenze", "ruolo", "remoto", "ibrido", "dati",
    },
    "de": {
        "entwickler", "entwicklerin", "ingenieur", "praktikum", "werkstudent",
        "stelle", "aufgaben", "profil", "vorteile", "erfahrung", "kenntnisse", "daten",
    },
}

_cache: "OrderedDict[Tuple[str, str], Tuple[str, Optional[str]]]" = OrderedDict()
_cache_lock = threading.Lock()
_db_lock = threading.Lock()
_configured_db_path: Optional[str] = None
_initialized_dbs: Set[str] = set()

_argos_lock = threading.Lock()
_argos_languages_by_code: Optional[Dict[str, Any]] = None
_argos_translators: Dict[Tuple[str, str], Any] = {}


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


_LATIN_STOPWORDS_NORM: Dict[str, Set[str]] = {
    lang: {_strip_accents(s) for s in sw_set}
    for lang, sw_set in _LATIN_STOPWORDS.items()
}


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
            with closing(sqlite3.connect(db_path, timeout=5.0)) as conn, conn:
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
            with closing(sqlite3.connect(db_path, timeout=5.0)) as conn, conn:
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


def reset_argos_cache() -> None:
    """Clear cached Argos Translate language index and translator instances."""
    global _argos_languages_by_code
    with _argos_lock:
        _argos_languages_by_code = None
        _argos_translators.clear()


def clear_memory_cache() -> None:
    """Clear only the in-memory LRU cache without deleting the persistent SQLite cache."""
    with _cache_lock:
        _cache.clear()


def clear_cache() -> None:
    """Clear the in-memory, SQLite, and Argos model caches."""
    clear_memory_cache()
    reset_argos_cache()
    db_path = _active_db_path()
    if db_path and os.path.exists(db_path):
        with _db_lock:
            try:
                with closing(sqlite3.connect(db_path, timeout=5.0)) as conn, conn:
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


def _is_already_target_language(text: str, target_lang: str) -> bool:
    """Conservatively skip translation only for long texts clearly already in target_lang."""
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


def _score_latin_languages(text: str) -> Dict[str, int]:
    """Score Latin-script languages using diacritics, stopwords, and IT role terms."""
    lower = text.lower()
    scores: Dict[str, int] = {lang: 0 for lang in _LANG_JOB_KEYWORDS}
    if any(ch in lower for ch in "ãõçêâô"):
        scores["pt"] += 3
    if "ñ" in lower or "¿" in lower or "¡" in lower:
        scores["es"] += 3
    if "ß" in lower or "ä" in lower or "ö" in lower or "ü" in lower:
        scores["de"] += 2
    if any(ch in lower for ch in "àèéìòù") and any(
        tok in lower for tok in ("svilupp", "lavoro", "azienda", "di ", "per ")
    ):
        scores["it"] += 2
    if any(ch in lower for ch in "éèêàçôù") and any(
        tok in lower for tok in ("développ", "ingénieur", "poste", "chez", "avec")
    ):
        scores["fr"] += 3

    norm_lower = _strip_accents(lower)
    words = re.findall(r"[a-z]+", norm_lower)
    for w in words:
        for lang_code, sw_set in _LATIN_STOPWORDS_NORM.items():
            if w in sw_set:
                scores[lang_code] += 2
        for lang_code, kw_set in _LANG_JOB_KEYWORDS.items():
            if w in kw_set:
                scores[lang_code] += 2
    return scores


def detect_source_language(
    text: Optional[str],
    target_lang: str = "en",
    strict: bool = False,
    hint: Optional[str] = None,
) -> Optional[str]:
    """Detect source ISO-639-1 language via script checks, diacritics, stopwords, and IT job terms."""
    if not text or not text.strip():
        return None if strict else (hint or ("en" if target_lang != "en" else "pt"))

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

    scores = _score_latin_languages(text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best_score = ranked[0]
    if best_score > 0:
        # Avoid falsely treating mixed bilingual descriptions as purely target_lang.
        if best_lang == target_lang and not strict:
            for alt_lang, alt_score in ranked[1:]:
                if alt_lang != target_lang and alt_score >= 6 and best_score < alt_score * 3:
                    return alt_lang
        return best_lang
    if strict:
        return hint if (hint and hint in TARGET_LANG_MAP) else None
    if hint and hint in TARGET_LANG_MAP:
        return hint
    return "en" if target_lang != "en" else "pt"


def _get_argos_translation(from_code: str, to_code: str) -> Optional[Any]:
    """Return a cached Argos Translate translator object (supporting automatic English pivot)."""
    global _argos_languages_by_code
    if not from_code or not to_code or from_code == to_code:
        return None
    pair = (from_code, to_code)
    with _argos_lock:
        if pair in _argos_translators:
            return _argos_translators[pair]

    try:
        import argostranslate.translate as argos_translate
    except ImportError:
        return None

    with _argos_lock:
        if pair in _argos_translators:
            return _argos_translators[pair]
        if _argos_languages_by_code is None:
            installed = argos_translate.get_installed_languages()
            _argos_languages_by_code = {lang.code: lang for lang in installed}
        lang_map = _argos_languages_by_code or {}
        from_lang = lang_map.get(from_code)
        to_lang = lang_map.get(to_code)
        if not from_lang or not to_lang:
            return None
        translation_obj = from_lang.get_translation(to_lang)
        if translation_obj is not None:
            _argos_translators[pair] = translation_obj
        return translation_obj


def _translate_single_text_offline(
    text: str, target_code: str, source_code: Optional[str] = None, hint: Optional[str] = None
) -> Tuple[str, Optional[str], bool]:
    """Translate text offline via Argos Translate. Returns (output_text, detected_src, ok)."""
    detected_src = source_code or detect_source_language(text, target_code, strict=False, hint=hint)
    if not detected_src:
        return text, None, False
    if detected_src == target_code:
        return text, target_code, True

    translator_obj = _get_argos_translation(detected_src, target_code)
    if translator_obj is None:
        return text, None, False

    chunks = _split_chunks(text, MAX_CHUNK_CHARS)
    translated_parts: List[str] = []
    for ch in chunks:
        out_chunk = translator_obj.translate(ch)
        if not isinstance(out_chunk, str) or not out_chunk.strip():
            return text, None, False
        translated_parts.append(out_chunk)

    joined = translated_parts[0] if len(translated_parts) == 1 else "\n\n".join(translated_parts)
    return joined, detected_src, True


def _translate_texts_with_argos(
    texts: List[str],
    lang_key: str,
    text_hints: Optional[Dict[str, Optional[str]]] = None,
    forced_source: Optional[str] = None,
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Translate unique non-empty strings using RAM + SQLite cache and local Argos models."""
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

    # Batch lookup in persistent SQLite cache before running neural translation
    if uncached_candidates:
        digest_to_raw = {_make_cache_key(tl, raw)[1]: raw for raw in uncached_candidates}
        sqlite_hits = _sqlite_batch_get(tl, list(digest_to_raw.keys()))
        remaining: List[str] = []
        for dig, raw in digest_to_raw.items():
            hit = sqlite_hits.get(dig)
            if hit is not None:
                _cache_put(tl, raw, hit[0], hit[1])
                resolved[raw] = hit
            else:
                remaining.append(raw)
        uncached_candidates = remaining

    for raw in uncached_candidates:
        hint = text_hints.get(raw) if text_hints else None
        try:
            translated, src_lang, ok = _translate_single_text_offline(
                raw, tl, source_code=forced_source, hint=hint
            )
        except Exception:
            translated, src_lang, ok = raw, None, False

        if not ok or src_lang is None:
            resolved[raw] = (raw, None)
            continue

        _cache_put(tl, raw, translated, src_lang)
        _, dig = _make_cache_key(tl, raw)
        sqlite_rows_to_save.append((tl, dig, translated, src_lang))
        resolved[raw] = (translated, src_lang)

    if sqlite_rows_to_save:
        _sqlite_batch_put(sqlite_rows_to_save)

    return resolved


def translate_text_with_meta(
    text: Optional[str],
    target_lang: str,
    source_lang: Optional[str] = None,
    timeout: int = 8,
) -> Tuple[Optional[str], Optional[str]]:
    """Translate text locally via Argos returning (translated_text, detected_source_lang)."""
    _ = timeout
    if not text or not text.strip():
        return text, None

    lang_key = normalize_target_lang(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return text, None

    src_key = normalize_target_lang(source_lang) if source_lang else None
    resolved = _translate_texts_with_argos([text], lang_key, forced_source=src_key)
    return resolved.get(text, (text, None))


def translate_text(
    text: Optional[str], target_lang: str, source_lang: Optional[str] = None, timeout: int = 8
) -> Optional[str]:
    """Translate text locally into target_lang using cache and safe original fallback."""
    translated, _ = translate_text_with_meta(
        text, target_lang, source_lang=source_lang, timeout=timeout
    )
    return translated


def _translate_single_job(item: Dict[str, Any], target_lang: str) -> Tuple[str, Dict[str, Any]]:
    job_id = str(item.get("id", ""))
    raw_title = item.get("title")
    raw_desc = item.get("description")
    lang_key = normalize_target_lang(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return job_id, {
            "title": raw_title,
            "description": raw_desc,
            "excerpt": raw_desc,
            "source_lang": None,
            "target_lang": target_lang,
            "was_translated": False,
            "is_full": True,
        }

    combined_sample = " ".join(
        t for t in (raw_title, raw_desc) if isinstance(t, str) and t.strip()
    )
    job_hint = detect_source_language(combined_sample, lang_key, strict=True)
    text_hints: Dict[str, Optional[str]] = {}
    texts: List[str] = []
    for t in (raw_title, raw_desc):
        if isinstance(t, str) and t.strip():
            texts.append(t)
            text_hints[t] = job_hint

    translated_map = _translate_texts_with_argos(texts, lang_key, text_hints=text_hints)

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
    was_translated = bool(source_lang and source_lang != lang_key and changed)
    return job_id, {
        "title": title_out,
        "description": desc_out,
        "excerpt": desc_out,
        "source_lang": source_lang,
        "target_lang": lang_key,
        "was_translated": was_translated,
        "is_full": True,
    }


def translate_jobs_batch(
    items: List[Dict[str, Any]], target_lang: str, mode: str = "full"
) -> Dict[str, Dict[str, Any]]:
    """Translate titles and descriptions (preview snippet or full) offline for up to MAX_BATCH_ITEMS jobs."""
    lang_key = normalize_target_lang(target_lang)
    if not lang_key or lang_key not in TARGET_LANG_MAP:
        return {}

    valid_items = [item for item in items[:MAX_BATCH_ITEMS] if item.get("id")]
    if not valid_items:
        return {}

    effective_mode = "preview" if mode == "preview" else "full"
    prepared: List[Tuple[str, Any, Optional[str], bool]] = []
    batch_texts: List[str] = []
    text_hints: Dict[str, Optional[str]] = {}

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

        combined_sample = " ".join(
            t for t in (raw_title, target_desc) if isinstance(t, str) and t.strip()
        )
        job_hint = detect_source_language(combined_sample, lang_key, strict=True)

        prepared.append((job_id, raw_title, target_desc, is_full))
        if isinstance(raw_title, str) and raw_title.strip():
            batch_texts.append(raw_title)
            if raw_title not in text_hints and job_hint:
                text_hints[raw_title] = job_hint
        if isinstance(target_desc, str) and target_desc.strip():
            batch_texts.append(target_desc)
            if target_desc not in text_hints and job_hint:
                text_hints[target_desc] = job_hint

    translated_map = (
        _translate_texts_with_argos(batch_texts, lang_key, text_hints=text_hints)
        if batch_texts
        else {}
    )

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
