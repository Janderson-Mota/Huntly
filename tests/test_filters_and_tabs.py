import json
import subprocess
import time
from unittest.mock import patch

import pytest

from app import DEFAULT_LIMIT_JOBS, MAX_LIMIT_JOBS, MIN_LIMIT_JOBS, UNLIMITED_JOBS_CAP, app
from scraper import (
    UNLIMITED_JOBS_CAP as SCRAPER_UNLIMITED_CAP,
    _infer_search_locale,
    adapt_keywords_for_location,
    build_experience_search_queries,
    build_params,
    classify_job_match,
    detect_description_experience_levels,
    detect_title_experience_levels,
    detect_work_mode,
    get_job_count,
    job_matches_experience,
    job_matches_location,
    job_matches_work_mode,
    jobs_state,
    search_jobs_thread,
)


@pytest.fixture(autouse=True)
def reset_state():
    jobs_state.stop()
    jobs_state.set_results([])
    yield
    jobs_state.stop()
    jobs_state.set_results([])


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def _wait_thread_call(mock_thread):
    for _ in range(25):
        if mock_thread.called:
            return
        time.sleep(0.02)
    assert mock_thread.called


def test_search_multiselect_accepts_lists_and_single_strings(client):
    with patch("app.search_jobs_thread") as mock_thread:
        res = client.post(
            "/search",
            json={
                "type": "jobs",
                "keywords": "python",
                "experience_level": ["1", "2"],
                "work_mode": ["2", "3"],
                "limit_jobs": 50,
            },
        )
        assert res.status_code == 200
        _wait_thread_call(mock_thread)
        args, _ = mock_thread.call_args
        assert args[5] == ["2", "3"]  # place / work_mode
        assert args[6] == 50  # limit_jobs
        assert args[7] == ["1", "2"]  # experience_level

    jobs_state.stop()
    with patch("app.search_jobs_thread") as mock_thread:
        res = client.post(
            "/search",
            json={
                "type": "jobs",
                "keywords": "python",
                "experience_level": "1",
                "place": "2,3",
            },
        )
        assert res.status_code == 200
        _wait_thread_call(mock_thread)
        args, _ = mock_thread.call_args
        assert args[5] == ["2", "3"]
        assert args[6] == DEFAULT_LIMIT_JOBS
        assert args[7] == ["1"]


def test_limit_jobs_parsing_and_unlimited_cap(client):
    assert DEFAULT_LIMIT_JOBS == 25
    assert MIN_LIMIT_JOBS == 25
    assert MAX_LIMIT_JOBS == 50
    assert UNLIMITED_JOBS_CAP == 50
    assert SCRAPER_UNLIMITED_CAP == 50

    cases = [
        (None, 25),
        (0, 25),
        (10, 25),
        (25, 25),
        (40, 40),
        (50, 50),
        (75, 50),
        ("unlimited", 50),
        (500, 50),
    ]
    for raw_limit, expected in cases:
        jobs_state.stop()
        payload = {"type": "jobs", "keywords": "python"}
        if raw_limit is not None:
            payload["limit_jobs"] = raw_limit
        with patch("app.search_jobs_thread") as mock_thread:
            res = client.post("/search", json=payload)
            assert res.status_code == 200
            _wait_thread_call(mock_thread)
            args, _ = mock_thread.call_args
            assert args[6] == expected

    assert get_job_count(None, "python", "", "", "", [], [], limit_jobs=0) == 25
    assert get_job_count(None, "python", "", "", "", [], [], limit_jobs=10) == 25
    assert get_job_count(None, "python", "", "", "", [], [], limit_jobs=999) == 50


def test_build_params_encodes_multiselect_comma_separated_and_deduped():
    qs_lists = build_params(
        keywords="python",
        location="Brazil",
        time_range="",
        distance="",
        job_type=[],
        place=[],
        experience_level=["1", "2", "3,4"],
        work_mode=["2", "3"],
    )
    assert "f_E=1%2C2%2C3%2C4" in qs_lists or "f_E=1,2,3,4" in qs_lists
    assert "f_WT=2%2C3" in qs_lists or "f_WT=2,3" in qs_lists

    qs_str = build_params(
        keywords="python",
        location="Brazil",
        time_range="",
        distance="",
        job_type=[],
        place="2,3,2",
        experience_level="3,4",
    )
    assert "f_E=3%2C4" in qs_str or "f_E=3,4" in qs_str
    assert "f_WT=2%2C3" in qs_str or "f_WT=2,3" in qs_str

    qs_semantic = build_params(
        keywords="python",
        location="Brazil",
        time_range="",
        distance="",
        job_type=[],
        place=[],
        experience_level=["trainee", "tech_lead", "5,6"],
    )
    assert "f_E=1%2C2%2C4%2C5%2C6" in qs_semantic or "f_E=1,2,4,5,6" in qs_semantic
    assert "tech_lead" not in qs_semantic
    assert "trainee" not in qs_semantic


def test_expanded_it_seniority_levels_post_validation():
    intern_job = {"title": "Estágio em Python", "experience_level_code": "internship"}
    trainee_job = {"title": "Programa Trainee em Engenharia", "experience_level_code": "internship"}
    junior_job = {"title": "Desenvolvedor Python Júnior", "experience_level_code": "entry_level"}
    pleno_job = {"title": "Engenheiro de Software Pleno", "experience_level_code": "mid_senior"}
    senior_job = {"title": "Senior Backend Engineer", "experience_level_code": "mid_senior"}
    tech_lead_job = {"title": "Tech Lead Python", "experience_level_code": "mid_senior"}
    director_job = {"title": "Diretor de Tecnologia", "experience_level_code": "director"}
    generic_mid_senior = {"title": "Desenvolvedor Python", "experience_level_code": "mid_senior"}

    assert job_matches_experience(intern_job, ["1"]) is True
    assert job_matches_experience(trainee_job, ["trainee"]) is True
    assert job_matches_experience(intern_job, ["trainee"]) is False
    assert job_matches_experience(junior_job, ["2"]) is True
    assert job_matches_experience(pleno_job, ["3,4"]) is True
    assert job_matches_experience(senior_job, ["4"]) is True
    assert job_matches_experience(tech_lead_job, ["4"]) is False
    assert job_matches_experience(tech_lead_job, ["tech_lead"]) is True
    assert job_matches_experience(senior_job, ["tech_lead"]) is False
    assert job_matches_experience(generic_mid_senior, ["tech_lead"]) is False
    assert job_matches_experience(director_job, ["5,6"]) is True


def test_post_validation_experience_and_work_mode_classification():
    # Estágio ["1"]: aceita estágio, rejeita Pleno-sênior / Não aplicável / título Senior
    intern_job = {"title": "Estágio em Python", "experience_level_code": "internship"}
    mid_senior_job = {"title": "Desenvolvedor Backend", "experience_level_code": "mid_senior"}
    na_job = {"title": "Engenheiro de Software", "experience_level_code": "not_applicable"}
    contradictory_title = {"title": "Senior Python Developer", "experience_level_code": "internship"}

    assert job_matches_experience(intern_job, ["1"]) is True
    assert job_matches_experience(mid_senior_job, ["1"]) is False
    assert job_matches_experience(na_job, ["1"]) is False
    assert job_matches_experience(contradictory_title, ["1"]) is False

    # Estágio + Júnior ["1", "2"]
    junior_job = {"title": "Desenvolvedor Python Júnior", "experience_level_code": "entry_level"}
    tech_lead = {"title": "Tech Lead Python", "experience_level_code": "mid_senior"}
    assert job_matches_experience(intern_job, ["1", "2"]) is True
    assert job_matches_experience(junior_job, ["1", "2"]) is True
    assert job_matches_experience(tech_lead, ["1", "2"]) is False

    # Pleno ["3,4"]: aceita Pleno / mid_senior genérico, rejeita Senior explícito
    pleno_job = {"title": "Engenheiro de Software Pleno", "experience_level_code": "mid_senior"}
    generic_mid = {"title": "Software Engineer", "experience_level_code": "mid_senior"}
    senior_job = {"title": "Senior Backend Developer", "experience_level_code": "mid_senior"}
    assert "senior" in detect_title_experience_levels("Senior Backend Developer")
    assert "internship" not in detect_title_experience_levels("Engineering Manager (Early Stage)")
    assert job_matches_experience(pleno_job, ["3,4"]) is True
    assert job_matches_experience(generic_mid, ["3,4"]) is True
    assert job_matches_experience(senior_job, ["3,4"]) is False

    # Modalidades + negação
    assert detect_work_mode({"title": "Python Dev (100% Remoto)"}) == "remote"
    assert detect_work_mode({"title": "Backend Engineer", "description": "Modelo híbrido 2 dias presenciais e 3 remoto"}) == "hybrid"
    assert detect_work_mode({"title": "Dev Java", "description": "Vaga presencial. Não é remoto."}) == "onsite"

    assert job_matches_work_mode({"title": "Dev (Remoto)"}, ["2", "3"]) is True
    assert job_matches_work_mode({"title": "Dev", "description": "Regime híbrido"}, ["2", "3"]) is True
    assert job_matches_work_mode({"title": "Dev", "description": "100% presencial"}, ["2", "3"]) is False
    assert job_matches_work_mode({"title": "Dev", "description": "Atuação com Python e SQL"}, ["2", "3"]) is False


def test_post_validation_location_strict_city_and_state():
    req = "Belo Horizonte, Minas Gerais, Brazil"
    assert job_matches_location("Belo Horizonte, Minas Gerais, Brasil", req) is True
    assert job_matches_location("Belo Horizonte, MG", req) is True
    assert job_matches_location("São Paulo, SP", req) is False
    assert job_matches_location("Uberlândia, Minas Gerais, Brasil", req) is False

    req_state = "Minas Gerais, Brazil"
    assert job_matches_location("Uberlândia, MG", req_state) is True
    assert job_matches_location("Belo Horizonte, Minas Gerais, Brazil", req_state) is True
    assert job_matches_location("Curitiba, PR", req_state) is False


def test_classify_job_match_and_thread_integration():
    def fake_detail(_session, job_id, _summary=None, run_id=None, lang="en"):
        data = {
            "1": {
                "id": "1",
                "title": "Estágio Python (Remoto)",
                "company": "Empresa A",
                "location": "Belo Horizonte, MG",
                "time": "Há 1 dia",
                "link": "https://www.linkedin.com/jobs/view/1/",
                "experience_level_code": "internship",
                "description": "Trabalho 100% remoto com Python.",
            },
            "2": {
                "id": "2",
                "title": "Senior Python Developer",
                "company": "Empresa B",
                "location": "São Paulo, SP",
                "time": "Há 2 dias",
                "link": "https://www.linkedin.com/jobs/view/2/",
                "experience_level_code": "mid_senior",
                "description": "Atuação presencial em escritório.",
            },
        }
        return data[job_id]

    with (
        patch("scraper.get_job_count", return_value=25),
        patch("scraper.get_job_ids_per_page", return_value=["1", "2"]),
        patch("scraper.get_job_detail", side_effect=fake_detail),
    ):
        search_jobs_thread(
            keywords="python",
            location="Belo Horizonte, Minas Gerais, Brazil",
            max_date="",
            distance="",
            job_type=[],
            place=["2"],
            limit_jobs=25,
            experience_level=["1"],
            sort_by="R",
            easy_apply=False,
            already_started=False,
            lang="pt",
        )

    results = jobs_state.get_results()
    assert len(results) == 2
    by_id = {item["id"]: item for item in results}
    assert by_id["1"]["match_category"] == "matched"
    assert by_id["1"]["work_mode_code"] == "remote"
    assert by_id["2"]["match_category"] == "recommended"
    assert by_id["2"]["work_mode_code"] == "onsite"


def test_results_and_export_respect_active_tab_and_filters(client):
    jobs_state.set_results(
        [
            {
                "id": "10",
                "title": "Dev Python Júnior",
                "company": "Alpha",
                "location": "São Paulo, SP",
                "time": "Há 1 dia",
                "link": "https://www.linkedin.com/jobs/view/10/",
                "description": "Python API",
                "match_category": "matched",
            },
            {
                "id": "20",
                "title": "Senior Go Architect",
                "company": "Beta",
                "location": "Rio de Janeiro, RJ",
                "time": "Há 2 dias",
                "link": "https://www.linkedin.com/jobs/view/20/",
                "description": "Go distributed systems",
                "match_category": "recommended",
            },
        ]
    )

    all_res = client.get("/results?type=jobs").get_json()
    assert [j["id"] for j in all_res] == ["10", "20"]

    matched_res = client.get("/results?type=jobs&tab=matched").get_json()
    assert [j["id"] for j in matched_res] == ["10"]

    rec_res = client.get("/results?type=jobs&tab=recommended").get_json()
    assert [j["id"] for j in rec_res] == ["20"]

    csv_matched = client.get("/export/csv?type=jobs&tab=matched&lang=pt").data.decode("utf-8-sig")
    assert "Dev Python Júnior" in csv_matched
    assert "Senior Go Architect" not in csv_matched

    json_rec = json.loads(client.get("/export/json?type=jobs&tab=recommended&lang=en").data.decode("utf-8"))
    assert [j["id"] for j in json_rec] == ["20"]

    filtered_out = client.get("/export/json?type=jobs&tab=matched&exclude=Python")
    assert filtered_out.status_code == 400


def test_i18n_8_langs_parity_with_new_multiselect_tabs_and_limit_keys():
    with open("templates/index.html", encoding="utf-8") as fh:
        html = fh.read()
    assert html.count('<input type="checkbox" name="experience_level"') == 7
    assert 'id="easy_apply"' not in html
    assert '<option value="75"' not in html
    assert '<option value="unlimited"' not in html

    js_check = r"""
    const fs = require('fs');
    const vm = require('vm');
    const code = fs.readFileSync('static/i18n.js', 'utf8');
    const ctx = { window: {} };
    vm.runInNewContext(code, ctx);
    const i18n = ctx.window.HUNTLY_I18N;
    const langs = Object.keys(i18n);
    const refKeys = Object.keys(i18n.pt).sort();
    const required = [
      'expIntern', 'expTrainee', 'expJunior', 'expMid', 'expSenior', 'expTechLead', 'expDirector',
      'ariaExperienceMulti', 'ariaWorkModeMulti',
      'ariaResultsTabs', 'tabMatched', 'tabRecommended',
      'emptyTabMatchedTitle', 'emptyTabMatchedDesc',
      'emptyTabRecommendedTitle', 'emptyTabRecommendedDesc',
      'labelLimitJobs', 'limit25', 'limit50',
      'translatedFromTo', 'modalTranslating',
      'ariaMainNav', 'ariaFooter', 'footerRights'
    ];
    for (const l of langs) {
      if ('labelEasyApply' in i18n[l] || 'limit75' in i18n[l] || 'limitUnlimited' in i18n[l]) {
        throw new Error('Obsolete filter/limit key present in ' + l);
      }
      if (!i18n[l].langNames || typeof i18n[l].langNames !== 'object') {
        throw new Error('Missing langNames map in ' + l);
      }
      for (const code of ['pt', 'en', 'es', 'fr', 'it', 'de', 'ru', 'zh']) {
        if (!i18n[l].langNames[code] || typeof i18n[l].langNames[code] !== 'string') {
          throw new Error('Missing langNames.' + code + ' in ' + l);
        }
      }
    }
    const errors = [];
    for (const l of langs) {
      const k = Object.keys(i18n[l]).sort();
      if (JSON.stringify(k) !== JSON.stringify(refKeys)) {
        errors.push('Key mismatch in ' + l);
      }
      for (const req of required) {
        if (!i18n[l][req] || typeof i18n[l][req] !== 'string') {
          errors.push('Missing/empty ' + req + ' in ' + l);
        }
      }
      if (!Array.isArray(i18n[l].roleSuggestions) || i18n[l].roleSuggestions.length !== 51) {
        errors.push('Expected 51 roleSuggestions in ' + l);
      }
      for (const arrowKey of [
        'btnExportCsv', 'btnExportJson', 'btnDetails',
        'btnOpenLinkedin', 'modalOpenLinkedin',
        'pagePrev', 'pageNext', 'translatedFromTo'
      ]) {
        if (/[↗→←]/.test(String(i18n[l][arrowKey] || ''))) {
          errors.push('Unexpected arrow glyph in ' + arrowKey + ' for ' + l);
        }
      }
      if (/\bIDs?\b/i.test(String(i18n[l].statusCollectingPages || ''))) {
        errors.push('Technical ID jargon present in statusCollectingPages for ' + l);
      }
    }
    console.log(JSON.stringify({ langs, errors }));
    """
    proc = subprocess.run(["node", "-e", js_check], capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout)
    assert out["langs"] == ["pt", "en", "es", "fr", "it", "de", "ru", "zh"]
    assert out["errors"] == []


def test_translate_jobs_to_pt_and_source_meta(client):
    import translator

    translator.clear_cache()

    class FakeArgosTranslator:
        def __init__(self, prefix):
            self.prefix = prefix

        def translate(self, text):
            return f"{self.prefix}{text}"

    with patch(
        "translator._get_argos_translation",
        side_effect=lambda src, dst: FakeArgosTranslator(f"[{dst.upper()}] ") if src == "en" else None,
    ):
        batch = translator.translate_jobs_batch(
            [{"id": "901", "title": "Senior Python Developer", "description": "Senior Python Developer"}],
            "pt",
        )
        assert batch["901"]["title"] == "[PT] Senior Python Developer"
        assert batch["901"]["source_lang"] == "en"
        assert batch["901"]["target_lang"] == "pt"
        assert batch["901"]["was_translated"] is True

        jobs_state.set_results(
            [{"id": "901", "title": "Senior Python Developer", "description": "Senior Python Developer"}]
        )
        res = client.post("/translate", json={"lang": "pt", "job_ids": ["901"]})
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["lang"] == "pt"
        assert payload["translations"]["901"]["was_translated"] is True
        assert payload["translations"]["901"]["source_lang"] == "en"

    translator.clear_cache()
    batch_same = translator.translate_jobs_batch(
        [{"id": "902", "title": "Desenvolvedor Python Pleno", "description": "Desenvolvedor Python Pleno"}],
        "pt",
    )
    assert batch_same["902"]["source_lang"] == "pt"
    assert batch_same["902"]["was_translated"] is False
    assert batch_same["902"]["title"] == "Desenvolvedor Python Pleno"


def test_translate_preview_mode_and_full_mode_contract(client):
    import translator

    translator.clear_cache()
    sent_texts = []

    class RecordingArgosTranslator:
        def translate(self, text):
            sent_texts.append(text)
            return f"[PT] {text}"

    long_desc = " ".join(["Python backend service architecture experience"] * 25)
    assert len(long_desc) > translator.PREVIEW_DESC_CHARS
    short_desc = "Remote backend Python role."

    with patch("translator._get_argos_translation", return_value=RecordingArgosTranslator()):
        preview_batch = translator.translate_jobs_batch(
            [
                {"id": "910", "title": "Backend Engineer", "description": long_desc},
                {"id": "911", "title": "Data Engineer", "description": short_desc},
            ],
            "pt",
            mode="preview",
        )
        assert preview_batch["910"]["is_full"] is False
        assert preview_batch["910"]["description"] is None
        assert preview_batch["910"]["excerpt"].startswith("[PT] ")
        assert preview_batch["910"]["was_translated"] is True
        # Original snippet sent for long description was capped at PREVIEW_DESC_CHARS
        assert any(txt.startswith("Python backend") and len(txt) <= translator.PREVIEW_DESC_CHARS for txt in sent_texts)

        assert preview_batch["911"]["is_full"] is True
        assert preview_batch["911"]["description"] == f"[PT] {short_desc}"
        assert preview_batch["911"]["excerpt"] == f"[PT] {short_desc}"

        full_batch = translator.translate_jobs_batch(
            [{"id": "910", "title": "Backend Engineer", "description": long_desc}],
            "pt",
            mode="full",
        )
        assert full_batch["910"]["is_full"] is True
        assert full_batch["910"]["description"] == f"[PT] {long_desc}"

        jobs_state.set_results([{"id": "910", "title": "Backend Engineer", "description": long_desc}])
        res_preview = client.post("/translate", json={"lang": "pt", "mode": "preview", "job_ids": ["910"]})
        assert res_preview.status_code == 200
        preview_payload = res_preview.get_json()
        assert preview_payload["mode"] == "preview"
        assert preview_payload["translations"]["910"]["is_full"] is False
        assert preview_payload["translations"]["910"]["description"] is None

        bad_mode = client.post("/translate", json={"lang": "pt", "mode": "invalid", "job_ids": ["910"]})
        assert bad_mode.status_code == 400


def test_translate_deduplicates_identical_texts_and_skips_obvious_same_lang():
    import translator

    translator.clear_cache()
    calls = []

    class RecordingArgosTranslator:
        def translate(self, text):
            calls.append(text)
            return f"[PT] {text}"

    long_pt_desc = (
        "Buscamos profissional com experiência em desenvolvimento backend Python, Docker e AWS. "
        "Atuação com nossa equipe de engenharia, pelos projetos da empresa, com benefícios e trabalho remoto. "
        "Você também terá contato com sistemas distribuídos."
    )
    long_es_desc = (
        "Buscamos desarrollador backend con experiencia en nuestro equipo de ingeniería para el puesto remoto. "
        "Los conocimientos en desarrollo de sistemas y los beneficios que ofrecemos también forman parte del trabajo."
    )
    bilingual_desc = (
        "Buscamos nossa equipe com você e também nossos benefícios pela vaga. "
        "We are looking for a strong backend engineer with Python experience and cloud architecture skills."
    )

    with patch("translator._get_argos_translation", return_value=RecordingArgosTranslator()):
        # Deduplicates identical title across multiple jobs & skips long clear-PT description
        batch = translator.translate_jobs_batch(
            [
                {"id": "920", "title": "Senior Backend Engineer", "description": long_pt_desc},
                {"id": "921", "title": "Senior Backend Engineer", "description": long_pt_desc},
            ],
            "pt",
            mode="full",
        )
        assert calls == ["Senior Backend Engineer"]
        assert batch["920"]["title"] == "[PT] Senior Backend Engineer"
        assert batch["921"]["title"] == "[PT] Senior Backend Engineer"
        assert batch["920"]["description"] == long_pt_desc
        assert batch["920"]["source_lang"] in ("en", "pt")

        # Verify pure same-lang skips with zero Argos calls
        calls.clear()
        out_pt, src_pt = translator.translate_text_with_meta(long_pt_desc, "pt")
        assert calls == []
        assert out_pt == long_pt_desc
        assert src_pt == "pt"

        # Clear Spanish description must NOT be skipped when target_lang="pt"
        out_es, _src_es = translator.translate_text_with_meta(long_es_desc, "pt")
        assert len(calls) == 1
        assert out_es == f"[PT] {long_es_desc}"

        # Bilingual mixed PT+EN description must NOT be skipped when target_lang="pt"
        calls.clear()
        out_bi, _src_bi = translator.translate_text_with_meta(bilingual_desc, "pt")
        assert len(calls) == 1
        assert out_bi == f"[PT] {bilingual_desc}"


def test_search_allows_empty_keywords_when_filter_selected_and_rejects_empty_form(client):
    # Completely empty filters (even with default sort_by/limit_jobs overridden) -> 400
    empty_res = client.post(
        "/search",
        json={"type": "jobs", "keywords": "   ", "sort_by": "DD", "limit_jobs": 50},
    )
    assert empty_res.status_code == 400
    assert empty_res.get_json()["error_code"] == "errNoKeyword"

    valid_filter_payloads = [
        {"type": "jobs", "keywords": "", "location": "Brazil"},
        {"type": "jobs", "keywords": "", "max_date": "r24h"},
        {"type": "jobs", "keywords": "", "experience_level": ["2"]},
        {"type": "jobs", "keywords": "", "work_mode": ["2"]},
    ]

    with patch("app.threading.Thread") as mock_thread:
        mock_thread.return_value.start.return_value = None
        for payload in valid_filter_payloads:
            jobs_state.stop()
            res = client.post("/search", json=payload)
            assert res.status_code == 200, f"Expected 200 for {payload}, got {res.status_code}: {res.get_json()}"

    query = build_params(
        "",
        "Brazil",
        "r24h",
        "",
        [],
        ["2"],
        experience_level=["1", "2"],
    )
    assert "keywords=" not in query
    assert "geoId=106057199" in query
    assert "f_TPR=r24h" in query
    assert "f_WT=2" in query
    assert "f_E=1%2C2" in query


def test_home_renders_minimalist_footer(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert 'class="navbar-nav"' in html
    assert 'class="navbar-controls"' in html
    assert '🇺🇸 Inglês' in html
    assert '🇪🇸 Espanhol' in html
    assert '🇨🇳 Chinês' in html
    assert 'id="modal-translating-indicator"' in html
    assert 'data-i18n="modalTranslating"' in html
    assert 'bi-arrow-counterclockwise' not in html
    assert 'bi-arrow-right' not in html
    assert '↗' not in html
    assert 'class="btn btn-outline btn-sm" id="reset-filters-btn"' in html
    assert 'class="btn btn-primary btn-sm" id="search-btn"' in html
    assert 'class="btn btn-danger btn-sm" id="stop-button"' in html
    assert 'class="btn btn-primary btn-sm" data-i18n="modalOpenLinkedin"' in html
    assert '<footer class="site-footer"' in html
    assert 'data-i18n="footerRights"' in html
    footer_start = html.index('<footer class="site-footer"')
    footer_end = html.index("</footer>", footer_start)
    footer_html = html[footer_start:footer_end]
    assert "<a " not in footer_html


def test_build_experience_search_queries_enriches_php_intern_tech_lead_and_multilevel():
    # PT/Brazil: PHP + Estágio -> PHP Estágio primary, PHP Internship secondary, fallback PHP
    q_pt_intern = build_experience_search_queries("PHP", ["1"], location="Brazil", lang="pt")
    assert q_pt_intern[0] == ("PHP Estágio", ["1"], True)
    assert ("PHP Internship", ["1"], False) in q_pt_intern
    assert ("PHP", ["1"], False) in q_pt_intern

    # US / English: PHP + Estágio -> PHP Internship primary
    q_us_intern = build_experience_search_queries("PHP", ["1"], location="United States", lang="pt")
    assert q_us_intern[0] == ("PHP Internship", ["1"], True)

    # Tech Lead: injects Tech Lead / Líder Técnico / Technical Lead + includes None fallback for Not Applicable
    q_pt_lead = build_experience_search_queries("PHP", ["tech_lead"], location="Brazil", lang="pt")
    assert q_pt_lead[0] == ("PHP Tech Lead", ["tech_lead"], True)
    assert ("PHP Líder Técnico", ["tech_lead"], False) in q_pt_lead
    assert ("PHP Tech Lead", None, False) in q_pt_lead

    q_us_lead = build_experience_search_queries("PHP", ["tech_lead"], location="United States", lang="en")
    assert q_us_lead[0] == ("PHP Tech Lead", ["tech_lead"], True)
    assert ("PHP Technical Lead", ["tech_lead"], False) in q_us_lead

    # Never duplicate level keyword if already typed by the user
    q_already_intern = build_experience_search_queries("Estágio PHP", ["1"], location="Brazil", lang="pt")
    assert q_already_intern[0] == ("Estágio PHP", ["1"], True)
    assert all(kw == "Estágio PHP" for kw, _, _ in q_already_intern)

    q_already_lead = build_experience_search_queries("Tech Lead Python", ["tech_lead"], location="Brazil", lang="pt")
    assert q_already_lead[0] == ("Tech Lead Python", ["tech_lead"], True)

    # Empty keyword with filter selected uses level term directly
    q_empty_kw = build_experience_search_queries("", ["1"], location="Brazil", lang="pt")
    assert q_empty_kw[0] == ("Estágio", ["1"], True)

    # Multi-level splits into separate targeted primary queries instead of impossible AND strings
    q_multi = build_experience_search_queries("PHP", ["1", "2"], location="Brazil", lang="pt")
    primaries = [q for q in q_multi if q[2] is True]
    assert primaries == [("PHP Estágio", ["1"], True), ("PHP Júnior", ["2"], True)]


def test_search_jobs_thread_uses_enriched_queries_and_balanced_multilevel_cap():
    seen_calls = []

    def fake_get_job_ids(_session, kw, *_args, **kwargs):
        exp = kwargs.get("experience_level")
        seen_calls.append((kw, list(exp) if exp else None))
        if kw == "PHP Estágio":
            return [f"intern_{i}" for i in range(15)]
        if kw == "PHP Júnior":
            return [f"jr_{i}" for i in range(15)]
        return [f"extra_{i}" for i in range(10)]

    def fake_detail(_session, job_id, _summary=None, run_id=None, lang="en"):
        if job_id.startswith("intern_"):
            return {
                "id": job_id,
                "title": "Estágio PHP",
                "company": "Emp",
                "location": "Brazil",
                "time": "1 day ago",
                "link": f"https://www.linkedin.com/jobs/view/{job_id}/",
                "experience_level_code": "internship",
                "description": "Vaga de estágio PHP",
            }
        return {
            "id": job_id,
            "title": "Desenvolvedor PHP Júnior",
            "company": "Emp",
            "location": "Brazil",
            "time": "1 day ago",
            "link": f"https://www.linkedin.com/jobs/view/{job_id}/",
            "experience_level_code": "entry_level",
            "description": "Vaga PHP Júnior",
        }

    with (
        patch("scraper.get_job_count", return_value=25),
        patch("scraper.get_job_ids_per_page", side_effect=fake_get_job_ids),
        patch("scraper.get_job_detail", side_effect=fake_detail),
    ):
        search_jobs_thread(
            keywords="PHP",
            location="Brazil",
            max_date="",
            distance="",
            job_type=[],
            place=[],
            limit_jobs=25,
            experience_level=["1", "2"],
            sort_by="R",
            easy_apply=False,
            already_started=False,
            lang="pt",
        )

    assert seen_calls[0] == ("PHP Estágio", ["1"])
    assert ("PHP Júnior", ["2"]) in seen_calls
    results = jobs_state.get_results()
    assert len(results) == 25
    intern_count = sum(1 for r in results if r["id"].startswith("intern_"))
    jr_count = sum(1 for r in results if r["id"].startswith("jr_"))
    assert intern_count == 13
    assert jr_count == 12
    assert all(r["match_category"] == "matched" for r in results)


def test_tech_lead_and_all_levels_match_tab1_even_with_not_applicable_metadata():
    levels_cases = [
        ({"title": "Tech Lead PHP", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "Technical Lead - Backend", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "Líder Técnico PHP", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "PHP Lead", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "Estágio em PHP", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "PHP Internship", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Programa de Trainee", "experience_level_code": "not_applicable"}, ["trainee"], "matched"),
        ({"title": "Desenvolvedor PHP Jr", "experience_level_code": "not_applicable"}, ["2"], "matched"),
        ({"title": "Desenvolvedor PHP Pleno", "experience_level_code": "not_applicable"}, ["3,4"], "matched"),
        ({"title": "Senior PHP Engineer", "experience_level_code": "not_applicable"}, ["4"], "matched"),
        ({"title": "Head de Engenharia", "experience_level_code": "not_applicable"}, ["5,6"], "matched"),
        ({"title": "Diretor de Tecnologia", "experience_level_code": "not_applicable"}, ["5,6"], "matched"),
        # Conflicting explicit titles remain in Aba 2 ('recommended')
        ({"title": "Senior PHP Developer", "experience_level_code": "not_applicable"}, ["1"], "recommended"),
        ({"title": "Estágio em PHP", "experience_level_code": "not_applicable"}, ["tech_lead"], "recommended"),
        ({"title": "Desenvolvedor Júnior", "experience_level_code": "not_applicable"}, ["4"], "recommended"),
    ]
    for job, exp_filter, expected_tab in levels_cases:
        assert classify_job_match(job, experience_level=exp_filter) == expected_tab, (
            f"Unexpected category for {job} with {exp_filter}"
        )


def test_description_semantics_match_role_and_ignore_incidental_mentions():
    intern_from_desc = {
        "title": "Desenvolvedor PHP",
        "experience_level_code": "not_applicable",
        "description": "Vaga de estágio em desenvolvimento PHP com bolsa-auxílio para cursando ensino superior.",
    }
    assert classify_job_match(intern_from_desc, experience_level=["1"]) == "matched"
    assert classify_job_match(intern_from_desc, experience_level=["4"]) == "recommended"

    lead_from_desc = {
        "title": "Engenheiro de Software",
        "experience_level_code": "not_applicable",
        "description": "Buscamos um Tech Lead para liderar a squad de pagamentos em arquitetura distribuída.",
    }
    assert classify_job_match(lead_from_desc, experience_level=["tech_lead"]) == "matched"

    incidental_mentions = {
        "title": "Desenvolvedor PHP",
        "experience_level_code": "not_applicable",
        "description": "Você reporta ao Diretor de Engenharia e ajuda a mentorar juniores no dia a dia.",
    }
    assert detect_description_experience_levels(incidental_mentions["description"]) == set()
    assert classify_job_match(incidental_mentions, experience_level=["5,6"]) == "recommended"
    assert classify_job_match(incidental_mentions, experience_level=["2"]) == "recommended"


def test_translate_endpoint_post_load_batch_cache_and_safe_fallback(client):
    import translator

    translator.clear_cache()
    jobs_state.set_results(
        [
            {
                "id": "950",
                "title": "Senior Backend Engineer",
                "description": "Build scalable Python APIs " + ("and distributed services " * 25),
            },
            {
                "id": "951",
                "title": "Frontend Engineer",
                "description": "Short UI role",
            },
        ]
    )

    calls = []

    class FakeArgosTranslator:
        def translate(self, text):
            calls.append(text)
            return f"[PT] {text}"

    with patch("translator._get_argos_translation", return_value=FakeArgosTranslator()):
        first = client.post("/translate", json={"lang": "pt", "mode": "preview", "job_ids": ["950", "951"]})
        assert first.status_code == 200
        first_data = first.get_json()
        assert first_data["mode"] == "preview"
        assert first_data["translations"]["950"]["title"] == "[PT] Senior Backend Engineer"
        assert first_data["translations"]["950"]["is_full"] is False
        assert first_data["translations"]["950"]["description"] is None
        assert first_data["translations"]["951"]["title"] == "[PT] Frontend Engineer"
        assert len(calls) == 4

        # Second identical batch hits backend LRU cache with zero Argos calls
        calls.clear()
        second = client.post("/translate", json={"lang": "pt", "mode": "preview", "job_ids": ["950", "951"]})
        assert second.status_code == 200
        assert second.get_json() == first_data
        assert calls == []

    # Missing package / runtime failure during modal full translation falls back safely without poisoning cache
    translator.clear_cache()
    with patch("translator._get_argos_translation", return_value=None):
        fallback = client.post("/translate", json={"lang": "pt", "mode": "full", "job_ids": ["951"]})
        assert fallback.status_code == 200
        fb_data = fallback.get_json()
        assert fb_data["translations"]["951"]["title"] == "Frontend Engineer"
        assert fb_data["translations"]["951"]["description"] == "Short UI role"
        assert fb_data["translations"]["951"]["was_translated"] is False
        assert fb_data["translations"]["951"]["source_lang"] is None
        assert translator.cache_size() == 0


def test_translate_all_supported_languages_and_code_normalization(client):
    import translator

    translator.clear_cache()
    jobs_state.set_results(
        [{"id": "1100", "title": "Senior Backend Engineer", "description": "Remote role"}]
    )

    seen_targets = []

    class MultiLangArgos:
        def __init__(self, dst):
            self.dst = dst

        def translate(self, text):
            seen_targets.append(self.dst)
            return f"[{self.dst}] {text}"

    expected_map = [
        ("pt", "pt"),
        ("en", "en"),
        ("es", "es"),
        ("fr", "fr"),
        ("it", "it"),
        ("de", "de"),
        ("ru", "ru"),
        ("zh", "zh"),
        ("zh-CN", "zh"),
        ("ja", "ja"),
        ("pt-BR", "pt"),
    ]

    with patch(
        "translator._get_argos_translation",
        side_effect=lambda _src, dst: MultiLangArgos(dst),
    ):
        for req_code, expected_tl in expected_map:
            seen_targets.clear()
            translator.clear_cache()
            res = client.post("/translate", json={"lang": req_code, "mode": "preview", "job_ids": ["1100"]})
            assert res.status_code == 200, f"Failed for {req_code}: {res.get_json()}"
            payload = res.get_json()
            if expected_tl == "en":
                # Source text is already English -> skipped without invoking Argos
                assert seen_targets == []
                assert payload["translations"]["1100"]["title"] == "Senior Backend Engineer"
                assert payload["translations"]["1100"]["was_translated"] is False
            else:
                assert seen_targets == [expected_tl, expected_tl]
                assert payload["translations"]["1100"]["title"] == f"[{expected_tl}] Senior Backend Engineer"
                assert payload["translations"]["1100"]["description"] == f"[{expected_tl}] Remote role"

    invalid = client.post("/translate", json={"lang": "xx-invalid", "job_ids": ["1100"]})
    assert invalid.status_code == 400
    assert invalid.get_json()["error_code"] == "errInvalidLanguage"


def test_translate_single_batch_sqlite_persistent_cache_and_pivot_real_offline(tmp_path, client):
    import translator
    from scripts.setup_translation import build_required_pairs

    # Verify idempotent pivot pair builder produces bidirectional en<->X (14 pairs for 7 UI langs)
    pairs_7 = build_required_pairs(["pt", "es", "fr", "it", "de", "ja", "zh"])
    assert len(pairs_7) == 14
    assert ("en", "pt") in pairs_7 and ("pt", "en") in pairs_7
    assert ("pt", "de") not in pairs_7

    db_file = str(tmp_path / "test_translation_cache.sqlite3")
    translator.configure_cache_db(db_file)
    try:
        translator.clear_cache()
        jobs = [
            {
                "id": str(1200 + idx),
                "title": f"Backend Engineer {idx}",
                "description": f"Build Python services {idx}",
            }
            for idx in range(25)
        ]
        jobs_state.set_results(jobs)
        argos_calls = []

        class RecordingArgos:
            def translate(self, text):
                argos_calls.append(text)
                return f"[DE] {text}"

        with patch("translator._get_argos_translation", return_value=RecordingArgos()):
            res = client.post(
                "/translate",
                json={"lang": "de", "mode": "preview", "job_ids": [j["id"] for j in jobs]},
            )
            assert res.status_code == 200
            data = res.get_json()
            assert len(data["translations"]) == 25
            assert len(argos_calls) == 50
            assert data["translations"]["1200"]["title"] == "[DE] Backend Engineer 0"
            assert data["translations"]["1224"]["excerpt"] == "[DE] Build Python services 24"

        # Evict RAM cache while preserving SQLite DB: reload must hit SQLite with 0 Argos calls
        translator.clear_memory_cache()
        assert translator.cache_size() == 0
        with patch("translator._get_argos_translation", side_effect=AssertionError("Must hit SQLite cache")):
            res_sqlite = client.post(
                "/translate",
                json={"lang": "de", "mode": "preview", "job_ids": [j["id"] for j in jobs]},
            )
        assert res_sqlite.status_code == 200
        assert res_sqlite.get_json() == data

        # Real offline end-to-end Argos Translate verification (direct en->pt + automatic en pivot pt->de / pt->ja)
        translator.clear_cache()
        direct_out, direct_src = translator.translate_text_with_meta("Senior PHP Developer", "pt")
        assert direct_src == "en"
        assert direct_out != "Senior PHP Developer"

        pivot_de, pivot_src = translator.translate_text_with_meta("Desenvolvedor Backend Python", "de")
        assert pivot_src == "pt"
        assert pivot_de != "Desenvolvedor Backend Python"

        pivot_ja, _ = translator.translate_text_with_meta("Desenvolvedor Backend Python", "ja")
        assert any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in pivot_ja)
    finally:
        translator.clear_cache()
        translator.configure_cache_db(None)


def test_country_language_adaptation_of_keywords_and_experience_terms():
    import translator

    # Country -> language inference across selectors and major markets
    expected_locales = {
        "Brazil": "pt",
        "Portugal": "pt",
        "United States": "en",
        "United Kingdom": "en",
        "Canada": "en",
        "Australia": "en",
        "Ireland": "en",
        "Spain": "es",
        "Mexico": "es",
        "Argentina": "es",
        "Colombia": "es",
        "Chile": "es",
        "Germany": "de",
        "France": "fr",
        "Italy": "it",
        "Japan": "ja",
        "China": "zh",
        "Russia": "ru",
    }
    for country, exp_loc in expected_locales.items():
        assert _infer_search_locale(country, "pt") == exp_loc

    # Portuguese query in US translates via offline Argos into English with original fallback in Pass 2
    translator.clear_cache()
    adapted, locale, orig = adapt_keywords_for_location("Desenvolvedor Backend", "United States", lang="pt")
    assert locale == "en"
    assert orig == "Desenvolvedor Backend"
    assert "developer" in adapted.lower()

    us_queries = build_experience_search_queries("Desenvolvedor Backend", ["1"], location="United States", lang="pt")
    assert us_queries[0][2] is True
    assert "developer" in us_queries[0][0].lower() and "internship" in us_queries[0][0].lower()
    assert any(q[0] == "Desenvolvedor Backend" for q in us_queries)

    # Same experience filter adapts cleanly to Germany, Spain, France, Italy, Japan, China
    de_queries = build_experience_search_queries("PHP", ["1"], location="Germany", lang="pt")
    assert de_queries[0] == ("PHP Praktikum", ["1"], True)
    assert ("PHP Internship", ["1"], False) in de_queries

    es_queries = build_experience_search_queries("PHP", ["1"], location="Mexico", lang="pt")
    assert es_queries[0] == ("PHP Prácticas", ["1"], True)

    fr_queries = build_experience_search_queries("PHP", ["1"], location="France", lang="pt")
    assert fr_queries[0] == ("PHP Stage", ["1"], True)

    it_queries = build_experience_search_queries("PHP", ["1"], location="Italy", lang="pt")
    assert it_queries[0] == ("PHP Stage", ["1"], True)
    assert ("PHP Tirocinio", ["1"], False) in it_queries

    ja_queries = build_experience_search_queries("PHP", ["1"], location="Japan", lang="pt")
    assert ja_queries[0] == ("PHP インターン", ["1"], True)

    zh_queries = build_experience_search_queries("PHP", ["1"], location="China", lang="pt")
    assert zh_queries[0] == ("PHP 实习", ["1"], True)

    # Pure tech term + universal Tech Lead phrase stay intact regardless of country
    adapted_php, _, _ = adapt_keywords_for_location("PHP", "United States", lang="pt")
    assert adapted_php == "PHP"
    adapted_lead, _, _ = adapt_keywords_for_location("Tech Lead Python", "Brazil", lang="pt")
    assert adapted_lead == "Tech Lead Python"

    # Safe fallback if offline translation raises
    with patch("translator.translate_text_with_meta", side_effect=RuntimeError("model load error")):
        fb_kw, fb_loc, fb_orig = adapt_keywords_for_location("Desenvolvedor Backend", "United States", lang="pt")
        assert fb_kw == "Desenvolvedor Backend"
        assert fb_loc == "en"
        assert fb_orig == "Desenvolvedor Backend"


def test_multilingual_experience_classification_for_tab1():
    multilingual_cases = [
        ({"title": "PHP Praktikum (m/w/d)", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Werkstudent Backend PHP", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Prácticas Desarrollo Backend", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Stage Développeur PHP", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Offre Stage Développeur Backend", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Tirocinio Sviluppatore PHP", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Backend Internship", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Estágio em PHP", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "バックエンド インターン", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "后端开发实习", "experience_level_code": "not_applicable"}, ["1"], "matched"),
        ({"title": "Lead Technique Backend", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "テックリード PHP", "experience_level_code": "not_applicable"}, ["tech_lead"], "matched"),
        ({"title": "Développeur PHP Confirmé", "experience_level_code": "not_applicable"}, ["3,4"], "matched"),
    ]
    for job, exp_filter, expected in multilingual_cases:
        assert classify_job_match(job, experience_level=exp_filter) == expected, f"Failed for {job}"










