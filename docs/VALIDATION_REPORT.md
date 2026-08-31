# Validation report

Prepared for the repaired YouClip AI portfolio repository on August 26, 2026.

## Offline checks executed during repair

- Python compilation passed for `main.py`, `shorts_generator`, `backend_api`,
  and `tests`.
- The upstream provenance verifier passed. Declared repaired pipeline files
  differ from the supplied historical hashes, and every other manifest-covered
  file still matches.
- A direct deterministic execution of the long-video algorithm passed for the
  first, second, and third chunks. The segment at 1,200 seconds remained at
  1,200 seconds and did not become 2,340 seconds.
- Dependency-free frontend HTTP-state tests passed for 401, 413, 429, expiry,
  and safe fallback messages.
- Hosted mode now fails closed when `YOUCLIP_ACCESS_KEY` is missing, short, or
  left as a public placeholder value.

## Complete repository checks

Run these after installing the declared dependencies:

```bash
python -m pip install -r requirements-dev.txt
python scripts/verify-backend-unchanged.py
python -m compileall -q main.py shorts_generator backend_api
python -m pytest -q
```

```bash
cd frontend
npm ci
npm run lint
npm test
npx tsc --noEmit
npm run build
```

The repair workspace did not contain the declared FastAPI, pytest, HTTPX,
Next.js, or ESLint packages and its restricted package proxy did not permit
installing them. Therefore, the full pytest, ESLint, TypeScript, and Next.js
commands were prepared in CI but are not falsely recorded here as locally
executed.

## Mocked test scope

The test suite covers:

- exact first/second/third-chunk timestamp offsets;
- invalid model JSON shapes, types, ranges, scores, and overlap behavior;
- local and hosted access behavior;
- hosted access-key configuration safety;
- canonical YouTube URL acceptance plus SSRF/lookalike rejection;
- empty, incorrect-signature, excessive, and ffprobe-failing uploads;
- queue admission before provider invocation;
- thread-safe job updates and executor shutdown;
- concurrent clip and transcript-cache isolation, transcript removal on expiry,
  and ffmpeg timeouts;
- arbitrary paths, symlinks, and unreferenced media;
- sanitized provider/media-tool failures; and
- retention cleanup with 404 behavior after expiry.

Tests make no live provider requests, public downloads, model downloads, or
media renders.

## Remaining operating constraints

Real processing still requires user-supplied credentials, authorized media,
provider availability, and local media tools where applicable. Job state is
in-memory, restart recovery and cancellation are not implemented, and the
project is intentionally scoped as a local/single-process portfolio
application rather than a distributed public service.
