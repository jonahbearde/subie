import pytest


@pytest.fixture(autouse=True)
def subie_home(tmp_path, monkeypatch):
    """Keep every test off the developer's real model cache."""
    home = tmp_path / "subie-home"
    monkeypatch.setenv("SUBIE_HOME", str(home))
    return home
