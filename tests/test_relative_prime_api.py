import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


def test_relative_prime_api_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    # No lifespan: API tests must not trigger first-start engine installation.
    client = local_client()
    response = client.post("/api/primes/nth-near", json={
        "start": "1289", "index": 100, "direction": "after",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["value"] == "2039"
    report = (tmp_path / result["output_file"]).read_text()
    assert "2039" in report and "strictly after 1289" in report
    assert "starting integer is excluded" in report
    download = client.get(f'/api/outputs/{result["output_file"]}')
    assert download.status_code == 200
    assert download.text == report

    invalid = client.post("/api/primes/nth-near", json={
        "start": "2", "index": 1, "direction": "before",
    })
    assert invalid.status_code == 422
    assert "does not exist" in invalid.json()["detail"]
    assert len(list(tmp_path.iterdir())) == 1

    for payload in [
        {"start": "13", "index": 0, "direction": "after"},
        {"start": "13", "index": 1, "direction": "invalid"},
        {"start": "not an integer", "index": 1, "direction": "before"},
    ]:
        assert client.post("/api/primes/nth-near", json=payload).status_code == 422


@pytest.mark.parametrize('endpoint,payload,expected', [
    ('batch-check', {'integers': '13, 561, -1'}, [['13', 'Proven prime'], ['561', 'Composite'], ['-1', 'Neither prime nor composite']]),
    ('progression', {'start': '1', 'end': '20', 'modulus': '4', 'residue': '1'}, [['5'], ['13'], ['17']]),
    ('modular', {'modulus': '7', 'value': '2', 'operation': 'roots'}, [['3'], ['4']]),
])
def test_manipulation_api_report_download(endpoint, payload, expected, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, 'OUTPUT_DIR', tmp_path)
    client = local_client()
    response = client.post('/api/primes/' + endpoint, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['rows'] == expected
    report = (tmp_path / result['output_file']).read_text()
    for row in expected:
        assert ' | '.join(row) in report
    download = client.get('/api/outputs/' + result['output_file'])
    assert download.status_code == 200
    assert download.text == report


@pytest.mark.parametrize('endpoint,payload', [
    ('batch-check', {'integers': '2;quit()'}),
    ('progression', {'start': '10', 'end': '1', 'modulus': '4'}),
    ('progression', {'start': '1', 'end': '100', 'modulus': '0'}),
    ('modular', {'modulus': '15', 'value': '2'}),
    ('modular', {'modulus': '7', 'value': '0', 'operation': 'inverse'}),
    ('modular', {'modulus': '7', 'timeout_seconds': 0}),
])
def test_manipulation_api_failure_does_not_save(endpoint, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, 'OUTPUT_DIR', tmp_path)
    response = local_client().post('/api/primes/' + endpoint, json=payload)
    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []

def test_the_gaps_endpoint_reports_merit_for_every_gap(tmp_path, monkeypatch):
    """Merit lived only in the distribution and visual gap tools until 0.9.1.

    It is the normalization that makes gaps at different magnitudes comparable, so the
    main gap page is the one place it was most missed.
    """

    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post(
        "/api/primes/gaps", json={"start": "2", "end": "100", "limit": 100}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["gaps"], "no gaps returned below 100"
    for gap in payload["gaps"]:
        assert float(gap["merit"]) > 0
    assert float(payload["largest"]["merit"]) > 0
    assert "Merit is the gap divided by" in payload["note"]
    report = (tmp_path / payload["output_file"]).read_text(encoding="utf-8")
    assert "merit" in report
