from unittest.mock import MagicMock, patch

from scraper import MAX_RETRIES, build_params, calculate_time_range, get_job_ids_per_page, jobs_state
from state import MAX_LOG_ENTRIES, SearchState


def test_calculate_time_range():
    assert calculate_time_range("r24h") == "r86400"
    assert calculate_time_range("r3d") == "r259200"
    assert calculate_time_range("r7d") == "r604800"
    assert calculate_time_range("r1m") == "r2592000"
    assert calculate_time_range("past-24-hours") == "r86400"
    assert calculate_time_range("invalid") == "r604800"
    assert calculate_time_range("") == "r604800"


def test_build_params_encodes_properly():
    qs = build_params(
        keywords="dev jr",
        location="São Paulo",
        time_range="r604800",
        distance="25",
        job_type=["F"],
        place=["2"],
        start=25,
    )
    assert "f_TPR=r604800" in qs
    assert "start=25" in qs
    assert "dev+junior" in qs or "dev%20junior" in qs
    assert "location=S%C3%A3o+Paulo" in qs
    assert "f_JT=F" in qs
    assert "f_WT=2" in qs


def test_build_params_supports_cascade_location_and_advanced_filters():
    qs = build_params(
        keywords="python",
        location="Belo Horizonte, Minas Gerais, Brasil",
        time_range="r24h",
        distance="10",
        job_type=["F"],
        place=["2"],
        experience_level=["1", "2"],
        sort_by="R",
        easy_apply=True,
    )
    assert "sortBy=R" in qs
    assert "f_E=1%2C2" in qs or "f_E=1,2" in qs
    assert "f_AL=true" in qs
    assert "Belo+Horizonte" in qs or "Belo%20Horizonte" in qs
    assert "Minas+Gerais" in qs or "Minas%20Gerais" in qs


def test_get_job_ids_per_page_stops_after_max_retries():
    jobs_state.start()
    try:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.ok = False
        mock_session.get.return_value = mock_response

        with patch("scraper.sleep", return_value=None):
            result = get_job_ids_per_page(
                mock_session, "python", "Brasil", "r604800", "", [], [], start=0
            )

        assert result == []
        assert mock_session.get.call_count == MAX_RETRIES
    finally:
        jobs_state.stop()


def test_get_job_ids_per_page_parses_urns():
    jobs_state.start()
    try:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.text = """
        <ul>
            <li><div data-entity-urn="urn:li:jobPosting:111"></div></li>
            <li><div data-entity-urn="urn:li:jobPosting:222"></div></li>
        </ul>
        """
        mock_session.get.return_value = mock_response

        result = get_job_ids_per_page(
            mock_session, "python", "Brasil", "r604800", "", [], [], start=0
        )
        assert result == ["111", "222"]
    finally:
        jobs_state.stop()


def test_search_state_bounds_logs_and_prevents_double_start():
    state = SearchState()
    assert state.start() is True
    assert state.start() is False

    for i in range(MAX_LOG_ENTRIES + 50):
        state.log(f"msg {i}")

    snap = state.snapshot()
    assert len(snap["log_messages"]) == MAX_LOG_ENTRIES
    state.stop()

