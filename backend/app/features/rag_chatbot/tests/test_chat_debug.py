import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(autouse=True, scope="session")
def _env_openai_key():
    # Fake value to pass status checks; we won't call OpenAI in this test
    os.environ.setdefault("OPENAI_API_KEY", "test_key")
    yield

client = TestClient(app)

def test_retrieve_endpoint_exists():
    r = client.get("/api/rag/chat/_retrieve", params={"q": "test", "top_k": 2})
    # 200 even if no index; 'trace' should exist
    assert r.status_code == 200
    data = r.json()
    assert "trace" in data
    assert "count" in data

def test_status_endpoint():
    r = client.get("/api/rag/chat/status")
    assert r.status_code == 200
    data = r.json()
    assert "llm" in data
    assert "retrieval" in data
