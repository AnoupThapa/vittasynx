"""Private file storage behind an adapter. The local backend writes outside any web root under
<file_storage_dir>/<organisation_id>/<uuid>. An S3-compatible backend can replace it (Phase 3 decision).
Files are only ever served through an authorised, tenant-checked API endpoint."""
import hashlib
import uuid
from pathlib import Path

from app.config import get_settings


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


def get_storage() -> LocalStorage:
    return LocalStorage()
