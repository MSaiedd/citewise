"""Document API with server-selected tenant identity and a lightweight browser UI."""

import os
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .answering import extract, generate
from .retrieval import search
from .security import make_auth
from .store import Store


class Document(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    text: str = Field(min_length=1, max_length=50000)

    @field_validator("title", "text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)


def create_app(db_path=None, tokens=None, backend=None, encoder=None):
    auth = make_auth(tokens)
    store = Store(db_path or os.environ.get("DB_PATH", "data/app.db"))
    backend = backend or os.environ.get("ANSWER_BACKEND", "extractive")
    if backend not in {"extractive", "ollama"}:
        raise ValueError("ANSWER_BACKEND must be extractive or ollama")
    if encoder is None and os.environ.get("EMBEDDING_MODEL"):
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(os.environ["EMBEDDING_MODEL"])
    app = FastAPI(title="CiteWise", version="0.1.0")
    web = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(web / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "answer_backend": backend, "dense_search": encoder is not None}

    @app.post("/documents", status_code=201)
    def ingest(body: Document, principal=Depends(auth)):
        return store.put(principal.tenant, body.title, body.text)

    @app.get("/documents")
    def documents(principal=Depends(auth)):
        return store.documents(principal.tenant)

    @app.delete("/documents/{document_id}")
    def delete(document_id: str, principal=Depends(auth)):
        if not store.delete(principal.tenant, document_id):
            raise HTTPException(404, "Document not found")
        return {"deleted": True}

    @app.post("/query")
    def query(body: Question, principal=Depends(auth)):
        started = time.perf_counter()
        hits = search(body.question, store.chunks(principal.tenant), body.top_k, encoder)
        answer, ids = "", []
        if hits:
            try:
                if backend == "ollama":
                    answer, ids = generate(
                        body.question,
                        hits,
                        os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
                        os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
                    )
                else:
                    answer, ids = extract(body.question, hits)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                raise HTTPException(
                    502, "Answer provider failed or returned invalid evidence"
                ) from error
        return {
            "answer": answer or "I could not find supporting evidence in your documents.",
            "abstained": not bool(answer),
            "backend": backend,
            "citations": [{**h.chunk, "score": h.score} for h in hits if h.chunk["id"] in ids],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    return app
