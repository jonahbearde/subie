"""End-to-end: real audio, real PyAV decoding, real faster-whisper engine.

Excluded from the default run by the ``slow`` marker. Skips cleanly when no model is
cached or when the machine has no offline speech synthesiser to generate the Video.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from subie import models
from subie.cli import run
from subie.deps import default_deps
from subie.exit_codes import EXIT_OK

pytestmark = pytest.mark.slow

_SPOKEN = "The quick brown fox jumps over the lazy dog."


def _synthesise_speech(path: Path) -> bool:
    """Generate a short WAV saying :data:`_SPOKEN`, using an offline OS synthesiser."""

    def try_command(command: list[str]) -> bool:
        completed = subprocess.run(command, capture_output=True, timeout=60, check=False)
        return completed.returncode == 0 and path.exists()

    if sys.platform == "win32":
        escaped = str(path).replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{escaped}'); "
            f"$s.Speak('{_SPOKEN}'); "
            "$s.Dispose()"
        )
        if try_command(["powershell", "-NoProfile", "-Command", script]):
            return True

    for executable in ("espeak-ng", "espeak"):
        if shutil.which(executable) and try_command([executable, "-w", str(path), _SPOKEN]):
            return True

    if sys.platform == "darwin" and shutil.which("say"):
        if try_command(["say", "-o", str(path), "--data-format=LEI16@22050", _SPOKEN]):
            return True

    return False


def test_a_real_video_produces_a_readable_sidecar(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("SUBIE_HOME", raising=False)
    present = models.present_models()
    if not present:
        pytest.skip("no recognition model is cached on this machine")
    model = next((m for m in present if m.name == "small.en"), present[0])

    video = tmp_path / "spoken.wav"
    if not _synthesise_speech(video):
        pytest.skip("no offline speech synthesiser is available to generate a test Video")

    code = run(
        [str(video), "--model", model.name, "--device", "cpu"],
        default_deps(),
    )
    captured = capsys.readouterr()

    assert code == EXIT_OK, captured.err
    assert "Traceback" not in captured.err
    assert captured.err == ""
    assert re.fullmatch(
        r"spoken\.wav " + "\u2192" + r" spoken\.srt  \d+ cues?  \d+\.\d+s",
        captured.out.strip(),
    )

    sidecar = tmp_path / "spoken.srt"
    assert sidecar.exists()
    data = sidecar.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8")
    assert text.endswith("\r\n")

    blocks = [block for block in text.split("\r\n\r\n") if block.strip()]
    assert 1 <= len(blocks) <= 6
    for number, block in enumerate(blocks, start=1):
        lines = block.split("\r\n")
        assert lines[0] == str(number)
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", lines[1])

    spoken = text.lower()
    assert "quick" in spoken
    assert "fox" in spoken

    assert sorted(path.name for path in tmp_path.iterdir()) == ["spoken.srt", "spoken.wav"]
