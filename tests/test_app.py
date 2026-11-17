import json

import pytest

from app import app, generate_csv
from scraper import jobs_state


@pytest.fixture(autouse=True)
def reset_states():
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


def test_home_route(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"huntly" in res.data.lower()


def test_status_valid_and_invalid_types(client):
    res = client.get("/status?type=jobs")
    assert res.status_code == 200
    data = res.get_json()
    assert "is_searching" in data
    assert "progress" in data
    assert "status" in data

    bad = client.get("/status?type=invalid")
    assert bad.status_code == 400


def test_search_validation(client):
    bad_type = client.post("/search", json={"type": "unknown"})
    assert bad_type.status_code == 400

    bad_limit = client.post("/search", json={"type": "jobs", "limit_jobs": "abc"})
    assert bad_limit.status_code == 400


def test_export_empty_returns_400(client):
    res_csv = client.get("/export/csv?type=jobs")
    assert res_csv.status_code == 400

    res_json = client.get("/export/json?type=jobs")
    assert res_json.status_code == 400


def test_export_csv_and_json_with_results(client):
    jobs_state.set_results(
        [
            {
                "id": "123",
                "title": "Dev Python Júnior",
                "company": "Empresa BR",
                "location": "São Paulo",
                "time": "há 1 dia",
                "link": "https://example.com/123",
                "description": "Vaga remota",
            }
        ]
    )

    res_csv = client.get("/export/csv?type=jobs")
    assert res_csv.status_code == 200
    text = res_csv.data.decode("utf-8-sig")
    assert "Dev Python Júnior" in text
    assert "Empresa BR" in text

    res_json = client.get("/export/json?type=jobs")
    assert res_json.status_code == 200
    payload = json.loads(res_json.data.decode("utf-8"))
    assert len(payload) == 1
    assert payload[0]["id"] == "123"


def test_job_detail_endpoint(client):
    jobs_state.set_results([{"id": "42", "title": "Backend Engineer"}])

    found = client.get("/job/42")
    assert found.status_code == 200
    assert found.get_json()["title"] == "Backend Engineer"

    missing = client.get("/job/999")
    assert missing.status_code == 404


def test_generate_csv_empty():
    assert generate_csv([]) == ""
