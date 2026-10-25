"""Transactional document replacement and tenant-filtered SQLite persistence."""

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .retrieval import chunk_text


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL,
                    UNIQUE(tenant, title)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id)
                    ON DELETE CASCADE, tenant TEXT NOT NULL, text TEXT NOT NULL,
                    line_start INTEGER NOT NULL, line_end INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_tenant ON chunks(tenant);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, tenant, title, text):
        with self.connect() as db:
            # Serialize replacement: readers see either the old or the new complete document.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM documents WHERE tenant=? AND title=?", (tenant, title)
            ).fetchone()
            document_id = row["id"] if row else uuid.uuid4().hex
            if row:
                db.execute(
                    "DELETE FROM chunks WHERE document_id=? AND tenant=?", (document_id, tenant)
                )
            else:
                db.execute("INSERT INTO documents VALUES (?,?,?)", (document_id, tenant, title))
            parts = list(chunk_text(text))
            for part in parts:
                db.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (
                        uuid.uuid4().hex,
                        document_id,
                        tenant,
                        part["text"],
                        part["line_start"],
                        part["line_end"],
                    ),
                )
            return {"id": document_id, "title": title, "chunks": len(parts)}

    def documents(self, tenant):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,title FROM documents WHERE tenant=? ORDER BY title", (tenant,)
                )
            ]

    def chunks(self, tenant):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    """
                SELECT c.*, d.title FROM chunks c JOIN documents d ON c.document_id=d.id
                WHERE c.tenant=? AND d.tenant=? ORDER BY c.id
            """,
                    (tenant, tenant),
                )
            ]

    def delete(self, tenant, document_id):
        with self.connect() as db:
            return (
                db.execute(
                    "DELETE FROM documents WHERE id=? AND tenant=?", (document_id, tenant)
                ).rowcount
                > 0
            )
