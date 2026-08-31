"""Thread-safe, bounded, expiring job storage for the single-process API."""

from __future__ import annotations

import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class CapacityError(RuntimeError):
    """Raised when every active and queued job slot is occupied."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()


class InMemoryJobStore:
    def __init__(self, jobs_root: Path, capacity: int, retention_seconds: int) -> None:
        self.jobs_root = jobs_root.resolve()
        self.capacity = max(1, capacity)
        self.retention = timedelta(seconds=max(1, retention_seconds))
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, request_data: dict[str, Any], owner: str) -> dict[str, Any]:
        with self._lock:
            occupied = sum(
                job["status"] in {"queued", "processing"} for job in self._jobs.values()
            )
            if occupied >= self.capacity:
                raise CapacityError("Job capacity is full.")

            job_id = uuid.uuid4().hex
            now = utc_now()
            root = (self.jobs_root / job_id).resolve()
            (root / "input").mkdir(parents=True, exist_ok=False)
            (root / "output").mkdir()
            job = {
                "id": job_id,
                "owner": owner,
                "status": "queued",
                "progress": 5,
                "message": "Job queued",
                "created_at": iso(now),
                "updated_at": iso(now),
                "expires_at": iso(now + self.retention),
                "request": request_data,
                "result": None,
                "error": None,
                "root": str(root),
            }
            self._jobs[job_id] = job
            return self._public(job)

    @staticmethod
    def _public(job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if key not in {"owner", "root"}}

    def get(self, job_id: str, owner: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["owner"] != owner:
                raise KeyError(job_id)
            return self._public(job)

    def internal(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs[job_id]
            return dict(job)

    def update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(changes)
            now = utc_now()
            job["updated_at"] = iso(now)
            if changes.get("status") in {"completed", "failed"}:
                job["expires_at"] = iso(now + self.retention)

    def delete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job:
            shutil.rmtree(job["root"], ignore_errors=True)

    def cleanup_expired(self, now: datetime | None = None) -> list[str]:
        current = now or utc_now()
        with self._lock:
            expired = [
                job_id
                for job_id, job in self._jobs.items()
                if job["status"] not in {"queued", "processing"}
                and datetime.fromisoformat(job["expires_at"]) <= current
            ]
        for job_id in expired:
            self.delete(job_id)
        return expired

    def clear(self) -> None:
        with self._lock:
            job_ids = list(self._jobs)
        for job_id in job_ids:
            self.delete(job_id)
