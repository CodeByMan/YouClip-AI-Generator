from __future__ import annotations

import json
import subprocess
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend_api.app as api
from backend_api.job_store import InMemoryJobStore, utc_now
from backend_api.security import canonical_youtube_url


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setenv("WEB_ACCESS_MODE", "local")
    api.store.clear()
    with api._uploads_lock:
        api._uploads.clear()
    yield
    api.store.clear()
    api.runtime.stop()


@pytest.fixture
def client() -> TestClient:
    with TestClient(api.app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client


def job_payload(source: str = "https://www.youtube.com/watch?v=abc_123") -> dict:
    return {
        "source_type": "url",
        "source": source,
        "mode": "api",
        "num_clips": 1,
        "aspect_ratio": "9:16",
        "download_format": "360",
        "language": "en",
    }


def test_health_and_explicit_local_mode(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["access_mode"] == "local"
    assert response.json()["max_upload_mb"] <= 500


def test_local_mode_rejects_non_loopback_client() -> None:
    with TestClient(api.app, client=("203.0.113.10", 50000)) as remote_client:
        assert remote_client.get("/api/health").status_code == 403


def test_hosted_mode_requires_constant_access_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("WEB_ACCESS_MODE", "hosted")
    monkeypatch.setenv("YOUCLIP_ACCESS_KEY", "correct-key-with-at-least-32-characters")
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-YouClip-Key": "wrong"}).status_code == 401
    assert (
        client.get(
            "/api/health",
            headers={"X-YouClip-Key": "correct-key-with-at-least-32-characters"},
        ).status_code
        == 200
    )
    assert client.get("/").status_code == 401


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "",
        "short-key",
        "replace_with_a_long_random_value_for_hosted_mode",
        "example-hosted-key-with-enough-length",
        "changeme-hosted-key-with-enough-length",
    ],
)
def test_hosted_mode_rejects_unsafe_configured_access_keys(
    client: TestClient, monkeypatch, unsafe_key: str
) -> None:
    monkeypatch.setenv("WEB_ACCESS_MODE", "hosted")
    monkeypatch.setenv("YOUCLIP_ACCESS_KEY", unsafe_key)

    response = client.get("/api/health", headers={"X-YouClip-Key": unsafe_key})

    assert response.status_code == 500
    assert response.json()["detail"] == "Hosted access key is not safely configured."


@pytest.mark.parametrize(
    "value",
    [
        "http://www.youtube.com/watch?v=abc",
        "https://youtube.com.evil.example/watch?v=abc",
        "https://evil.example/?next=youtube.com",
        "https://127.0.0.1/watch?v=abc",
        "https://[::1]/watch?v=abc",
        "https://user@youtube.com/watch?v=abc",
        "https://youtube.com:8443/watch?v=abc",
        "file:///tmp/video.mp4",
    ],
)
def test_url_policy_rejects_ssrf_and_lookalikes(value: str) -> None:
    with pytest.raises(ValueError):
        canonical_youtube_url(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://youtube.com/watch?v=abc_123",
        "https://www.youtube.com/shorts/abc-123",
        "https://m.youtube.com/live/abc123",
        "https://youtu.be/abc123?t=2",
    ],
)
def test_url_policy_accepts_supported_youtube_shapes(value: str) -> None:
    assert canonical_youtube_url(value).startswith("https://")


def test_job_endpoint_rejects_arbitrary_url(client: TestClient) -> None:
    response = client.post("/api/jobs", json=job_payload("https://example.com/video"))
    assert response.status_code == 422


def test_upload_requires_local_mode(client: TestClient) -> None:
    payload = job_payload()
    payload.update({"source_type": "upload", "source": "missing", "mode": "api"})
    assert client.post("/api/jobs", json=payload).status_code == 422


def test_zero_byte_and_wrong_signature_uploads_are_rejected(client: TestClient) -> None:
    empty = client.post(
        "/api/uploads", files={"file": ("empty.mp4", b"", "video/mp4")}
    )
    wrong = client.post(
        "/api/uploads", files={"file": ("fake.mp4", b"not-a-video", "video/mp4")}
    )
    assert empty.status_code == 415
    assert wrong.status_code == 415


def test_valid_signature_is_probed(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "probe_video",
        lambda _path: {"duration": 30.0, "width": 640, "height": 360},
    )
    response = client.post(
        "/api/uploads",
        files={"file": ("sample.mp4", b"\x00\x00\x00\x18ftypisomdata", "video/mp4")},
    )
    assert response.status_code == 201
    assert response.json()["duration_seconds"] == 30


def test_oversize_upload_returns_413(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 8)
    response = client.post(
        "/api/uploads",
        files={"file": ("large.mp4", b"\x00\x00\x00\x18ftypisomdata", "video/mp4")},
    )
    assert response.status_code == 413


def test_ffprobe_failure_and_media_limits(monkeypatch, tmp_path) -> None:
    sample = tmp_path / "sample.mp4"
    sample.write_bytes(b"video")

    def failed(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(api.subprocess, "run", failed)
    with pytest.raises(api.HTTPException) as error:
        api.probe_video(sample)
    assert error.value.status_code == 415

    payload = {
        "format": {"duration": str(api.MAX_VIDEO_SECONDS + 1)},
        "streams": [{"codec_type": "video", "width": 640, "height": 360}],
    }
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(payload), ""
        ),
    )
    with pytest.raises(api.HTTPException) as duration_error:
        api.probe_video(sample)
    assert duration_error.value.status_code == 413

    payload = {
        "format": {"duration": "30"},
        "streams": [
            {
                "codec_type": "video",
                "width": api.MAX_VIDEO_WIDTH + 1000,
                "height": api.MAX_VIDEO_HEIGHT + 1000,
            }
        ],
    }
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps(payload), ""
        ),
    )
    with pytest.raises(api.HTTPException) as resolution_error:
        api.probe_video(sample)
    assert resolution_error.value.status_code == 413


def test_mocked_workflow_sanitizes_errors_and_does_not_call_live_provider(
    client: TestClient, monkeypatch
) -> None:
    def run_now(function, *args):
        function(*args)

    def fail_pipeline(**_kwargs):
        raise RuntimeError("/private/path provider-secret raw error")

    monkeypatch.setattr(api.runtime, "submit", run_now)
    monkeypatch.setattr(api, "generate_shorts", fail_pipeline)
    created = client.post("/api/jobs", json=job_payload())
    assert created.status_code == 202
    result = client.get(f"/api/jobs/{created.json()['id']}").json()
    assert result["status"] == "failed"
    assert "private" not in result["error"]
    assert "provider-secret" not in result["error"]


def test_queue_bound_returns_429_before_provider_invocation(
    client: TestClient, monkeypatch
) -> None:
    submitted = []
    monkeypatch.setattr(api.runtime, "submit", lambda *args: submitted.append(args))
    for index in range(api.store.capacity):
        response = client.post(
            "/api/jobs",
            json=job_payload(f"https://youtu.be/video{index}"),
        )
        assert response.status_code == 202
    rejected = client.post(
        "/api/jobs", json=job_payload("https://youtu.be/one_more")
    )
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "15"
    assert len(submitted) == api.store.capacity


def test_arbitrary_and_symlink_result_paths_are_rejected(tmp_path) -> None:
    job = api.store.create(job_payload(), "local")
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video")
    with pytest.raises(RuntimeError):
        api.make_public_result(
            {"mode": "local", "shorts": [{"clip_url": str(outside)}]}, job["id"]
        )

    output = Path(api.store.internal(job["id"])["root"]) / "output"
    link = output / "link.mp4"
    link.symlink_to(outside)
    with pytest.raises(RuntimeError):
        api.make_public_result(
            {"mode": "local", "shorts": [{"clip_url": str(link)}]}, job["id"]
        )


def test_expiry_removes_files_and_record(tmp_path) -> None:
    expiring = InMemoryJobStore(tmp_path / "jobs", capacity=1, retention_seconds=1)
    job = expiring.create(job_payload(), "owner")
    root = Path(expiring.internal(job["id"])["root"])
    (root / "output" / "clip.mp4").write_bytes(b"video")
    expiring.update(job["id"], status="completed")
    removed = expiring.cleanup_expired(utc_now() + timedelta(seconds=2))
    assert removed == [job["id"]]
    assert not root.exists()
    with pytest.raises(KeyError):
        expiring.get(job["id"], "owner")


def test_expired_media_returns_404(client: TestClient) -> None:
    job = api.store.create(job_payload(), "local")
    root = Path(api.store.internal(job["id"])["root"])
    clip = root / "output" / "clip.mp4"
    clip.write_bytes(b"video")
    url = f"/api/media/{job['id']}/clip.mp4"
    api.store.update(
        job["id"],
        status="completed",
        result={"shorts": [{"clip_url": url}]},
    )
    api.store.update(
        job["id"], expires_at=(utc_now() - timedelta(seconds=1)).isoformat()
    )
    assert client.get(url).status_code == 404
    assert not root.exists()


def test_job_updates_are_thread_safe(tmp_path) -> None:
    thread_store = InMemoryJobStore(tmp_path / "thread-jobs", 1, 60)
    job = thread_store.create(job_payload(), "owner")
    threads = [
        threading.Thread(target=thread_store.update, args=(job["id"],), kwargs={"progress": value})
        for value in range(25)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert 0 <= thread_store.get(job["id"], "owner")["progress"] < 25


def test_runtime_executor_shuts_down() -> None:
    runtime = api.JobRuntime()
    runtime.start()
    assert runtime._executor is not None
    runtime.stop()
    assert runtime._executor is None
