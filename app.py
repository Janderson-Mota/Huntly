import csv
from datetime import datetime
import io
import json
import os
import threading
from typing import Any, Dict, List

from flask import Flask, Response, jsonify, render_template, request

from scraper import jobs_state, search_jobs_thread

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


def _parse_limit(raw_value: Any, default: int = 100, max_limit: int = 500) -> int:
    if raw_value is None or raw_value == "":
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Limite deve ser um número inteiro válido.") from exc
    return max(1, min(value, max_limit))


def _validate_search_type(search_type: str):
    if search_type != "jobs":
        return jsonify({"error": "Tipo de busca inválido."}), 400
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def start_search():
    try:
        params = request.get_json(silent=True) or {}
        err = _validate_search_type(params.get("type", "jobs"))
        if err:
            return err

        if jobs_state.is_searching:
            return jsonify({"error": "Uma busca de vagas já está em andamento."}), 400

        limit_jobs = _parse_limit(params.get("limit_jobs"), default=100)
        args = (
            params.get("keywords", ""),
            params.get("location", ""),
            params.get("max_date", ""),
            params.get("distance", ""),
            params.get("job_type", []),
            params.get("place", []),
            limit_jobs,
            params.get("experience_level", []),
            params.get("sort_by", ""),
            bool(params.get("easy_apply", False)),
        )

        search_thread = threading.Thread(target=search_jobs_thread, args=args, daemon=True)
        search_thread.start()
        return jsonify({"message": "Busca de vagas iniciada."}), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Erro interno: {exc}"}), 500


@app.route("/stop", methods=["POST"])
def stop_search():
    params = request.get_json(silent=True) or {}
    search_type = params.get("type", "jobs")
    err = _validate_search_type(search_type)
    if err:
        return err
    jobs_state.stop()
    return jsonify({"message": "Busca de vagas interrompida."}), 200


@app.route("/status")
def get_search_status():
    err = _validate_search_type(request.args.get("type", "jobs"))
    if err:
        return err
    return jsonify(jobs_state.snapshot())


@app.route("/results")
def get_search_results():
    err = _validate_search_type(request.args.get("type", "jobs"))
    if err:
        return err
    return jsonify(jobs_state.get_results())


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
    err = _validate_search_type(search_type)
    if err:
        return None, None, err

    results = [item for item in jobs_state.get_results() if not item.get("error")]
    if not results:
        return None, None, (jsonify({"error": "Nenhum resultado disponível para exportação."}), 400)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return results, f"vagas_linkedin_{timestamp}", None


@app.route("/export/csv")
def export_to_csv():
    results, base_filename, err_response = _get_export_results(request.args.get("type", "jobs"))
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
    results, base_filename, err_response = _get_export_results(request.args.get("type", "jobs"))
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
