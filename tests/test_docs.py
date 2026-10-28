"""The documents a new person follows: README, install notes and subtitle policy.

These are not pipeline tests. They guard the promises the docs make: the first example is
the zero-argument case, both machines are covered, the policy's numbers are the
segmenter's numbers, and the limits and exit codes are stated rather than implied.
"""

from __future__ import annotations

import re
from pathlib import Path

from subie.segment import (
    INTER_CUE_GAP_S,
    MAX_CUE_DURATION_S,
    MAX_LINE_CHARS,
    MAX_LINES_PER_CUE,
    MAX_READING_CPS,
    MIN_CUE_DURATION_S,
    TRAILING_PADDING_S,
)

ROOT = Path(__file__).parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
POLICY = (ROOT / "docs" / "subtitle-policy.md").read_text(encoding="utf-8")


def _console_blocks(text: str) -> list[str]:
    return re.findall(r"```console[^\n]*\n(.*?)```", text, re.DOTALL)


def test_readme_opens_with_the_zero_argument_example():
    blocks = _console_blocks(README)

    assert blocks, "the README must show a console example"
    assert blocks[0].strip().splitlines() == ["subie video.mp4"]


def test_readme_installs_on_both_machines_and_verifies_the_gpu_path():
    assert 'uv tool install "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"' in README
    assert 'uv tool install "subie @ git+https://github.com/jonahbearde/subie.git"' in README
    assert "subie doctor" in README
    assert "--device cuda" in README
    assert "not usable" in README
    assert "docs/install.md" in README


def test_install_notes_cover_a_machine_without_git_and_an_offline_model_pull():
    assert "Git" in INSTALL
    assert "ZIP" in INSTALL
    assert "models pull" in INSTALL
    assert 'uv tool install ".[cuda]"' in INSTALL


def test_readme_documents_every_flag_that_changes_a_run():
    for flag in (
        "-r",
        "--force",
        "--out-dir",
        "--jobs",
        "--model",
        "--device",
        "--keep-audio",
        "--quiet",
        "--verbose",
    ):
        assert flag in README, f"the README does not document {flag}"


def test_readme_documents_keep_audio_as_the_way_to_hear_the_engine_input():
    assert "--keep-audio" in README
    assert ".keep-audio.wav" in README
    assert "16 kHz" in README


def test_readme_documents_skip_force_and_exit_codes_with_a_script():
    lowered = README.lower()

    assert "skipped (up to date)" in README
    assert "--force" in README
    assert "exit code" in lowered
    for code in ("0", "1", "2"):
        assert re.search(rf"^\|\s*{code}\s*\|", README, re.MULTILINE), f"code {code} is missing"
    assert "$LASTEXITCODE" in README
    assert "case $code in" in README


def test_readme_states_the_known_limitations_plainly():
    lowered = README.lower()

    for phrase in ("proper noun", "music", "english only", "no translation"):
        assert phrase in lowered, f"the README does not mention {phrase!r}"


def test_readme_links_the_policy_and_every_decision_record():
    assert "docs/subtitle-policy.md" in README

    records = sorted((ROOT / "docs" / "adr").glob("*.md"))
    assert len(records) >= 5
    for record in records:
        assert f"docs/adr/{record.name}" in README, f"{record.name} is not linked from the README"


def _policy_limits() -> dict[str, str]:
    limits: dict[str, str] = {}
    for line in POLICY.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            limits[cells[0]] = cells[1]
    return limits


def test_policy_cue_limits_match_the_segmenter():
    limits = _policy_limits()

    assert str(MAX_LINE_CHARS) in limits["Characters per line"]
    assert str(MAX_LINES_PER_CUE) in limits["Lines per cue"]
    assert f"{MAX_READING_CPS:g} CPS" in limits["Reading speed"]
    assert f"{MIN_CUE_DURATION_S:g} s min" in limits["Cue duration"]
    assert f"{MAX_CUE_DURATION_S:g} s max" in limits["Cue duration"]
    assert f"{INTER_CUE_GAP_S * 1000:g} ms" in limits["Gap between cues"]
    assert f"{TRAILING_PADDING_S * 1000:g} ms" in limits["Trailing padding"]