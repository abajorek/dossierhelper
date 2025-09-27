"""Three-pass dossier processing pipeline."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from rich.console import Console
from rich.progress import Progress

from . import classifier
from .classifier import ClassificationResult
from .config import AppConfig, DEFAULT_CONFIG
from .metadata import gather_metadata, write_finder_tags
from .text import extract_text

console = Console()


@dataclass
class Artifact:
    path: Path
    metadata: dict[str, str] = field(default_factory=dict)
    classification: Optional[ClassificationResult] = None
    text: Optional[str] = None
    hours_spent: float | None = None


class DossierPipeline:
    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG

    def pass_one_surface_scan(self, *, year: Optional[int] = None) -> List[Artifact]:
        console.log("Starting pass one (surface scan)...")
        candidates: list[Path] = []
        for root in self.config.search_roots:
            if not root.exists():
                console.log(f"[yellow]Search root {root} does not exist; skipping.")
                continue
            for path in _iter_files(root):
                if not path.is_file():
                    continue
                if not self.config.should_scan_path(path):
                    continue
                candidates.append(path)
        filtered = classifier.filter_by_year(candidates, year=year, metadata_lookup=lambda p: gather_metadata(p).raw)
        return [Artifact(path=path) for path in filtered]

    def pass_two_deep_analysis(self, artifacts: Iterable[Artifact], *, apply_tags: bool = True) -> List[Artifact]:
        console.log("Starting pass two (deep analysis)...")
        enriched: List[Artifact] = []
        artifacts_list = list(artifacts)
        with Progress() as progress:
            task = progress.add_task("Analyzing artifacts", total=len(artifacts_list))
            for artifact in artifacts_list:
                meta = gather_metadata(artifact.path)
                artifact.metadata = meta.raw
                artifact.text = extract_text(artifact.path)
                artifact.classification = classifier.classify(artifact.path, metadata=meta.raw, text=artifact.text)
                artifact.hours_spent = _estimate_hours(artifact, self.config.metadata)
                if apply_tags and artifact.classification:
                    write_finder_tags(artifact.path, _finder_tags_for(artifact.classification))
                enriched.append(artifact)
                progress.advance(task)
        return enriched

    def pass_three_report(self, artifacts: Iterable[Artifact], *, output: Optional[Path] = None) -> Path:
        console.log("Starting pass three (reporting)...")
        artifacts_list = list(artifacts)
        if output is None:
            output = Path.cwd() / "dossier_report.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=["path", "category", "subcategory", "destination", "rationale", "hours_spent"],
            )
            writer.writeheader()
            for artifact in artifacts_list:
                classification = artifact.classification
                writer.writerow(
                    {
                        "path": str(artifact.path),
                        "category": classification.category.value if classification else "Unclassified",
                        "subcategory": classification.subcategory if classification else "",
                        "destination": classification.portfolio_destination if classification else "",
                        "rationale": classification.rationale if classification else "",
                        "hours_spent": artifact.hours_spent or "",
                    }
                )
        return output

    def run_all(self, *, year: Optional[int] = None, apply_tags: bool = True) -> Path:
        artifacts = self.pass_one_surface_scan(year=year)
        enriched = self.pass_two_deep_analysis(artifacts, apply_tags=apply_tags)
        reporting_path = None
        if self.config.reporting:
            output_dir = self.config.reporting.output_directory
            output_dir.mkdir(parents=True, exist_ok=True)
            reporting_path = self.pass_three_report(
                enriched,
                output=output_dir / f"dossier_report_{year or 'all'}.csv",
            )
        else:
            reporting_path = self.pass_three_report(enriched)
        return reporting_path


def _finder_tags_for(result: ClassificationResult) -> List[str]:
    return [result.category.value, result.portfolio_destination]


def _estimate_hours(artifact: Artifact, metadata: dict[str, str | list[str]]) -> float | None:
    author = metadata.get("author") if isinstance(metadata.get("author"), str) else None
    if not author:
        return None
    text = artifact.text or ""
    marker = "HoursSpent:"
    if marker in text:
        try:
            return float(text.split(marker, 1)[1].split()[0])
        except (ValueError, IndexError):
            return None
    return None


def _iter_files(root: Path) -> Iterator[Path]:
    try:
        yield from root.rglob("*")
    except PermissionError as exc:  # noqa: BLE001
        console.log(f"[yellow]Permission denied while scanning {root}: {exc}")
        return
