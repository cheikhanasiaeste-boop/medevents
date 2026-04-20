"""Shared pytest fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _no_env_pollution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must declare any env they need; nothing leaks from the host."""
    for key in list(os.environ):
        if key.startswith("MEDEVENTS_") or key in {"DATABASE_URL"}:
            monkeypatch.delenv(key, raising=False)
