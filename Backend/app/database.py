"""Storage layer — SQLite.

User accounts, one-time passwords and analysis records are persisted in a local
**SQLite** database (`storage/bhudarpan.db`), so registrations survive restarts and
can be inspected with any SQLite tool. A tiny Mongo-like interface (insert_one,
find_one, find, update_one, delete_one, count_documents) is exposed so the rest of
the app is storage-agnostic.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional

from .config import settings

_SAFE = re.compile(r"^[a-z_]+$")


class _SqliteCollection:
    """A Mongo-like collection backed by one SQLite table
    (columns: id PK, email, owner, data=JSON document)."""

    def __init__(self, store: "_SqliteStore", name: str) -> None:
        self._store = store
        self._name = name

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    @staticmethod
    def _key(doc: dict) -> str:
        return doc.get("id") or doc.get("email") or uuid.uuid4().hex

    def _rows(self, query: dict) -> list[dict]:
        where, params = [], []
        for col in ("id", "email", "owner"):     # use indexed columns when possible
            if col in query:
                where.append(f"{col}=?")
                params.append(query[col])
        sql = f"SELECT data FROM {self._name}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        # A single sqlite3 connection is shared across FastAPI worker threads, and its
        # cursor state is not safe for concurrent use — two threads reading at once can
        # yield partial/empty rows. Serialize reads under the same lock that guards
        # writes (RLock, so nested read-inside-write in update/delete is fine).
        with self._store.lock:
            fetched = self._store.conn.execute(sql, params).fetchall()
        out = []
        for r in fetched:
            raw = r[0]
            if not raw:                            # defensive: skip a blank/NULL row
                continue
            try:
                out.append(json.loads(raw))
            except (ValueError, TypeError):
                continue
        return out

    def insert_one(self, doc: dict) -> None:
        with self._store.lock:
            key = self._key(doc)
            self._store.conn.execute(
                f"INSERT OR REPLACE INTO {self._name} (id, email, owner, data) VALUES (?,?,?,?)",
                (key, doc.get("email"), doc.get("owner"), json.dumps(doc, default=str)),
            )
            self._store.conn.commit()

    def find_one(self, query: dict) -> Optional[dict]:
        for doc in self._rows(query):
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query: Optional[dict] = None) -> list[dict]:
        query = query or {}
        return [dict(d) for d in self._rows(query) if self._matches(d, query)]

    def update_one(self, query: dict, update: dict) -> None:
        with self._store.lock:
            for doc in self._rows(query):
                if self._matches(doc, query):
                    doc.update(update.get("$set", {}))
                    self._store.conn.execute(
                        f"UPDATE {self._name} SET email=?, owner=?, data=? WHERE id=?",
                        (doc.get("email"), doc.get("owner"), json.dumps(doc, default=str), self._key(doc)),
                    )
                    self._store.conn.commit()
                    return

    def delete_one(self, query: dict) -> int:
        with self._store.lock:
            for doc in self._rows(query):
                if self._matches(doc, query):
                    self._store.conn.execute(
                        f"DELETE FROM {self._name} WHERE id=?", (self._key(doc),))
                    self._store.conn.commit()
                    return 1
        return 0

    def count_documents(self, query: Optional[dict] = None) -> int:
        return len(self.find(query or {}))


class _SqliteStore:
    def __init__(self, path) -> None:
        self.path = path
        self.lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.commit()

    def collection(self, name: str) -> _SqliteCollection:
        if not _SAFE.match(name):
            raise ValueError(f"unsafe collection name: {name!r}")
        with self.lock:
            self.conn.execute(
                f"CREATE TABLE IF NOT EXISTS {name} "
                f"(id TEXT PRIMARY KEY, email TEXT, owner TEXT, data TEXT NOT NULL)")
            self.conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{name}_email ON {name}(email)")
            self.conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{name}_owner ON {name}(owner)")
            self.conn.commit()
        return _SqliteCollection(self, name)


class Database:
    def __init__(self) -> None:
        self.backend = "sqlite"
        self.db_path = settings.storage_dir / "bhudarpan.db"
        self._store = _SqliteStore(self.db_path)
        self._collections: dict[str, Any] = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = self._store.collection(name)
        return self._collections[name]

    @property
    def users(self):
        return self.collection("users")

    @property
    def analyses(self):
        return self.collection("analyses")

    @property
    def changes(self):
        return self.collection("changes")

    @property
    def disasters(self):
        return self.collection("disasters")

    @property
    def otps(self):
        return self.collection("otps")

    def info(self) -> dict:
        return {
            "backend": "sqlite",
            "path": str(self.db_path),
            "db_name": settings.db_name,
            "users": self.users.count_documents({}),
        }


db = Database()
