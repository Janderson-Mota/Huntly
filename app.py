import csv
from datetime import datetime
import io
import json
import os
import threading
from typing import Any, Dict, List
import unicodedata

from flask import Flask, Response, jsonify, render_template, request

from scraper import jobs_state, search_jobs_thread
from translator import SUPPORTED_LANGS, translate_jobs_batch

app = Flask(__name__)
_debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
app.config["TEMPLATES_AUTO_RELOAD"] = _debug_mode
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0 if _debug_mode else 3600

DEFAULT_LIMIT_JOBS = 25
UNLIMITED_JOBS_CAP = 250
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_EXPORT_PREFIXES = {
    "pt": "vagas_linkedin",
    "en": "linkedin_jobs",
    "es": "empleos_linkedin",
    "fr": "offres_linkedin",
    "it": "offerte_linkedin",
    "de": "linkedin_jobs",
    "ru": "linkedin_jobs",
    "zh": "linkedin_jobs",
}


class _ValidationError(ValueError):
    """Validation error carrying a stable i18n error code."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def _parse_limit(raw_value: Any, default: int = DEFAULT_LIMIT_JOBS, max_limit: int = UNLIMITED_JOBS_CAP) -> int:
    if raw_value is None or raw_value == "":
        return default
    if isinstance(raw_value, bool):
        raise _ValidationError("Limite deve ser um número inteiro válido.", "errInvalidLimit")
    if isinstance(raw_value, str) and raw_value.strip().lower() in ("unlimited", "all", "sem_restricao"):
        return UNLIMITED_JOBS_CAP
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _ValidationError("Limite deve ser um número inteiro válido.", "errInvalidLimit") from exc
    if value == 0:
        return UNLIMITED_JOBS_CAP
    return max(1, min(value, max_limit))


def _parse_str(raw_value: Any, max_len: int = 200) -> str:
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise _ValidationError("Parâmetro textual inválido.", "errInvalidTextParam")
    return raw_value.strip()[:max_len]


def _parse_str_list(raw_value: Any) -> List[str]:
    if raw_value is None or raw_value == "":
        return []
    if not isinstance(raw_value, list):
        raise _ValidationError("Filtro deve ser uma lista.", "errInvalidFilterList")
    return [str(item).strip() for item in raw_value if item is not None and str(item).strip()]


def _parse_multi_filter(raw_value: Any) -> List[str]:
    """Parse list or comma-separated string filter while preserving compound tokens like '3,4'."""
    if raw_value is None or raw_value == "":
        return []
    values: List[str] = []
    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if not trimmed:
            return []
        if trimmed in ("3,4", "5,6"):
            values = [trimmed]
        else:
            values = [part.strip() for part in trimmed.split(",") if part.strip()]
    elif isinstance(raw_value, list):
        for item in raw_value:
            if item is None:
                continue
            if isinstance(item, (dict, list, bool)):
                raise _ValidationError("Filtro deve ser uma lista.", "errInvalidFilterList")
            cleaned = str(item).strip()
            if cleaned:
                values.append(cleaned)
    else:
        raise _ValidationError("Filtro deve ser uma lista.", "errInvalidFilterList")

    seen: set[str] = set()
    deduped: List[str] = []
    for val in values:
        if val not in seen:
            seen.add(val)
            deduped.append(val)
    return deduped


def _parse_bool(raw_value: Any, default: bool = False) -> bool:
    if raw_value is None or raw_value == "":
        return default
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return bool(raw_value)
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
    return bool(raw_value)


def _validate_search_type(search_type: Any):
    if search_type != "jobs":
        return jsonify({"error": "Tipo de busca inválido.", "error_code": "errInvalidSearchType"}), 400
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def start_search():
    try:
        params = request.get_json(silent=True)
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return jsonify({"error": "Payload JSON deve ser um objeto.", "error_code": "errInvalidPayload"}), 400

        err = _validate_search_type(params.get("type", "jobs"))
        if err:
            return err

        keywords = _parse_str(params.get("keywords"), max_len=200)
        location = _parse_str(params.get("location"), max_len=200)
        max_date = _parse_str(params.get("max_date"), max_len=30)
        distance = _parse_str(params.get("distance"), max_len=10)
        sort_by = _parse_str(params.get("sort_by"), max_len=10).upper()
        job_type = _parse_str_list(params.get("job_type"))
        raw_work_mode = params.get("work_mode") if "work_mode" in params else params.get("place")
        place = _parse_multi_filter(raw_work_mode)
        experience_level = _parse_multi_filter(params.get("experience_level"))
        easy_apply = _parse_bool(params.get("easy_apply"), default=False)
        limit_jobs = _parse_limit(params.get("limit_jobs"), default=DEFAULT_LIMIT_JOBS)
        lang = _parse_str(params.get("lang"), max_len=10).lower() or "en"

        has_filter_select = bool(
            location
            or max_date
            or place
            or experience_level
            or job_type
            or easy_apply
        )
        if not keywords and not has_filter_select:
            return jsonify({
                "error": "Informe um cargo/palavra-chave ou selecione ao menos um filtro (país, data, nível de experiência ou modalidade).",
                "error_code": "errNoKeyword",
            }), 400

        if not jobs_state.start():
            return jsonify({"error": "Uma busca de vagas já está em andamento.", "error_code": "errAlreadyRunning"}), 400

        run_id = jobs_state.run_id
        args = (
            keywords,
            location,
            max_date,
            distance,
            job_type,
            place,
            limit_jobs,
            experience_level,
            sort_by,
            easy_apply,
            True,
        )

        try:
            search_thread = threading.Thread(
                target=search_jobs_thread,
                args=args,
                kwargs={"run_id": run_id, "lang": lang},
                daemon=True,
            )
            search_thread.start()
        except Exception:
            jobs_state.stop(run_id=run_id)
            raise

        return jsonify({"message": "Busca de vagas iniciada.", "message_code": "msgSearchStarted"}), 200

    except _ValidationError as exc:
        return jsonify({"error": str(exc), "error_code": exc.code}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc), "error_code": "errInvalidPayload"}), 400
    except Exception:
        return jsonify({"error": "Erro interno ao iniciar a busca.", "error_code": "errInternalStart"}), 500


@app.route("/stop", methods=["POST"])
def stop_search():
    params = request.get_json(silent=True)
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return jsonify({"error": "Payload JSON deve ser um objeto.", "error_code": "errInvalidPayload"}), 400

    search_type = params.get("type", "jobs")
    err = _validate_search_type(search_type)
    if err:
        return err
    jobs_state.stop()
    return jsonify({"message": "Busca de vagas interrompida.", "message_code": "msgSearchStopped"}), 200


@app.route("/status")
def get_search_status():
    err = _validate_search_type(request.args.get("type", "jobs"))
    if err:
        return err
    include_results = request.args.get("include_results", "1").lower() not in ("0", "false", "no")
    return jsonify(jobs_state.snapshot(include_results=include_results))


def _normalize_search_text(text: Any) -> str:
    decomposed = unicodedata.normalize("NFD", str(text or ""))
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.lower().strip()


def _filter_results_by_tab(
    items: List[Dict[str, Any]],
    tab: str = "all",
    q: str = "",
    exclude: str = "",
) -> List[Dict[str, Any]]:
    filtered = [item for item in items if not item.get("error")]
    normalized_tab = (tab or "all").strip().lower()
    if normalized_tab == "matched":
        filtered = [item for item in filtered if item.get("match_category", "matched") != "recommended"]
    elif normalized_tab == "recommended":
        filtered = [item for item in filtered if item.get("match_category") == "recommended"]

    quick_term = _normalize_search_text(q)
    if quick_term:
        filtered = [
            item
            for item in filtered
            if quick_term
            in _normalize_search_text(
                " ".join(
                    str(item.get(field) or "")
                    for field in ("title", "company", "location", "description")
                )
            )
        ]

    exclude_terms = [
        _normalize_search_text(part)
        for part in str(exclude or "").split(",")
        if _normalize_search_text(part)
    ]
    if exclude_terms:
        filtered = [
            item
            for item in filtered
            if not any(
                term
                in _normalize_search_text(
                    " ".join(str(item.get(field) or "") for field in ("title", "description"))
                )
                for term in exclude_terms
            )
        ]

    return filtered


@app.route("/results")
def get_search_results():
    err = _validate_search_type(request.args.get("type", "jobs"))
    if err:
        return err
    results = jobs_state.get_results()
    tab = request.args.get("tab", "all")
    q = request.args.get("q", "")
    exclude = request.args.get("exclude", "")
    if tab and tab.strip().lower() != "all" or q or exclude:
        return jsonify(_filter_results_by_tab(results, tab=tab, q=q, exclude=exclude))
    return jsonify(results)


@app.route("/job/<job_id>")
def get_job_details(job_id: str):
    job = next((item for item in jobs_state.get_results() if item.get("id") == job_id), None)
    if job:
        return jsonify(job)
    return jsonify({"error": "Vaga não encontrada.", "error_code": "errJobNotFound"}), 404


@app.route("/translate", methods=["POST"])
def translate_job_cards():
    try:
        params = request.get_json(silent=True)
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return jsonify({"error": "Payload JSON deve ser um objeto.", "error_code": "errInvalidPayload"}), 400

        lang = _parse_str(params.get("lang"), max_len=10).lower()
        if lang not in SUPPORTED_LANGS:
            return jsonify({"error": "Idioma não suportado.", "error_code": "errInvalidLanguage"}), 400

        raw_mode = _parse_str(params.get("mode"), max_len=16).lower() or "full"
        if raw_mode not in ("full", "preview"):
            raise _ValidationError("Modo de tradução inválido.", "errInvalidPayload")

        job_ids = _parse_str_list(params.get("job_ids"))[:20]
        target_items: List[Dict[str, Any]] = []
        if job_ids:
            jobs_by_id = {
                str(item.get("id")): item
                for item in jobs_state.get_results()
                if item.get("id") and not item.get("error")
            }
            for jid in job_ids:
                if jid in jobs_by_id:
                    target_items.append(jobs_by_id[jid])
        elif "items" in params:
            raw_items = params.get("items")
            if not isinstance(raw_items, list):
                raise _ValidationError("Lista de vagas inválida.", "errInvalidPayload")
            for raw in raw_items[:20]:
                if not isinstance(raw, dict):
                    continue
                jid = _parse_str(raw.get("id"), max_len=64)
                if not jid:
                    continue
                title = _parse_str(raw.get("title"), max_len=500) if raw.get("title") is not None else None
                desc = _parse_str(raw.get("description"), max_len=15000) if raw.get("description") is not None else None
                target_items.append({"id": jid, "title": title, "description": desc})

        translations = translate_jobs_batch(target_items, lang, mode=raw_mode)
        return jsonify({"lang": lang, "mode": raw_mode, "translations": translations}), 200

    except _ValidationError as exc:
        return jsonify({"error": str(exc), "error_code": exc.code}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc), "error_code": "errInvalidPayload"}), 400
    except Exception:
        return jsonify({"error": "Erro ao traduzir vagas.", "error_code": "errGeneric"}), 500


def _sanitize_csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formula injection (CWE-1236)."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def generate_csv(items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""

    output = io.StringIO()
    fieldnames = sorted({key for item in items for key in item.keys()} - {"error"})
    preferred_fields = ["id", "title", "company", "location", "time", "link", "description"]

    for field in reversed(preferred_fields):
        if field in fieldnames:
            fieldnames.remove(field)
            fieldnames.insert(0, field)

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        if not item.get("error"):
            sanitized = {k: _sanitize_csv_cell(v) for k, v in item.items()}
            writer.writerow(sanitized)

    return output.getvalue()


def _get_export_results(
    search_type: str,
    lang: str = "",
    tab: str = "all",
    q: str = "",
    exclude: str = "",
):
    err = _validate_search_type(search_type)
    if err:
        return None, None, err

    results = _filter_results_by_tab(
        jobs_state.get_results(),
        tab=tab,
        q=q,
        exclude=exclude,
    )
    if not results:
        return None, None, (
            jsonify({"error": "Nenhum resultado disponível para exportação.", "error_code": "errNoExportResults"}),
            400,
        )

    prefix = _EXPORT_PREFIXES.get(lang.strip().lower(), "vagas_linkedin")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return results, f"{prefix}_{timestamp}", None


@app.route("/export/csv")
def export_to_csv():
    results, base_filename, err_response = _get_export_results(
        request.args.get("type", "jobs"),
        lang=request.args.get("lang", ""),
        tab=request.args.get("tab", "all"),
        q=request.args.get("q", ""),
        exclude=request.args.get("exclude", ""),
    )
    if err_response:
        return err_response

    csv_content = "\ufeff" + generate_csv(results)
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={base_filename}.csv"},
    )


@app.route("/export/json")
def export_to_json():
    results, base_filename, err_response = _get_export_results(
        request.args.get("type", "jobs"),
        lang=request.args.get("lang", ""),
        tab=request.args.get("tab", "all"),
        q=request.args.get("q", ""),
        exclude=request.args.get("exclude", ""),
    )
    if err_response:
        return err_response

    return Response(
        json.dumps(results, ensure_ascii=False, indent=2),
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={base_filename}.json"},
    )


if __name__ == "__main__":
    app.run(debug=_debug_mode)
