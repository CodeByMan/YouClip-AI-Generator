"""Verify historical upstream hashes and the declared modification set."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "original-backend-sha256.txt"
DECLARED_MODIFICATIONS = {
    "shorts_generator/downloader.py",
    "shorts_generator/highlights.py",
    "shorts_generator/pipeline.py",
    "shorts_generator/local/clipper.py",
    "shorts_generator/local/downloader.py",
    "shorts_generator/local/transcriber.py",
}

failures: list[str] = []
for line in MANIFEST.read_text(encoding="utf-8").splitlines():
    expected, relative = line.split(maxsplit=1)
    relative = relative.lstrip("* ")
    path = ROOT / relative
    if not path.exists():
        failures.append(f"MISSING: {relative}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if relative in DECLARED_MODIFICATIONS:
        if actual == expected:
            failures.append(f"DECLARED BUT UNCHANGED: {relative}")
    elif actual != expected:
        failures.append(f"UNDECLARED CHANGE: {relative}")

if failures:
    print("Upstream provenance verification failed:")
    for failure in failures:
        print(f" - {failure}")
    raise SystemExit(1)

print("PASS: upstream snapshot and declared modification set are consistent.")
