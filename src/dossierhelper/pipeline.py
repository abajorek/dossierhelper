"""Three-pass dossier processing pipeline."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional

from rich.console import Console
from rich.progress import Progress

from . import classifier
from .classifier import ClassificationResult
from .config import AppConfig, DEFAULT_CONFIG
from .metadata import gather_metadata, read_finder_tags, write_finder_tags
from .text import extract_text

console = Console()


@dataclass
class Artifact:
    path: Path
    metadata: dict[str, str] = field(default_factory=dict)
    classification: Optional[ClassificationResult] = None
    text: Optional[str] = None
    hours_spent: float | None = None


@dataclass
class ProgressEvent:
    stage: str
    message: str
    scanned_count: Optional[int] = None
    total_candidates: Optional[int] = None
    bucket: Optional[str] = None
    bucket_totals: Optional[dict[str, int]] = None
    finder_tagged: Optional[bool] = None


class DossierPipeline:
    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG

    def pass_one_surface_scan(
        self,
        *,
        year: Optional[int] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> List[Artifact]:
        console.log("Starting pass one (surface scan)...")
        candidates: list[Path] = []
        scanned_count = 0
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
                scanned_count += 1
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass1",
                            message=f"Scanning {path.name}",
                            scanned_count=scanned_count,
                        )
                    )
        filtered = classifier.filter_by_year(candidates, year=year, metadata_lookup=lambda p: gather_metadata(p).raw)
        artifacts = [Artifact(path=path) for path in filtered]
        if progress_callback:
            progress_callback(
                ProgressEvent(
                    stage="pass1",
                    message=f"Surfaced {len(artifacts)} dossier hopefuls from {scanned_count} scanned items.",
                    scanned_count=scanned_count,
                    total_candidates=len(artifacts),
                )
            )
        return artifacts

    def pass_two_deep_analysis(
        self,
        artifacts: Iterable[Artifact],
        *,
        apply_tags: bool = True,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> List[Artifact]:
        console.log("Starting pass two (deep analysis)...")
        enriched: List[Artifact] = []
        artifacts_list = list(artifacts)
        bucket_totals: Counter[str] = Counter()
        with Progress() as progress:
            task = progress.add_task("Analyzing artifacts", total=len(artifacts_list))
            for index, artifact in enumerate(artifacts_list, start=1):
                meta = gather_metadata(artifact.path)
                artifact.metadata = meta.raw
                artifact.text = extract_text(artifact.path)
                artifact.classification = classifier.classify(artifact.path, metadata=meta.raw, text=artifact.text)
                artifact.hours_spent = _estimate_hours(artifact, self.config.metadata)
                bucket = "Unclassified"
                if artifact.classification:
                    bucket = artifact.classification.portfolio_destination
                bucket_totals[bucket] += 1
                finder_tagged = False
                if apply_tags and artifact.classification:
                    desired_tags = _finder_tags_for(artifact.classification)
                    write_finder_tags(artifact.path, desired_tags)
                    updated_tags = read_finder_tags(artifact.path)
                    finder_tagged = all(tag in updated_tags for tag in desired_tags)
                enriched.append(artifact)
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass2",
                            message=f"Sorted {artifact.path.name} into {bucket}.",
                            scanned_count=index,
                            bucket=bucket,
                            bucket_totals=dict(bucket_totals),
                            finder_tagged=finder_tagged if apply_tags else None,
                        )
                    )
                progress.advance(task)
        return enriched

    def pass_three_report(
        self,
        artifacts: Iterable[Artifact],
        *,
        output: Optional[Path] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> Path:
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
        if progress_callback:
            progress_callback(
                ProgressEvent(
                    stage="pass3",
                    message=f"Report locked in at {output}",
                )
            )
        return output

    def run_all(
        self,
        *,
        year: Optional[int] = None,
        apply_tags: bool = True,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> Path:
        artifacts = self.pass_one_surface_scan(year=year, progress_callback=progress_callback)
        enriched = self.pass_two_deep_analysis(
            artifacts,
            apply_tags=apply_tags,
            progress_callback=progress_callback,
        )
        reporting_path = None
        if self.config.reporting:
            output_dir = self.config.reporting.output_directory
            output_dir.mkdir(parents=True, exist_ok=True)
            reporting_path = self.pass_three_report(
                enriched,
                output=output_dir / f"dossier_report_{year or 'all'}.csv",
                progress_callback=progress_callback,
            )
        else:
            reporting_path = self.pass_three_report(enriched, progress_callback=progress_callback)
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
