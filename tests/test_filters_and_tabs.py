import json
import subprocess
import time
from unittest.mock import patch

import pytest

from app import DEFAULT_LIMIT_JOBS, UNLIMITED_JOBS_CAP, app
from scraper import (
    UNLIMITED_JOBS_CAP as SCRAPER_UNLIMITED_CAP,
    build_params,
    classify_job_match,
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
    cases = [
        (None, DEFAULT_LIMIT_JOBS),
        (25, 25),
        (75, 75),
        ("unlimited", UNLIMITED_JOBS_CAP),
        (0, UNLIMITED_JOBS_CAP),
        (500, UNLIMITED_JOBS_CAP),
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

    assert get_job_count(None, "python", "", "", "", [], [], limit_jobs=0) == SCRAPER_UNLIMITED_CAP
    assert get_job_count(None, "python", "", "", "", [], [], limit_jobs=999) == SCRAPER_UNLIMITED_CAP


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
      'labelLimitJobs', 'limit25', 'limit50', 'limit75', 'limitUnlimited',
      'translatedFromTo'
    ];
    for (const l of langs) {
      if ('labelEasyApply' in i18n[l]) {
        throw new Error('Obsolete labelEasyApply present in ' + l);
      }
      if (!i18n[l].langNames || typeof i18n[l].langNames !== 'object' || !i18n[l].langNames.en || !i18n[l].langNames.pt) {
        throw new Error('Missing langNames map in ' + l);
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

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [[["Desenvolvedor Python Sênior", "Senior Python Developer"]], None, "en"]

    class FakeSameResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [[["Desenvolvedor Python Pleno", "Desenvolvedor Python Pleno"]], None, "pt"]

    with patch("translator.requests.post", return_value=FakeResp()):
        batch = translator.translate_jobs_batch(
            [{"id": "901", "title": "Senior Python Developer", "description": "Senior Python Developer"}],
            "pt",
        )
        assert batch["901"]["title"] == "Desenvolvedor Python Sênior"
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
    with patch("translator.requests.post", return_value=FakeSameResp()):
        batch_same = translator.translate_jobs_batch(
            [{"id": "902", "title": "Desenvolvedor Python Pleno", "description": "Desenvolvedor Python Pleno"}],
            "pt",
        )
        assert batch_same["902"]["source_lang"] == "pt"
        assert batch_same["902"]["was_translated"] is False

