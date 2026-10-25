from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep file exports inside each test's temporary working directory."""
    monkeypatch.chdir(tmp_path)
