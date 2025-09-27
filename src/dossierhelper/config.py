"""Configuration loading utilities for dossierhelper."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

import yaml


def _expand_paths(paths: Iterable[str]) -> List[Path]:
    return [Path(p).expanduser().resolve() for p in paths]


@dataclass
class ReportingConfig:
    """Output and analytics configuration."""

    output_directory: Path
    include_text_snippets: bool = False


@dataclass
class AppConfig:
    """User configurable settings loaded from YAML."""

    search_roots: List[Path]
    ignored_directories: List[str] = field(default_factory=list)
    extensions: dict[str, List[str]] = field(default_factory=dict)
    metadata: dict[str, str | list[str]] = field(default_factory=dict)
    reporting: Optional[ReportingConfig] = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        data = yaml.safe_load(Path(path).read_text()) or {}
        search_roots = _expand_paths(data.get("search_roots", ["."]))
        ignored_directories = data.get("ignored_directories", [])
        extensions = data.get("extensions", {})
        metadata = data.get("metadata", {})
        reporting_data = data.get("reporting")
        reporting = None
        if reporting_data:
            output_dir = Path(reporting_data["output_directory"]).expanduser().resolve()
            reporting = ReportingConfig(
                output_directory=output_dir,
                include_text_snippets=bool(reporting_data.get("include_text_snippets", False)),
            )
        return cls(
            search_roots=search_roots,
            ignored_directories=ignored_directories,
            extensions=extensions,
            metadata=metadata,
            reporting=reporting,
        )

    def should_scan_path(self, path: Path) -> bool:
        """Return True if the provided path should be processed."""

        parts = {part for part in path.parts}
        return not any(ignored in parts for ignored in self.ignored_directories)


def _default_config_path() -> Optional[Path]:
    """Return the path to the packaged example configuration, if it exists."""

    candidate = Path(__file__).resolve().parent.parent / "example_config.yaml"
    return candidate if candidate.exists() else None


def _load_default_config() -> AppConfig:
    """Load the default configuration bundled with the project."""

    example_path = _default_config_path()
    if example_path:
        try:
            return AppConfig.from_yaml(example_path)
        except Exception:  # noqa: BLE001
            pass
    return AppConfig(
        search_roots=[Path.home()],
        ignored_directories=[".git", "node_modules", "__pycache__"],
    )


DEFAULT_CONFIG = _load_default_config()
DEFAULT_CONFIG_PATH = _default_config_path()
