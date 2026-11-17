import csv
from datetime import datetime
import io
import json
import os
import threading
from typing import Any, Dict, List

from flask import Flask, Response, jsonify, render_template, request

from people_scraper import people_state, search_people_thread
from publications_scraper import publications_state, search_publications_thread
from scraper import jobs_state, search_jobs_thread
from state import SearchState

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

STATE_BY_TYPE: Dict[str, SearchState] = {
    "jobs": jobs_state,
    "publications": publications_state,
    "people": people_state,
}

EXPORT_PREFIX_BY_TYPE: Dict[str, str] = {
    "jobs": "vagas_linkedin",
    "publications": "publicacoes_linkedin",
    "people": "pessoas_linkedin",
}


def _parse_limit(raw_value: Any, default: int, max_limit: int = 500) -> int:
    if raw_value is None or raw_value == "":
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Limite deve ser um número inteiro válido.") from exc
    return max(1, min(value, max_limit))


def _get_state_or_400(search_type: str):
    state = STATE_BY_TYPE.get(search_type)
    if state is None:
        return None, (jsonify({"error": "Tipo de busca inválido."}), 400)
    return state, None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def start_search():
    try:
        params = request.get_json(silent=True) or {}
        search_type = params.get("type", "jobs")
        state, err_response = _get_state_or_400(search_type)
        if err_response:
            return err_response

        if state.is_searching:
            return jsonify({"error": f"Uma busca de '{search_type}' já está em andamento."}), 400

        if search_type == "jobs":
            limit_jobs = _parse_limit(params.get("limit_jobs"), default=100)
            target = search_jobs_thread
            args = (
                params.get("keywords", ""),
                params.get("location", ""),
                params.get("max_date", "r7d"),
                params.get("distance", ""),
                params.get("job_type", []),
                params.get("place", []),
                limit_jobs,
                params.get("experience_level", []),
                params.get("sort_by", "DD"),
                bool(params.get("easy_apply", False)),
            )
        elif search_type == "publications":
            limit_publications = _parse_limit(params.get("limit_publications"), default=50)
            target = search_publications_thread
            args = (
                params.get("keywords", ""),
                params.get("max_date", "past-week"),
                limit_publications,
            )
        else:
            limit_people = _parse_limit(params.get("limit_people"), default=50)
            target = search_people_thread
            args = (
                params.get("keywords", ""),
                params.get("location", ""),
                bool(params.get("hiring_only", False)),
                params.get("hiring_keywords", []),
                limit_people,
            )

        search_thread = threading.Thread(target=target, args=args, daemon=True)
        search_thread.start()
        return jsonify({"message": f"Busca de '{search_type}' iniciada."}), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Erro interno: {exc}"}), 500


@app.route("/stop", methods=["POST"])
def stop_search():
    params = request.get_json(silent=True) or {}
    search_type = params.get("type")

    if search_type:
        state, err_response = _get_state_or_400(search_type)
        if err_response:
            return err_response
        state.stop()
        return jsonify({"message": f"Busca de '{search_type}' interrompida."}), 200

    for state in STATE_BY_TYPE.values():
        state.stop()
    return jsonify({"message": "Todas as buscas foram interrompidas."}), 200


@app.route("/status")
def get_search_status():
    search_type = request.args.get("type", "jobs")
    state, err_response = _get_state_or_400(search_type)
    if err_response:
        return err_response
    return jsonify(state.snapshot())


@app.route("/results")
def get_search_results():
    search_type = request.args.get("type", "jobs")
    state, err_response = _get_state_or_400(search_type)
    if err_response:
        return err_response
    return jsonify(state.get_results())


@app.route("/job/<job_id>")
def get_job_details(job_id: str):
    job = next((item for item in jobs_state.get_results() if item.get("id") == job_id), None)
    if job:
        return jsonify(job)
    return jsonify({"error": "Vaga não encontrada."}), 404


def generate_csv(items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""

    output = io.StringIO()
    is_publication = any("author" in item for item in items)
    is_person = any(item.get("type") == "person" for item in items)

    if is_publication:
        fieldnames = ["title", "author", "content", "time", "link", "type"]
        preferred_fields = ["title", "author", "content", "time", "link"]
    elif is_person:
        fieldnames = ["name", "headline", "location", "link", "type"]
        preferred_fields = ["name", "headline", "location", "link"]
    else:
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
            writer.writerow(item)

    return output.getvalue()


def _get_export_results(search_type: str):
    state, err_response = _get_state_or_400(search_type)
    if err_response:
        return None, None, err_response

    results = [item for item in state.get_results() if not item.get("error")]
    if not results:
        return None, None, (jsonify({"error": "Nenhum resultado disponível para exportação."}), 400)

    prefix = EXPORT_PREFIX_BY_TYPE[search_type]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return results, f"{prefix}_{timestamp}", None


@app.route("/export/csv")
def export_to_csv():
    search_type = request.args.get("type", "jobs")
    results, base_filename, err_response = _get_export_results(search_type)
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
    search_type = request.args.get("type", "jobs")
    results, base_filename, err_response = _get_export_results(search_type)
    if err_response:
        return err_response

    return Response(
        json.dumps(results, ensure_ascii=False, indent=2),
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={base_filename}.json"},
    )


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
