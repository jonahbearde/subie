"""``subie doctor`` through the single seam: exit code, reported fields, no tracebacks."""

from __future__ import annotations

import re
import wave

from subie.cli import EXIT_FAILED, EXIT_OK, EXIT_USAGE, run
from subie.media import MediaError
from tests.fakes import (
    CPU_ONLY,
    GPU_READY,
    GPU_UNUSABLE,
    FakeDeviceProbe,
    FakeMediaProbe,
    FakeTranscriberFactory,
    make_deps,
)


def _field(output: str, label: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s{{2,}}(.*)$")
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    raise AssertionError(f"missing {label!r} field in:\n{output}")


def _doctor(capsys, deps, *args):
    code = run(["doctor", *args], deps)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_healthy_gpu_machine_reports_every_field_and_exits_zero(capsys, subie_home):
    transcriber_factory = FakeTranscriberFactory()
    deps = make_deps(hardware=GPU_READY, transcriber_factory=transcriber_factory)

    code, out, err = _doctor(capsys, deps)

    assert code == EXIT_OK
    assert err == ""
    assert "Traceback" not in out + err
    assert _field(out, "python") != ""
    assert "PyAV" in _field(out, "ffmpeg")
    assert _field(out, "media probe").startswith("ok")
    assert _field(out, "device") == "cuda"
    assert "NVIDIA GeForce RTX 3070 Ti" in _field(out, "gpu")
    assert "not usable" not in _field(out, "gpu")
    assert _field(out, "cuda libraries").startswith("resolved")
    assert _field(out, "compute type") == "float16"
    assert _field(out, "model").startswith("turbo")
    assert _field(out, "model cache") == str(subie_home / "models")
    assert _field(out, "models present") == "none"
    assert _field(out, "result").startswith("ready")
    assert transcriber_factory.calls == []


def test_cpu_only_machine_never_claims_a_gpu(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=CPU_ONLY))

    assert code == EXIT_OK
    assert "Traceback" not in out + err
    assert _field(out, "device") == "cpu"
    assert _field(out, "gpu") == "none visible"
    assert "resolved" not in _field(out, "cuda libraries")
    assert _field(out, "compute type") == "int8"
    assert _field(out, "model").startswith("small.en")
    assert _field(out, "result").startswith("ready")


def test_gpu_visible_but_cuda_unresolved_is_reported_as_not_usable(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=GPU_UNUSABLE))

    assert code == EXIT_OK  # the CPU path still works
    assert "Traceback" not in out + err
    assert _field(out, "device") == "cpu"
    assert "NVIDIA GeForce GT 710" in _field(out, "gpu")
    assert "not usable" in _field(out, "gpu")
    assert "not resolved" in _field(out, "cuda libraries")
    assert "cudnn_ops_infer64_8.dll" in _field(out, "cuda libraries")
    assert _field(out, "compute type") == "int8"
    assert _field(out, "model").startswith("small.en")
    assert "GPU not usable" in _field(out, "result")


def test_media_probe_failure_is_reported_without_a_traceback(capsys):
    deps = make_deps(
        hardware=CPU_ONLY,
        media_probe=FakeMediaProbe(error=MediaError("cannot read sample.wav: invalid data")),
    )

    code, out, err = _doctor(capsys, deps)

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert _field(out, "media probe").startswith("failed")
    assert "invalid data" in _field(out, "media probe")
    assert _field(out, "device") == "cpu"  # one broken field does not hide the rest
    assert _field(out, "result").startswith("not ready")


def test_device_probe_failure_is_reported_without_a_traceback(capsys):
    deps = make_deps(device_probe=FakeDeviceProbe(error=RuntimeError("driver probe\nfailed badly")))

    code, out, err = _doctor(capsys, deps)

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert _field(out, "device") == "unknown"
    assert _field(out, "result").startswith("not ready")
    assert "driver probe failed badly" in _field(out, "result")


def test_requesting_cuda_on_an_unusable_machine_is_not_ready(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=GPU_UNUSABLE), "--device", "cuda")

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert _field(out, "device") == "cuda"
    assert "cudnn_ops_infer64_8.dll" in _field(out, "cuda libraries")
    assert _field(out, "result").startswith("not ready")


def test_requesting_cpu_on_a_gpu_machine_reports_cpu_defaults(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=GPU_READY), "--device", "cpu")

    assert code == EXIT_OK
    assert "Traceback" not in out + err
    assert _field(out, "device") == "cpu"
    assert _field(out, "compute type") == "int8"
    assert _field(out, "model").startswith("small.en")


def test_requesting_a_model_reports_it_as_requested(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=GPU_READY), "--model", "medium.en")

    assert code == EXIT_OK
    assert "Traceback" not in out + err
    assert _field(out, "model").startswith("medium.en")
    assert "requested" in _field(out, "model")
    assert _field(out, "compute type") == "float16"


def test_unknown_model_is_a_usage_error_and_starts_no_work(capsys):
    code, out, err = _doctor(capsys, make_deps(hardware=GPU_READY), "--model", "gigantic")

    assert code == EXIT_USAGE
    assert out == ""
    assert "unknown model 'gigantic'" in err
    assert "Traceback" not in err


def test_models_present_lists_only_known_models_already_cached(capsys, subie_home):
    cache = subie_home / "models"
    (cache / "models--Systran--faster-whisper-small.en").mkdir(parents=True)
    (cache / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo").mkdir()
    (cache / "unrelated-download").mkdir()

    code, out, err = _doctor(capsys, make_deps(hardware=CPU_ONLY))

    assert code == EXIT_OK
    assert "Traceback" not in out + err
    assert _field(out, "models present") == "small.en, turbo"


def test_media_probe_self_test_uses_a_real_decodable_clip(capsys):
    class WavCheckingProbe(FakeMediaProbe):
        def __call__(self, path):
            with wave.open(str(path), "rb") as clip:
                assert clip.getnchannels() == 1
                assert clip.getframerate() == 16_000
                assert clip.getnframes() > 0
            return super().__call__(path)

    code, out, err = _doctor(capsys, make_deps(hardware=CPU_ONLY, media_probe=WavCheckingProbe()))

    assert code == EXIT_OK
    assert "Traceback" not in out + err
    assert _field(out, "media probe").startswith("ok")
