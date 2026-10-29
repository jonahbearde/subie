"""Readability segmentation, asserted through the single agreed seam.

Each fixture is a Transcript on disk and the exact Sidecar bytes it must produce. The
same run is also checked against the policy's external limits, Cue by Cue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden import (
    assert_readability,
    assert_sidecar_bytes,
    fixture_cases,
    parse_transcript,
    run_fixture,
)

FIXTURES = Path(__file__).parent / "fixtures" / "segmentation"

#: Every behaviour the ticket calls out has a fixture named here.
BEHAVIOURS = {
    # one line per Cue, and the 90-character cap from both sides
    "one-line-cue-at-sixty-one-characters",
    "one-line-cues-never-wrap",
    "ninety-character-cue-fits-one-line",
    "over-ninety-splits-into-two-cues",
    "normalization-splits-oversized-cue",
    # Fragments read as fragments
    "fragment-drops-its-comma",
    "fragment-keeps-no-stop",
    "fragment-second-cue-starts-lowercase",
    "proper-noun-keeps-its-capital",
    "pronoun-keeps-its-capital",
    "sentence-edge-of-a-fragment-keeps-its-stop",
    "article-final-stop-is-not-a-sentence-end",
    # one Sentence per Cue, and the rescue for one too slight to stand alone
    "rescue-short-utterance-joins-forward",
    "rescue-short-utterance-joins-backward",
    "forty-character-scrap-joins-forward",
    "comfortable-sentence-stays-alone",
    # what ends a Sentence when the engine punctuates nothing
    "pause-ends-unpunctuated-sentence",
    "short-pause-does-not-end-a-sentence",
    # splitting a Sentence too long for one Cue
    "midpoint-halving-not-capacity-filling",
    "recursive-halving-quarters-a-long-sentence",
    "clause-boundary-splits",
    "reading-speed-splits",
    "dense-speech-stays-whole",
    "maximum-duration-splits",
    "seven-seconds-still-makes-two-cues",
    # the limits themselves
    "long-sentences-stay-apart",
    "lopsided-pair-cuts-at-the-sentence-end",
    "minimum-duration-and-padding",
    "minimum-duration-takes-the-gap",
    "unavoidable-sub-second-cue",
    "tight-pause-clips-padding",
    "contiguous-clips-to-next-start",
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


@pytest.mark.parametrize("transcript_path", fixture_cases(FIXTURES), ids=lambda path: path.stem)
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


def test_the_limits_checker_rejects_two_comfortable_sentences_in_one_cue():
    transcript = parse_transcript(
        (FIXTURES / "comfortable-sentence-stays-alone.transcript").read_text(encoding="utf-8")
    )
    packed = (
        b"1\r\n00:00:00,000 --> 00:00:07,000\r\n"
        b"The first thing you should know is this one. "
        b"The second thing matters even more than that.\r\n"
    )

    with pytest.raises(AssertionError, match="2 Sentences in one Cue"):
        assert_readability(packed, transcript, label="packed")


def test_the_limits_checker_rejects_a_cue_that_wraps_onto_a_second_line():
    transcript = parse_transcript(
        (FIXTURES / "one-line-cue-at-sixty-one-characters.transcript").read_text(encoding="utf-8")
    )
    wrapped = (
        b"1\r\n00:00:00,000 --> 00:00:05,400\r\n"
        b"What does it look like for a story to\r\n"
        b"be stripped right back?\r\n"
    )

    with pytest.raises(AssertionError, match="2 lines, not one"):
        assert_readability(wrapped, transcript, label="wrapped")


def test_the_limits_checker_rejects_a_line_over_ninety_characters():
    transcript = parse_transcript(
        (FIXTURES / "over-ninety-splits-into-two-cues.transcript").read_text(encoding="utf-8")
    )
    oversized = (
        b"1\r\n00:00:00,000 --> 00:00:06,920\r\n"
        b"The committee met on Tuesday afternoon to discuss the proposal and then decided "
        b"to postpone the vote until everyone had spoken.\r\n"
    )

    with pytest.raises(AssertionError, match="line too long"):
        assert_readability(oversized, transcript, label="oversized")


def test_the_limits_checker_rejects_a_lowercase_start_at_a_sentence_start():
    transcript = parse_transcript(
        (FIXTURES / "comfortable-sentence-stays-alone.transcript").read_text(encoding="utf-8")
    )
    lowercase = (
        b"1\r\n00:00:00,000 --> 00:00:03,800\r\n"
        b"the first thing you should know is this one.\r\n"
        b"\r\n"
        b"2\r\n00:00:04,000 --> 00:00:07,400\r\n"
        b"The second thing matters even more than that.\r\n"
    )

    with pytest.raises(AssertionError, match="starts lowercase at a Sentence start"):
        assert_readability(lowercase, transcript, label="lowercase")


def test_the_limits_checker_rejects_a_stop_where_the_sentence_carries_on():
    transcript = parse_transcript(
        (FIXTURES / "over-ninety-splits-into-two-cues.transcript").read_text(encoding="utf-8")
    )
    stopped = (
        b"1\r\n00:00:00,000 --> 00:00:03,200\r\n"
        b"The committee met on Tuesday afternoon to discuss the proposal.\r\n"
        b"\r\n"
        b"2\r\n00:00:03,200 --> 00:00:06,920\r\n"
        b"and then decided to postpone the vote until everyone had spoken.\r\n"
    )

    with pytest.raises(AssertionError, match="a stop where its Sentence carries on"):
        assert_readability(stopped, transcript, label="stopped")


def test_the_limits_checker_rejects_a_missing_stop_at_a_sentence_end():
    transcript = parse_transcript(
        (FIXTURES / "comfortable-sentence-stays-alone.transcript").read_text(encoding="utf-8")
    )
    unterminated = (
        b"1\r\n00:00:00,000 --> 00:00:03,800\r\n"
        b"The first thing you should know is this one\r\n"
        b"\r\n"
        b"2\r\n00:00:04,000 --> 00:00:07,400\r\n"
        b"The second thing matters even more than that.\r\n"
    )

    with pytest.raises(AssertionError, match="no stop at a Sentence end"):
        assert_readability(unterminated, transcript, label="unterminated")


def test_the_limits_checker_rejects_a_lowercased_proper_noun():
    transcript = parse_transcript(
        (FIXTURES / "proper-noun-keeps-its-capital.transcript").read_text(encoding="utf-8")
    )
    mangled = (
        b"1\r\n00:00:00,000 --> 00:00:03,840\r\n"
        b"The committee gathered early in the morning and waited very patiently for\r\n"
        b"\r\n"
        b"2\r\n00:00:03,840 --> 00:00:08,200\r\n"
        b"tuesday afternoon to arrive before they began the meeting in the main hall.\r\n"
    )

    with pytest.raises(AssertionError, match="lowercased a capitalized token"):
        assert_readability(mangled, transcript, label="mangled")


def test_the_limits_checker_rejects_a_short_cue_that_had_room_to_reach_a_second():
    transcript = parse_transcript(
        (FIXTURES / "minimum-duration-takes-the-gap.transcript").read_text(encoding="utf-8")
    )
    short = (
        b"1\r\n00:00:00,000 --> 00:00:00,900\r\nYes.\r\n\r\n"
        b"2\r\n00:00:01,000 --> 00:00:07,700\r\n"
        b"We should probably leave before traffic gets any worse than it is right now.\r\n"
    )

    with pytest.raises(AssertionError, match="room to extend"):
        assert_readability(short, transcript, label="short")
