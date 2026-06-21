import os

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_api.db")

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_endpoint_routes_policy_question():
    resp = client.post("/api/chat", json={"message": "What is the leave policy?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent"] == "knowledge_agent"


def test_chat_endpoint_routes_shipment_question():
    resp = client.post("/api/chat", json={"message": "Show delayed shipments last month"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent"] == "sql_agent"
    assert body["sql"].upper().startswith("SELECT")


def test_chat_endpoint_rejects_empty_message():
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


def test_upload_endpoint_ingests_text_file(tmp_path):
    file_path = tmp_path / "policy.txt"
    file_path.write_text("Employees get 20 days of paid leave per year.")

    with open(file_path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("policy.txt", f, "text/plain")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["doc_id"] == "policy"
    assert body["chunk_count"] >= 1
