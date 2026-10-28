"""Readability segmentation, asserted through the single agreed seam.

Each fixture is a Transcript on disk and the exact Sidecar bytes it must produce. The
same run is also checked against the policy's external limits, Cue by Cue.
"""

from __future__ import annotations

import pytest

from tests.golden import (
    assert_readability,
    assert_sidecar_bytes,
    fixture_cases,
    run_fixture,
)

#: Every behaviour the ticket calls out has a fixture named here.
BEHAVIOURS = {
    "reading-speed-splits",
    "clause-boundary-splits",
    "short-sentences-merge",
    "merged-sentences-two-lines",
    "long-sentences-stay-apart",
    "line-length-and-balance",
    "lopsided-clause-balances",
    "maximum-duration-splits",
    "minimum-duration-and-padding",
    "tight-pause-clips-padding",
    "contiguous-clips-to-next-start",
}


def test_every_behaviour_has_a_fixture():
    present = {path.stem for path in fixture_cases()}
    assert present >= BEHAVIOURS


@pytest.mark.parametrize("transcript_path", fixture_cases(), ids=lambda path: path.stem)
def test_golden_sidecar(transcript_path, tmp_path, capsys):
    actual, transcript = run_fixture(transcript_path, tmp_path, capsys)

    expected = transcript_path.with_suffix(".srt").read_bytes()
    assert_sidecar_bytes(actual, expected, label=transcript_path.stem)
    assert_readability(actual, transcript, label=transcript_path.stem)


@pytest.mark.parametrize("transcript_path", fixture_cases(), ids=lambda path: path.stem)
def test_identical_transcripts_produce_identical_sidecars(transcript_path, tmp_path, capsys):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    first, _ = run_fixture(transcript_path, first_dir, capsys)
    second, _ = run_fixture(transcript_path, second_dir, capsys)

    assert first == second


def test_a_failure_names_the_differing_cue_instead_of_a_byte_offset():
    expected = (
        b"1\r\n00:00:00,000 --> 00:00:01,000\r\nHello there.\r\n"
        b"\r\n"
        b"2\r\n00:00:01,100 --> 00:00:02,100\r\nGeneral Kenobi.\r\n"
    )
    actual = expected.replace(b"General Kenobi.", b"General Grievous.")

    with pytest.raises(pytest.fail.Exception) as failure:
        assert_sidecar_bytes(actual, expected, label="example")

    message = str(failure.value)
    assert "cue 2 differs" in message
    assert "General Kenobi." in message
    assert "General Grievous." in message
