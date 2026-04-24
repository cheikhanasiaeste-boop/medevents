"""Parser registry.

Usage:

    from medevents_ingest.parsers import register_parser, parser_for

    @register_parser("ada_listing")
    class AdaListingParser:
        name = "ada_listing"
        def discover(self, source): ...
        def fetch(self, page): ...
        def parse(self, content): ...
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .base import Parser

_T = TypeVar("_T", bound=type[Parser])

_REGISTRY: dict[str, Parser] = {}


class UnknownParserError(KeyError):
    """Raised when a source's parser_name is not registered."""


def register_parser(name: str) -> Callable[[_T], _T]:
    """Class decorator that registers a parser instance under `name`."""

    def _wrap(cls: _T) -> _T:
        if name in _REGISTRY:
            raise ValueError(f"Parser '{name}' is already registered")
        instance = cls()
        if instance.name != name:
            raise ValueError(
                f"Parser class declares name='{instance.name}' but decorator registers as '{name}'"
            )
        _REGISTRY[name] = instance
        return cls

    return _wrap


def parser_for(parser_name: str | None) -> Parser:
    """Resolve a parser by name. Raises UnknownParserError if not registered.

    The generic fallback parser is W3 work; for W1/W2 a missing parser_name is a hard error.
    """
    if parser_name is None:
        raise UnknownParserError("source.parser_name is None; generic fallback parser is W3 work")
    if parser_name not in _REGISTRY:
        raise UnknownParserError(f"No parser registered as '{parser_name}'")
    return _REGISTRY[parser_name]


def registered_parser_names() -> list[str]:
    return sorted(_REGISTRY.keys())


def _reset_registry_for_tests() -> None:
    """Test-only helper to clear the registry between tests."""
    _REGISTRY.clear()


__all__ = [
    "Parser",
    "UnknownParserError",
    "parser_for",
    "register_parser",
    "registered_parser_names",
]

# Side-effect: registers the curated-source parsers.
from . import aap, ada, fdi, gnydm  # noqa: E402,F401
