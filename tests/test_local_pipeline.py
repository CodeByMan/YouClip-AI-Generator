from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from backend_api.job_store import InMemoryJobStore, utc_now
from shorts_generator.local import clipper
from shorts_generator.local import transcriber
from shorts_generator.pipeline import MAX_VIDEO_SECONDS, _validate_transcript
import pytest


def test_concurrent_jobs_use_isolated_unique_output_names(tmp_path, monkeypatch) -> None:
    def fake_crop(_source, _start, _end, _ratio, output) -> str:
        Path(output).write_bytes(b"video")
        return output

    monkeypatch.setattr(clipper, "crop_clip_local", fake_crop)
    highlight = [{"title": "One", "start_time": 0, "end_time": 30, "score": 90}]
    first_dir = tmp_path / "job-one"
    second_dir = tmp_path / "job-two"
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            clipper.crop_highlights_local, "source.mp4", highlight, "9:16", str(first_dir)
        )
        second_future = executor.submit(
            clipper.crop_highlights_local, "source.mp4", highlight, "9:16", str(second_dir)
        )
        first = first_future.result()
        second = second_future.result()

    first_path = Path(first[0]["clip_url"])
    second_path = Path(second[0]["clip_url"])
    assert first_path.parent == first_dir
    assert second_path.parent == second_dir
    assert first_path.name != second_path.name
    assert first_path.exists() and second_path.exists()


def test_concurrent_jobs_use_isolated_transcript_caches(tmp_path) -> None:
    transcript = {
        "duration": 2.0,
        "segments": [{"start": 0.0, "end": 2.0, "text": "job transcript"}],
    }
    first_dir = tmp_path / "job-one" / "output"
    second_dir = tmp_path / "job-two" / "output"
    source_name = "source.mp4"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            transcriber._write_srt_cache, source_name, transcript, str(first_dir)
        )
        second_future = executor.submit(
            transcriber._write_srt_cache, source_name, transcript, str(second_dir)
        )
        first_cache = first_future.result()
        second_cache = second_future.result()

    assert first_cache == first_dir / "source.srt"
    assert second_cache == second_dir / "source.srt"
    assert first_cache != second_cache
    assert first_cache.exists() and second_cache.exists()


def test_job_expiry_removes_private_transcript_cache(tmp_path) -> None:
    expiring = InMemoryJobStore(
        tmp_path / "jobs", capacity=1, retention_seconds=1
    )
    job = expiring.create({"mode": "local"}, "owner")
    root = Path(expiring.internal(job["id"])["root"])
    transcript_path = transcriber._write_srt_cache(
        "source.mp4",
        {
            "duration": 2.0,
            "segments": [{"start": 0.0, "end": 2.0, "text": "private"}],
        },
        str(root / "output"),
    )
    assert transcript_path.exists()

    expiring.update(job["id"], status="completed")
    removed = expiring.cleanup_expired(utc_now() + timedelta(seconds=2))

    assert removed == [job["id"]]
    assert not transcript_path.exists()
    assert not root.exists()


def test_ffmpeg_cut_has_a_timeout(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(clipper.subprocess, "run", fake_run)
    clipper._cut_subclip("source.mp4", 0, 30, "out.mp4")
    assert captured["timeout"] == 300


def test_pipeline_rejects_excessive_or_invalid_duration() -> None:
    with pytest.raises(RuntimeError):
        _validate_transcript(
            {"duration": MAX_VIDEO_SECONDS + 1, "segments": [{"text": "speech"}]}
        )
    with pytest.raises(RuntimeError):
        _validate_transcript({"duration": 30, "segments": []})
