from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_rejects_empty_message():
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_rejects_oversized_message():
    response = client.post("/api/chat", json={"message": "x" * 5001})
    assert response.status_code == 422


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "LearnWise" in response.text
