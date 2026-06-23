import pytest
from fastapi.testclient import TestClient
from app import app
from agent.mock import MOCK_SAMPLES


client = TestClient(app)


def test_index():
    r = client.get("/")
    assert r.status_code == 200
    assert "Multi-Agent Code Reviewer" in r.text


def test_review_empty_input():
    r = client.post("/review", data={"code_input": ""}, follow_redirects=True)
    assert r.status_code == 200
    assert "Please paste" in r.text


def test_review_not_code():
    r = client.post("/review", data={"code_input": "This is a long enough plain English sentence with no code."}, follow_redirects=True)
    assert r.status_code == 200
    assert "does not appear" in r.text


def test_review_user_service():
    r = client.post("/review", data={"code_input": MOCK_SAMPLES["user_service"]["code"]}, follow_redirects=True)
    assert r.status_code == 200
    assert "grade-F" in r.text
    assert "Conflict" in r.text


def test_review_clean_api():
    r = client.post("/review", data={"code_input": MOCK_SAMPLES["clean_api"]["code"]}, follow_redirects=True)
    assert r.status_code == 200
    assert "grade-A" in r.text


def test_review_redirect():
    r = client.post("/review", data={"code_input": MOCK_SAMPLES["data_processor"]["code"]}, follow_redirects=False)
    assert r.status_code == 303
    assert "/review/" in r.headers["location"]


def test_review_page_404():
    r = client.get("/review/nonexistent")
    assert r.status_code == 404


def test_compare_page():
    r = client.get("/compare")
    assert r.status_code == 200
    assert "Compare" in r.text


def test_compare_empty_input():
    r = client.post("/compare", data={"code_input": "", "team_a": "security", "team_b": "security"})
    assert r.status_code == 400


def test_compare_submit():
    r = client.post("/compare", data={
        "code_input": MOCK_SAMPLES["user_service"]["code"],
        "team_a": "security,performance,maintainability,bug_detection",
        "team_b": "security,bug_detection",
    })
    assert r.status_code == 200
    assert "Comparison" in r.text or "Compare" in r.text


def test_api_review():
    r = client.post("/api/review", json={"code": MOCK_SAMPLES["user_service"]["code"]})
    assert r.status_code == 200
    data = r.json()
    assert data["review"]["grade"] == "F"
    assert "eval" in data


def test_api_review_empty():
    r = client.post("/api/review", json={"code": ""})
    assert r.status_code == 400


def test_static_css():
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "var(--bg)" in r.text
