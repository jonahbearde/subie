"""Cue text cleaning, asserted through the single agreed seam.

Music and markers, whitespace and casing, fillers, and the phantom-phrase blocklist:
each fixture is a Transcript on disk and the exact Sidecar bytes it must produce. The
same run is also checked against the policy's external limits, Cue by Cue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subie.cli import run
from subie.exit_codes import EXIT_OK
from subie.guard import (
    HIGH_NO_SPEECH_PROB,
    LOW_AVG_LOGPROB,
    PHANTOM_PHRASES,
    SENTENCE_FINAL_IMPOSSIBILITIES,
)
from subie.transcript import Segment, Transcript, Word
from tests.fakes import FakeTranscriber, FakeTranscriberFactory, make_deps
from tests.golden import (
    assert_readability,
    assert_sidecar_bytes,
    fixture_cases,
    run_fixture,
)
from tests.wav import write_wav

FIXTURES = Path(__file__).parent / "fixtures" / "text"
POLICY = Path(__file__).parent.parent / "docs" / "subtitle-policy.md"

#: Every behaviour the ticket calls out has a fixture named here.
BEHAVIOURS = {
    "music-notes-dropped",
    "bracketed-marker-kept",
    "marker-stripped-from-speech",
    "whitespace-and-punctuation",
    "fillers-preserved",
    "phantom-phrase-dropped-unless-confident",
    "mixed-rules-one-cue",
    "numeral-start-left-alone",
    "normalization-splits-oversized-cue",
}


def test_every_behaviour_has_a_fixture():
    present = {path.stem for path in fixture_cases(FIXTURES)}
    assert present >= BEHAVIOURS


@pytest.mark.parametrize("transcript_path", fixture_cases(FIXTURES), ids=lambda path: path.stem)
def test_golden_sidecar(transcript_path, tmp_path, capsys):
    actual, transcript = run_fixture(transcript_path, tmp_path, capsys)

    expected = transcript_path.with_suffix(".srt").read_bytes()
    assert_sidecar_bytes(actual, expected, label=transcript_path.stem)
    assert_readability(actual, transcript, label=transcript_path.stem)


def test_a_transcript_of_only_music_produces_no_sidecar(tmp_path, capsys):
    video = tmp_path / "music.wav"
    write_wav(video)
    music = Transcript(
        segments=(
            Segment(
                start=0.0,
                end=1.2,
                text="♪ ♪ ♪",
                words=(
                    Word(start=0.0, end=0.4, text="♪"),
                    Word(start=0.4, end=0.8, text="♪"),
                    Word(start=0.8, end=1.2, text="♪"),
                ),
            ),
        )
    )
    deps = make_deps(transcriber_factory=FakeTranscriberFactory(FakeTranscriber(music)))

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "no speech detected" in captured.err
    assert not (tmp_path / "music.srt").exists()


def test_the_blocklist_and_its_thresholds_are_documented():
    policy = POLICY.read_text(encoding="utf-8")

    for phrase in PHANTOM_PHRASES:
        assert phrase in policy, f"the policy does not document {phrase!r}"
    for name in ("PHANTOM_PHRASES", "LOW_AVG_LOGPROB", "HIGH_NO_SPEECH_PROB"):
        assert name in policy, f"the policy does not name {name}"
    assert str(LOW_AVG_LOGPROB) in policy
    assert str(HIGH_NO_SPEECH_PROB) in policy


def test_the_sentence_final_impossibilities_are_documented():
    policy = POLICY.read_text(encoding="utf-8")

    assert "SENTENCE_FINAL_IMPOSSIBILITIES" in policy
    for word in SENTENCE_FINAL_IMPOSSIBILITIES:
        assert f"`{word}`" in policy, f"the policy does not document {word!r}"
