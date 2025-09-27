"""Text extraction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from rich.console import Console

console = Console()

_EXTRACTORS: Dict[str, Callable[[Path], str]] = {}


def register_extractor(suffix: str, func: Callable[[Path], str]) -> None:
    _EXTRACTORS[suffix.lower()] = func


def extract_text(path: Path) -> str:
    extractor = _EXTRACTORS.get(path.suffix.lower())
    if extractor:
        try:
            return extractor(path)
        except Exception as exc:  # noqa: BLE001
            console.log(f"[yellow]Extractor for {path} failed: {exc}")
    if path.suffix.lower() == ".pdf":
        try:
            from pdfminer.high_level import extract_text as pdf_extract

            return pdf_extract(str(path))
        except Exception as exc:  # noqa: BLE001
            console.log(f"[yellow]Falling back from PDF extraction for {path}: {exc}")
    return ""
