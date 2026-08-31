import json

import pytest

from shorts_generator.highlights import (
    chunk_transcript,
    dedupe_highlights,
    get_highlights,
    validate_highlights,
)


def _highlight(start: float, end: float, score: int = 80) -> dict:
    return {
        "title": "Karachi creator insight",
        "start_time": start,
        "end_time": end,
        "score": score,
        "hook_sentence": "Here is the key idea.",
        "virality_reason": "A concise, practical explanation.",
    }


def test_chunks_use_relative_timestamps() -> None:
    transcript = {
        "duration": 3600,
        "segments": [
            {"start": 100.0, "end": 130.0, "text": "first"},
            {"start": 1200.0, "end": 1230.0, "text": "second"},
            {"start": 2400.0, "end": 2430.0, "text": "third"},
        ],
    }
    chunks = chunk_transcript(transcript)
    assert chunks[0]["segments"][1]["start"] == 1200.0
    assert chunks[1]["_offset"] == 1140
    assert chunks[1]["segments"][0]["start"] == 60.0
    assert chunks[2]["_offset"] == 2280
    assert chunks[2]["segments"][0]["start"] == 120.0


def test_first_second_third_chunk_offsets_are_added_exactly_once() -> None:
    transcript = {
        "duration": 3600,
        "segments": [
            {"start": 100.0, "end": 130.0, "text": "first"},
            {"start": 1200.0, "end": 1230.0, "text": "second"},
            {"start": 2400.0, "end": 2430.0, "text": "third"},
        ],
    }

    def llm(prompt: str) -> str:
        if "classify the content type" in prompt:
            return json.dumps({"content_type": "tutorial", "density": "high"})
        if "[1200.0s]" in prompt:
            values = [_highlight(100, 130, 70), _highlight(1200, 1230, 90)]
        elif "[60.0s]" in prompt:
            values = [_highlight(60, 90, 90)]
        else:
            values = [_highlight(120, 150, 80)]
        return json.dumps({"highlights": values})

    result = get_highlights(transcript, num_clips=3, llm_fn=llm)
    ranges = {(item["start_time"], item["end_time"]) for item in result["highlights"]}
    assert ranges == {(100.0, 130.0), (1200.0, 1230.0), (2400.0, 2430.0)}
    assert all(item["end_time"] <= transcript["duration"] for item in result["highlights"])
    assert not any(item["start_time"] == 2340 for item in result["highlights"])


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"highlights": ["wrong"]},
        {"highlights": [_highlight(True, 40)]},
        {"highlights": [_highlight(float("nan"), 40)]},
        {"highlights": [_highlight(40, 20)]},
        {"highlights": [_highlight(0, 19)]},
        {"highlights": [_highlight(0, 181)]},
        {"highlights": [_highlight(80, 120, 101)]},
        {"highlights": [_highlight(80, 120) | {"title": 7}]},
    ],
)
def test_invalid_model_output_is_rejected(payload: object) -> None:
    with pytest.raises(ValueError):
        validate_highlights(payload, 120)


def test_overlap_is_deterministic_and_keeps_higher_score() -> None:
    low = _highlight(30, 90, 70)
    high = _highlight(20, 80, 95)
    assert dedupe_highlights([low, high]) == [high]
