"""Secure single-process FastAPI adapter for YouClip AI."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend_api.job_store import CapacityError, InMemoryJobStore
from backend_api.security import access_mode, canonical_youtube_url, require_access
from shorts_generator import generate_shorts
from shorts_generator.config import (
    GEMINI_API_KEY,
    LLM_PROVIDER,
    MUAPI_API_KEY,
    OPENAI_API_KEY,
)

LOGGER = logging.getLogger("youclip.api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = (PROJECT_ROOT / ".runtime").resolve()
UPLOAD_DIR = RUNTIME_DIR / "uploads"
JOBS_DIR = RUNTIME_DIR / "jobs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = max(1, int(os.getenv("WEB_MAX_UPLOAD_MB", "500")))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_WORKERS = max(1, int(os.getenv("WEB_MAX_WORKERS", "1")))
MAX_QUEUED_JOBS = max(0, int(os.getenv("WEB_MAX_QUEUED_JOBS", "2")))
RETENTION_SECONDS = max(60, int(os.getenv("WEB_RETENTION_SECONDS", "3600")))
MAX_VIDEO_SECONDS = max(60, int(os.getenv("WEB_MAX_VIDEO_SECONDS", "14400")))
MAX_VIDEO_WIDTH = max(320, int(os.getenv("WEB_MAX_VIDEO_WIDTH", "1920")))
MAX_VIDEO_HEIGHT = max(240, int(os.getenv("WEB_MAX_VIDEO_HEIGHT", "1080")))
FFPROBE_TIMEOUT = max(1, int(os.getenv("WEB_FFPROBE_TIMEOUT", "15")))
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
ALLOWED_CONTENT_TYPES = {
    "application/octet-stream",
    "video/avi",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}


def secret_is_configured(value: str) -> bool:
    cleaned = (value or "").strip().lower()
    return bool(cleaned) and not any(
        token in cleaned
        for token in ("your_", "replace_", "paste_", "example", "changeme")
    )


def parse_origins() -> list[str]:
    raw = os.getenv(
        "WEB_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class JobRequest(BaseModel):
    source_type: Literal["url", "upload"] = "url"
    source: str = Field(min_length=1, max_length=4096)
    mode: Literal["api", "local"] = "api"
    num_clips: int = Field(default=3, ge=1, le=10)
    aspect_ratio: str = Field(default="9:16", pattern=r"^\d{1,3}:\d{1,3}$")
    download_format: Literal["360", "480", "720", "1080"] = "720"
    language: str | None = Field(default=None, max_length=20)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A source URL or upload ID is required.")
        return cleaned

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else ""
        return cleaned or None


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int
    duration_seconds: float


class JobResponse(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int
    message: str
    created_at: str
    updated_at: str
    expires_at: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


store = InMemoryJobStore(
    jobs_root=JOBS_DIR,
    capacity=MAX_WORKERS + MAX_QUEUED_JOBS,
    retention_seconds=RETENTION_SECONDS,
)
_uploads: dict[str, dict[str, str]] = {}
_uploads_lock = threading.RLock()


def cleanup_stale_uploads() -> None:
    cutoff = time.time() - RETENTION_SECONDS
    with _uploads_lock:
        expired = [
            upload_id
            for upload_id, item in _uploads.items()
            if not Path(item["path"]).exists()
            or Path(item["path"]).stat().st_mtime <= cutoff
        ]
        for upload_id in expired:
            item = _uploads.pop(upload_id)
            shutil.rmtree(Path(item["path"]).parent, ignore_errors=True)


class JobRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._stop = threading.Event()
        self._cleaner: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._executor is not None:
                return
            self._stop.clear()
            self._executor = ThreadPoolExecutor(
                max_workers=MAX_WORKERS, thread_name_prefix="youclip-job"
            )
            self._cleaner = threading.Thread(
                target=self._cleanup_loop, name="youclip-cleanup", daemon=True
            )
            self._cleaner.start()

    def _cleanup_loop(self) -> None:
        while not self._stop.wait(min(60, RETENTION_SECONDS)):
            store.cleanup_expired()
            cleanup_stale_uploads()

    def submit(self, *args: Any) -> None:
        self.start()
        assert self._executor is not None
        self._executor.submit(*args)

    def stop(self) -> None:
        with self._lock:
            executor, cleaner = self._executor, self._cleaner
            self._executor = None
            self._cleaner = None
            self._stop.set()
        if cleaner:
            cleaner.join(timeout=2)
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)


runtime = JobRuntime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(
    title="YouClip AI API",
    version="2.0.0",
    description="Bounded local portfolio API for authorized video-to-shorts workflows.",
    contact={"name": "Muhammad Ali Nawaz 2026"},
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-YouClip-Key"],
)


@app.middleware("http")
async def access_gate(request: Request, call_next):
    """Protect every hosted surface; CORS preflight performs no work or reads."""
    if request.method == "OPTIONS":
        return await call_next(request)
    try:
        require_access(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    return await call_next(request)


def _looks_like_video(header: bytes, suffix: str) -> bool:
    if suffix in {".mp4", ".mov", ".m4v"}:
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if suffix in {".mkv", ".webm"}:
        return header.startswith(b"\x1aE\xdf\xa3")
    if suffix == ".avi":
        return (
            len(header) >= 12
            and header[:4] == b"RIFF"
            and header[8:12] == b"AVI "
        )
    return False


def probe_video(path: Path) -> dict[str, float | int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT,
        )
        payload = json.loads(completed.stdout)
        duration = float(payload["format"]["duration"])
        video_streams = [
            stream
            for stream in payload.get("streams", [])
            if stream.get("codec_type") == "video"
        ]
        if not video_streams:
            raise ValueError("No video stream")
        width = max(int(stream.get("width", 0)) for stream in video_streams)
        height = max(int(stream.get("height", 0)) for stream in video_streams)
    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(
            status_code=415, detail="The upload is not a readable video file."
        ) from exc

    if not 0 < duration <= MAX_VIDEO_SECONDS:
        raise HTTPException(
            status_code=413,
            detail=f"Video duration must be no more than {MAX_VIDEO_SECONDS} seconds.",
        )
    fits_landscape = width <= MAX_VIDEO_WIDTH and height <= MAX_VIDEO_HEIGHT
    fits_portrait = width <= MAX_VIDEO_HEIGHT and height <= MAX_VIDEO_WIDTH
    if width <= 0 or height <= 0 or not (fits_landscape or fits_portrait):
        raise HTTPException(
            status_code=413,
            detail=(
                f"Video resolution must be no more than "
                f"{MAX_VIDEO_WIDTH}x{MAX_VIDEO_HEIGHT} in either orientation."
            ),
        )
    return {"duration": duration, "width": width, "height": height}


def _prepare_source(request: JobRequest, owner: str, job_id: str) -> str:
    if request.source_type == "url":
        return request.source
    with _uploads_lock:
        item = _uploads.get(request.source)
        if item is None or item["owner"] != owner:
            raise HTTPException(status_code=404, detail="Uploaded source was not found.")
        source = Path(item["path"])
        destination = (
            Path(store.internal(job_id)["root"]) / "input" / f"source{source.suffix}"
        )
        shutil.move(str(source), destination)
        _uploads.pop(request.source, None)
        shutil.rmtree(source.parent, ignore_errors=True)
    return str(destination.resolve())


def _safe_local_media(path_value: str, job_id: str) -> str:
    job = store.internal(job_id)
    output_root = (Path(job["root"]) / "output").resolve()
    candidate = Path(path_value)
    lexical = PROJECT_ROOT / candidate if not candidate.is_absolute() else candidate
    if lexical.is_symlink() or any(parent.is_symlink() for parent in lexical.parents):
        raise RuntimeError("Pipeline returned an unsafe media file.")
    candidate = lexical.resolve()
    try:
        candidate.relative_to(output_root)
    except ValueError as exc:
        raise RuntimeError(
            "Pipeline returned a path outside the job output directory."
        ) from exc
    if (
        not candidate.exists()
        or not candidate.is_file()
    ):
        raise RuntimeError("Pipeline returned an unsafe media file.")
    return f"/api/media/{job_id}/{candidate.name}"


def make_public_result(result: dict[str, Any], job_id: str) -> dict[str, Any]:
    public = dict(result)
    shorts: list[dict[str, Any]] = []
    for short in result.get("shorts", []):
        item = dict(short)
        clip_url = item.get("clip_url")
        if (
            result.get("mode") == "local"
            and isinstance(clip_url, str)
            and clip_url
        ):
            item["clip_url"] = _safe_local_media(clip_url, job_id)
        if item.get("error"):
            item["error"] = "Clip rendering failed."
        shorts.append(item)
    public["shorts"] = shorts
    public.pop("transcript", None)
    if result.get("mode") == "local":
        public["source_video_url"] = Path(
            str(result.get("source_video_url", ""))
        ).name
    return public


def execute_job(job_id: str, request: JobRequest, source: str) -> None:
    store.update(
        job_id,
        status="processing",
        progress=20,
        message="Processing the authorized source video",
    )
    try:
        output_dir = str(Path(store.internal(job_id)["root"]) / "output")
        result = generate_shorts(
            youtube_url=source,
            num_clips=request.num_clips,
            aspect_ratio=request.aspect_ratio,
            download_format=request.download_format,
            language=request.language,
            mode=request.mode,
            output_dir=output_dir,
        )
        store.update(
            job_id,
            status="completed",
            progress=100,
            message="Shorts generated successfully",
            result=make_public_result(result, job_id),
            error=None,
        )
    except Exception:
        LOGGER.exception("Generation failed for job %s", job_id)
        store.update(
            job_id,
            status="failed",
            progress=100,
            message="Generation failed",
            error=f"Processing failed. Check the server log for job {job_id[:8]}.",
        )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "YouClip AI API",
        "owner": "Muhammad Ali Nawaz 2026",
    }


@app.get("/api/health")
def health(_: str = Depends(require_access)) -> dict[str, Any]:
    store.cleanup_expired()
    return {
        "status": "ok",
        "service": "YouClip AI API",
        "access_mode": access_mode(),
        "max_workers": MAX_WORKERS,
        "max_queued_jobs": MAX_QUEUED_JOBS,
        "max_upload_mb": MAX_UPLOAD_MB,
        "max_video_seconds": MAX_VIDEO_SECONDS,
        "retention_seconds": RETENTION_SECONDS,
        "providers": {
            "muapi_configured": secret_is_configured(MUAPI_API_KEY),
            "openai_configured": secret_is_configured(OPENAI_API_KEY),
            "gemini_configured": secret_is_configured(GEMINI_API_KEY),
            "local_llm_provider": LLM_PROVIDER,
        },
    }


@app.post("/api/uploads", response_model=UploadResponse, status_code=201)
def upload_video(
    file: UploadFile = File(...), owner: str = Depends(require_access)
) -> UploadResponse:
    original_name = Path(file.filename or "video.mp4").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported video file extension.")
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported video content type.")

    upload_id = uuid.uuid4().hex
    upload_root = UPLOAD_DIR / upload_id
    upload_root.mkdir(parents=True, exist_ok=False)
    destination = upload_root / f"source{suffix}"
    total = 0
    try:
        with destination.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {MAX_UPLOAD_MB} MB upload limit.",
                    )
                output.write(chunk)
        if total == 0:
            raise HTTPException(status_code=415, detail="The uploaded file is empty.")
        with destination.open("rb") as source_file:
            header = source_file.read(16)
        if not _looks_like_video(header, suffix):
            raise HTTPException(
                status_code=415,
                detail="File signature does not match its video type.",
            )
        metadata = probe_video(destination)
    except Exception:
        shutil.rmtree(upload_root, ignore_errors=True)
        raise
    finally:
        file.file.close()

    with _uploads_lock:
        _uploads[upload_id] = {"owner": owner, "path": str(destination)}
    return UploadResponse(
        upload_id=upload_id,
        filename=original_name,
        size_bytes=total,
        duration_seconds=float(metadata["duration"]),
    )


@app.post("/api/jobs", response_model=JobResponse, status_code=202)
def create_job(
    request: JobRequest, owner: str = Depends(require_access)
) -> dict[str, Any]:
    store.cleanup_expired()
    if request.source_type == "url":
        try:
            request.source = canonical_youtube_url(request.source)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif request.mode != "local":
        raise HTTPException(status_code=422, detail="Uploaded files require local mode.")

    try:
        job = store.create(request.model_dump(), owner)
    except CapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail="Job capacity is full. Retry after an active job finishes.",
            headers={"Retry-After": "15"},
        ) from exc
    try:
        source = _prepare_source(request, owner, job["id"])
        runtime.submit(execute_job, job["id"], request, source)
    except Exception:
        store.delete(job["id"])
        raise
    return job


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, owner: str = Depends(require_access)) -> dict[str, Any]:
    store.cleanup_expired()
    try:
        return store.get(job_id, owner)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Job expired or was not found."
        ) from exc


@app.get("/api/media/{job_id}/{filename}")
def get_media(
    job_id: str, filename: str, owner: str = Depends(require_access)
) -> FileResponse:
    store.cleanup_expired()
    try:
        job = store.get(job_id, owner)
        internal = store.internal(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Media file not found.") from exc

    safe_name = Path(filename).name
    if filename != safe_name:
        raise HTTPException(status_code=404, detail="Media file not found.")
    output_root = (Path(internal["root"]) / "output").resolve()
    lexical_path = output_root / safe_name
    path = lexical_path.resolve()
    referenced = {
        item.get("clip_url")
        for item in (job.get("result") or {}).get("shorts", [])
        if isinstance(item, dict)
    }
    expected_url = f"/api/media/{job_id}/{safe_name}"
    if (
        path.parent != output_root
        or not path.exists()
        or not path.is_file()
        or lexical_path.is_symlink()
        or expected_url not in referenced
    ):
        raise HTTPException(status_code=404, detail="Media file not found.")
    return FileResponse(path, media_type="video/mp4", filename=safe_name)
