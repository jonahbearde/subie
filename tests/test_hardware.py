"""CUDA library resolution: visible device and usable libraries are different facts."""

from __future__ import annotations

from subie import hardware


def _fake_gpu_environment(monkeypatch, *, load_error: str | None = None) -> None:
    def fake_load(name: str) -> None:
        if load_error is not None and "cublas" in name.lower():
            raise OSError(load_error)

    monkeypatch.setattr(hardware, "_load_library", fake_load)
    monkeypatch.setattr(hardware, "_gpu_names", lambda: ("NVIDIA GeForce RTX 3070 Ti",))
    monkeypatch.setattr(hardware, "_probe_cuda", lambda: (1, ("float16", "int8_float16"), None))


def test_a_visible_gpu_whose_libraries_load_is_usable(monkeypatch):
    _fake_gpu_environment(monkeypatch)

    result = hardware.probe_hardware()

    assert result.gpu_names == ("NVIDIA GeForce RTX 3070 Ti",)
    assert result.cuda_device_count == 1
    assert [library.resolved for library in result.cuda_library_checks] == [True, True]
    assert result.cuda_libraries_ok is True
    assert result.cuda_usable is True
    assert hardware.resolve_device(result).name == "cuda"


def test_a_missing_cublas_keeps_the_gpu_from_being_reported_as_usable(monkeypatch):
    """CTranslate2 can see the driver without the CUDA runtime wheels being installed."""
    _fake_gpu_environment(
        monkeypatch,
        load_error="Library cublas64_12.dll is not found or cannot be loaded",
    )

    result = hardware.probe_hardware()

    assert result.cuda_device_count == 1  # the driver still sees the GPU
    assert result.cuda_libraries_ok is False
    assert result.cuda_usable is False
    assert "cublas64_12.dll" in (result.cuda_library_error or "")
    assert hardware.resolve_device(result).name == "cpu"
