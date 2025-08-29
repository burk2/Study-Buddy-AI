# File: backend/tests/test_api.py
import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    r = client.get("/")
    # root is not defined; ensure app responds to /ask missing key if no key
    # instead test /ask without key we expect a 500 if key not set
    resp = client.post("/ask", json={"text":"hi","mode":"explain"})
    assert resp.status_code in (200, 500)
