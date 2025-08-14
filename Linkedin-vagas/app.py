from flask import Flask, render_template, request, jsonify, Response
import threading
import io
import csv
import json
from datetime import datetime
from scraper import search_jobs_thread, search_status
from publications_scraper import search_publications_thread, publications_status
from people_scraper import search_people_thread, people_status

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def start_search():
    try:
        params = request.json or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            if search_status.get("is_searching", False):
                return jsonify({"error": "Uma busca de vagas já está em andamento."}), 400
            
            search_thread = threading.Thread(
                target=search_jobs_thread,
                args=(
                    params.get('keywords', ''),
                    params.get('location', ''),
                    params.get('max_date', 'r7d'),  # Valor padrão para vagas
                    params.get('distance', ''),
                    params.get('job_type', []),
                    params.get('place', []),
                    int(params.get('limit_jobs', 100))
                )
            )
            search_thread.daemon = True
            search_thread.start()
            
            return jsonify({"message": "Busca de vagas iniciada."}), 200
        
        elif search_type == 'publications':
            if publications_status.get("is_searching", False):
                return jsonify({"error": "Uma busca de publicações já está em andamento."}), 400
            
            search_thread = threading.Thread(
                target=search_publications_thread,
                args=(
                    params.get('keywords', ''),
                    params.get('max_date', 'past-week'),  # Valor padrão
                    int(params.get('limit_publications', 50))
                )
            )
            search_thread.daemon = True
            search_thread.start()
            
            return jsonify({"message": "Busca de publicações iniciada."}), 200
        
        elif search_type == 'people':
            if people_status.get("is_searching", False):
                return jsonify({"error": "Uma busca de pessoas já está em andamento."}), 400
            
            search_thread = threading.Thread(
                target=search_people_thread,
                args=(
                    params.get('keywords', ''),
                    params.get('location', ''),
                    bool(params.get('hiring_only', False)),
                    params.get('hiring_keywords', []),
                    int(params.get('limit_people', 50))
                )
            )
            search_thread.daemon = True
            search_thread.start()
            
            return jsonify({"message": "Busca de pessoas iniciada."}), 200
        
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400
            
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

@app.route('/stop', methods=['POST'])
def stop_search():
    try:
        params = request.json or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            search_status["is_searching"] = False
            return jsonify({"message": "Busca de vagas interrompida."}), 200
        elif search_type == 'publications':
            publications_status["is_searching"] = False
            return jsonify({"message": "Busca de publicações interrompida."}), 200
        elif search_type == 'people':
            people_status["is_searching"] = False
            return jsonify({"message": "Busca de pessoas interrompida."}), 200
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400
    except Exception as e:
        # Fallback: parar todos os tipos de busca
        search_status["is_searching"] = False
        publications_status["is_searching"] = False
        people_status["is_searching"] = False
        return jsonify({"message": "Busca interrompida."}), 200

@app.route('/status')
def get_search_status():
    try:
        params = request.args or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            return jsonify(search_status)
        elif search_type == 'publications':
            return jsonify(publications_status)
        elif search_type == 'people':
            return jsonify(people_status)
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400
    except Exception as e:
        return jsonify({"error": f"Erro ao obter status: {str(e)}"}), 500

@app.route('/results')
def get_search_results():
    try:
        params = request.args or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            return jsonify(search_status.get("results", []))
        elif search_type == 'publications':
            return jsonify(publications_status.get("results", []))
        elif search_type == 'people':
            return jsonify(people_status.get("results", []))
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400
    except Exception as e:
        return jsonify({"error": f"Erro ao obter resultados: {str(e)}"}), 500

@app.route('/job/<job_id>')
def get_job_details(job_id):
    job = next((job for job in search_status.get("results", []) if job.get('id') == job_id), None)
    if job:
        return jsonify(job)
    return jsonify({"error": "Vaga não encontrada."}), 404

def generate_csv(items):
    output = io.StringIO()
    
    if not items:
        return ""
    
    # Determinar se são vagas, publicações ou pessoas
    is_publication = any('author' in item for item in items)
    is_person = any(item.get('type') == 'person' for item in items)
    
    if is_publication:
        fieldnames = ['title', 'author', 'content', 'time', 'link', 'type']
        preferred_fields = ['title', 'author', 'content', 'time', 'link']
    elif is_person:
        fieldnames = ['name', 'headline', 'location', 'link', 'type']
        preferred_fields = ['name', 'headline', 'location', 'link']
    else:
        fieldnames = sorted({key for item in items for key in item.keys()} - {'error'})
        preferred_fields = ['id', 'title', 'company', 'location', 'time', 'link', 'description']
    
    for field in reversed(preferred_fields):
        if field in fieldnames:
            fieldnames.remove(field)
            fieldnames.insert(0, field)

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    
    for item in items:
        if not item.get('error'):
            writer.writerow(item)

    output.seek(0)
    return output.getvalue()

@app.route('/export/csv')
def export_to_csv():
    try:
        params = request.args or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            results = [job for job in search_status.get("results", []) if not job.get('error')]
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"vagas_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        elif search_type == 'publications':
            results = publications_status.get("results", [])
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"publicacoes_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        elif search_type == 'people':
            results = people_status.get("results", [])
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"pessoas_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400

        return Response(generate_csv(results), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        return jsonify({"error": f"Erro na exportação: {str(e)}"}), 500

@app.route('/export/json')
def export_to_json():
    try:
        params = request.args or {}
        search_type = params.get('type', 'jobs')
        
        if search_type == 'jobs':
            results = [job for job in search_status.get("results", []) if not job.get('error')]
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"vagas_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        elif search_type == 'publications':
            results = publications_status.get("results", [])
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"publicacoes_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        elif search_type == 'people':
            results = people_status.get("results", [])
            if not results:
                return jsonify({"error": "Nenhum resultado disponível para exportação."}), 400
            filename = f"pessoas_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            return jsonify({"error": "Tipo de busca inválido."}), 400

        return Response(json.dumps(results, ensure_ascii=False, indent=2), mimetype="application/json", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        return jsonify({"error": f"Erro na exportação: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
