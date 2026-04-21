"""Test-only helper to reset the parser registry before a reload-based test."""

from . import _reset_registry_for_tests


def reset_registry() -> None:
    _reset_registry_for_tests()
