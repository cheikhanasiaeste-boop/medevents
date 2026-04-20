"""YAML → DB seed importer for sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from .models import SourceSeed
from .repositories.sources import upsert_source_seed

_SEEDS_ADAPTER = TypeAdapter(list[SourceSeed])


def load_source_seeds(path: Path) -> list[SourceSeed]:
    """Parse and validate a sources.yaml file. Raises ValidationError on bad shape."""
    raw: Any = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"Expected a YAML list at {path}; got {type(raw).__name__}")
    return _SEEDS_ADAPTER.validate_python(raw)


def upsert_all(session: Session, seeds: list[SourceSeed]) -> int:
    """Upsert each seed; return the number of rows touched."""
    for seed in seeds:
        upsert_source_seed(session, seed)
    return len(seeds)
