"""Private file storage behind an adapter.

- local: files under <file_storage_dir>/<organisation_id>/<uuid>, outside any web root.
- database: file contents in the RLS-protected file_blobs table. For hosts without persistent disk
  (free tiers and serverless). Adequate for Release 1 limits (5 MB per file); move to S3-compatible
  object storage at paid hosting.
Files are only ever served through an authorised, tenant-checked API endpoint.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings


class Storage(Protocol):
    def put(self, organisation_id: uuid.UUID, data: bytes) -> tuple[str, str]: ...
    def get(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or get_settings().file_storage_dir).resolve()

    def put(self, organisation_id: uuid.UUID, data: bytes) -> tuple[str, str]:
        key = f"{organisation_id}/{uuid.uuid4()}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        return key, hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path


class DatabaseStorage:
    def __init__(self, db: Session):
        self.db = db

    def put(self, organisation_id: uuid.UUID, data: bytes) -> tuple[str, str]:
        from app.models import FileBlob

        key = f"{organisation_id}/{uuid.uuid4()}"
        self.db.add(FileBlob(organisation_id=organisation_id, storage_key=key, data=data))
        self.db.flush()
        return key, hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        from app.models import FileBlob

        blob = self.db.scalar(select(FileBlob).where(FileBlob.storage_key == key))
        if blob is None:
            raise FileNotFoundError(key)
        return blob.data


def get_storage(db: Session | None = None) -> Storage:
    backend = get_settings().storage_backend
    if backend == "local":
        return LocalStorage()
    if backend == "database":
        if db is None:
            raise RuntimeError("Database storage needs a session")
        return DatabaseStorage(db)
    raise RuntimeError(f"Unknown storage backend '{backend}'")
