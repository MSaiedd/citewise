import httpx
import pytest
from fastapi.testclient import TestClient

from citewise.api import create_app
from citewise.retrieval import chunk_text, search

TOKENS = {
    "tenant-a-token-000000000000000": {"tenant": "a", "user": "alice"},
    "tenant-b-token-000000000000000": {"tenant": "b", "user": "bob"},
}
A = {"Authorization": "Bearer " + list(TOKENS)[0]}
B = {"Authorization": "Bearer " + list(TOKENS)[1]}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "test.db", TOKENS))


def test_citations_isolation_and_replacement(client):
    created = client.post(
        "/documents",
        headers=A,
        json={"title": "Policy", "text": "Refunds take five business days."},
    ).json()
    result = client.post("/query", headers=A, json={"question": "How long do refunds take?"}).json()
    assert result["citations"][0]["document_id"] == created["id"]
    assert "five" in result["answer"]
    assert client.get("/documents", headers=B).json() == []
    assert client.post("/query", headers=B, json={"question": "refunds"}).json()["abstained"]
    assert client.delete("/documents/" + created["id"], headers=B).status_code == 404
    replacement = client.post(
        "/documents", headers=A, json={"title": "Policy", "text": "Refunds take ten days."}
    ).json()
    assert replacement["id"] == created["id"]
    assert len(client.get("/documents", headers=A).json()) == 1
    assert "ten" in client.post("/query", headers=A, json={"question": "refunds"}).json()["answer"]
    assert client.delete("/documents/" + created["id"], headers=A).status_code == 200
    assert client.post("/query", headers=A, json={"question": "refunds"}).json()["abstained"]


def test_auth_validation_and_no_evidence(client):
    assert client.get("/documents").status_code == 401
    assert client.post("/documents", headers=A, json={"title": " ", "text": "x"}).status_code == 422
    client.post(
        "/documents", headers=A, json={"title": "Policy", "text": "Refunds take five days."}
    )
    assert client.post("/query", headers=A, json={"question": "quantum mechanics"}).json()[
        "abstained"
    ]
    assert (
        client.post("/query", headers=A, json={"question": "refunds", "top_k": 100}).status_code
        == 422
    )


def test_persistence(tmp_path):
    path = tmp_path / "persistent.db"
    TestClient(create_app(path, TOKENS)).post(
        "/documents", headers=A, json={"title": "Persistent", "text": "Saved across restart"}
    )
    assert len(TestClient(create_app(path, TOKENS)).get("/documents", headers=A).json()) == 1


def test_chunks_and_arabic():
    text = "أهلاً\nالاسترجاع خلال ثلاثين يوماً.\n" * 80
    parts = list(chunk_text(text))
    assert parts[0]["line_start"] == 1
    assert len(parts) > 1
    chunks = [{**p, "id": str(i)} for i, p in enumerate(parts)]
    assert search("الاسترجاع", chunks)
    with pytest.raises(ValueError):
        list(chunk_text("x", size=1, overlap=2))


def test_provider_failure_is_explicit(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("citewise.answering.httpx.post", fail)
    client = TestClient(create_app(tmp_path / "test.db", TOKENS, backend="ollama"))
    client.post(
        "/documents", headers=A, json={"title": "Policy", "text": "Refunds take five days."}
    )
    assert client.post("/query", headers=A, json={"question": "refunds"}).status_code == 502


def test_model_cannot_invent_citations(monkeypatch):
    from citewise.answering import generate
    from citewise.retrieval import Hit

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": '{"answer":"invented", "citation_ids":["foreign"]}'}}

    monkeypatch.setattr("citewise.answering.httpx.post", lambda *a, **kw: FakeResponse())
    with pytest.raises(ValueError):
        generate(
            "question", [Hit({"id": "real", "text": "evidence"}, 1)], "http://localhost", "test"
        )
