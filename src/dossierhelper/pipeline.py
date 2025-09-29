"""Three-pass dossier processing pipeline."""

from __future__ import annotations

import csv
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Collection, Iterable, Iterator, List, Optional, Union

from time import perf_counter

from rich.console import Console

from . import classifier
from .classifier import ClassificationResult
from .config import AppConfig, DEFAULT_CONFIG
from .metadata import gather_metadata, read_finder_tags, write_finder_tags
from .text import extract_text

try:
    from .gdrive import GoogleDriveManager, GDriveFile
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False
    GoogleDriveManager = None
    GDriveFile = None

console = Console()


@dataclass
class EnhancedClassificationResult:
    """Enhanced classification result using pattern matching."""
    
    categories: dict[str, list[str]]  # e.g., {"Teaching": ["Syllabi", "Assignments"], "Scholarship": ["Publications"]}
    primary_category: str  # The highest-weighted category
    score: float
    rationale: str
    
    @property
    def portfolio_destination(self) -> str:
        """Determine portfolio destination based on primary category."""
        category_destinations = {
            "Teaching": "Teaching Evidence",
            "Service": "Service Evidence", 
            "Scholarship": "Scholarship Evidence",
            "Research": "Scholarship Evidence",
            "Administration": "Service Evidence"
        }
        return category_destinations.get(self.primary_category, "Unclassified")


@dataclass
class Artifact:
    path: Union[Path, str]  # Can be local Path or Google Drive file reference
    metadata: dict[str, str] = field(default_factory=dict)
    classification: Optional[EnhancedClassificationResult] = None
    text: Optional[str] = None
    hours_spent: float | None = None
    is_gdrive: bool = False
    gdrive_file: Optional['GDriveFile'] = None  # Store GDriveFile if from Google Drive
    temp_path: Optional[Path] = None  # Temp path for downloaded Google Drive files


@dataclass
class ProgressEvent:
    stage: str
    message: str
    scanned_count: Optional[int] = None
    total_candidates: Optional[int] = None
    bucket: Optional[str] = None
    bucket_totals: Optional[dict[str, int]] = None
    finder_tagged: Optional[bool] = None
    eta_seconds: Optional[float] = None
    current_file: Optional[str] = None
    stage_progress: Optional[str] = None
    file_progress_percentage: Optional[float] = None  # Individual file progress 0-100%
    file_progress_step: Optional[str] = None  # Current step (e.g., "Reading", "Extracting", "Classifying")


@dataclass
class RunAllResult:
    report_path: Path
    pass_one_count: int
    pass_two_count: int


class DossierPipeline:
    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.gdrive_manager: Optional[GoogleDriveManager] = None
        
        # Initialize Google Drive if configured
        if GDRIVE_AVAILABLE and self.config.google_drives:
            self._initialize_google_drives()

    def _initialize_google_drives(self) -> None:
        """Initialize and authenticate Google Drive connections."""
        if not GDRIVE_AVAILABLE:
            console.log("[yellow]Google Drive support not available. Install google-api-python-client to enable.")
            return
        
        credentials_dir = Path.home() / ".dossierhelper" / "gdrive_credentials"
        self.gdrive_manager = GoogleDriveManager(credentials_dir)
        
        for drive_config in self.config.google_drives:
            if not drive_config.enabled:
                continue
            
            console.log(f"[cyan]Authenticating Google Drive '{drive_config.name}'...")
            client_secrets = None
            if drive_config.client_secrets_file:
                client_secrets = Path(drive_config.client_secrets_file)
            
            success = self.gdrive_manager.authenticate_drive(
                drive_name=drive_config.name,
                client_secrets_file=client_secrets
            )
            
            if success:
                console.log(f"[green]✓ Google Drive '{drive_config.name}' authenticated successfully")
            else:
                console.log(f"[red]✗ Failed to authenticate Google Drive '{drive_config.name}'")
    
    def _classify_artifact(self, path: Union[Path, str], text: str, metadata: dict) -> Optional[EnhancedClassificationResult]:
        """Classify an artifact using the enhanced pattern matching system."""
        
        # Get categories from pattern matching
        categories = self.config.classify_text(text, str(path))
        
        if not categories:
            return None
            
        # Calculate score
        score = self.config.calculate_score(text, str(path), categories)
        
        # Determine primary category based on weights and matches
        primary_category = "Unclassified"
        max_weighted_score = 0
        
        for category_name, subcategories in categories.items():
            weight = self.config.scoring.category_weights.get(category_name, 1.0)
            weighted_score = len(subcategories) * weight
            
            if weighted_score > max_weighted_score:
                max_weighted_score = weighted_score
                primary_category = category_name
        
        # Build rationale
        rationale_parts = []
        for category_name, subcategories in categories.items():
            subcategory_str = ", ".join(subcategories)
            rationale_parts.append(f"{category_name}: {subcategory_str}")
        
        rationale = f"Pattern matches: {'; '.join(rationale_parts)}. Score: {score:.1f}"
        
        return EnhancedClassificationResult(
            categories=categories,
            primary_category=primary_category,
            score=score,
            rationale=rationale
        )

    def pass_one_surface_scan(
        self,
        *,
        years: Optional[Collection[int]] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> List[Artifact]:
        console.log("Starting pass one (surface scan)...")
        artifacts: list[Artifact] = []
        scanned_count = 0
        
        # Scan local file systems
        for root in self.config.search_roots:
            if not root.exists():
                console.log(f"[yellow]Search root {root} does not exist; skipping.")
                continue
            for path in _iter_files(root):
                if not path.is_file():
                    continue
                if not self.config.should_scan_path(path):
                    continue
                # Use new file extension filtering
                if not self.config.should_process_file(path):
                    continue
                artifacts.append(Artifact(path=path, is_gdrive=False))
                scanned_count += 1
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass1",
                            message=f"Scanning local: {path.name}",
                            scanned_count=scanned_count,
                        )
                    )
        
        # Scan Google Drives if configured
        if self.gdrive_manager:
            for drive_config in self.config.google_drives:
                if not drive_config.enabled:
                    continue
                
                console.log(f"[cyan]Scanning Google Drive '{drive_config.name}'...")
                
                def gdrive_progress(count: int, filename: str) -> None:
                    nonlocal scanned_count
                    scanned_count += 1
                    if progress_callback:
                        progress_callback(
                            ProgressEvent(
                                stage="pass1",
                                message=f"Scanning {drive_config.name}: {filename}",
                                scanned_count=scanned_count,
                            )
                        )
                
                try:
                    for gdrive_file in self.gdrive_manager.list_files(
                        drive_name=drive_config.name,
                        folder_id=drive_config.folder_id,
                        recursive=True,
                        progress_callback=gdrive_progress
                    ):
                        # Create artifact with Google Drive file reference
                        artifact = Artifact(
                            path=f"gdrive://{drive_config.name}/{gdrive_file.name}",
                            is_gdrive=True,
                            gdrive_file=gdrive_file
                        )
                        artifacts.append(artifact)
                except Exception as e:
                    console.log(f"[red]Error scanning Google Drive '{drive_config.name}': {e}")
        
        # Filter by year if specified
        if years:
            year_set = set(years)
            filtered_artifacts = []
            for artifact in artifacts:
                if not artifact.is_gdrive:
                    # Use existing year filter for local files
                    if artifact.path in classifier.filter_by_year(
                        [artifact.path],
                        years=year_set,
                        metadata_lookup=lambda p: gather_metadata(p).raw
                    ):
                        filtered_artifacts.append(artifact)
                else:
                    # For Google Drive files, check modified time
                    if artifact.gdrive_file:
                        modified_year = int(artifact.gdrive_file.modified_time[:4])
                        if modified_year in year_set:
                            filtered_artifacts.append(artifact)
            artifacts = filtered_artifacts
        
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
        total_candidates = len(artifacts_list)
        start_time = perf_counter()
        
        for index, artifact in enumerate(artifacts_list, start=1):
            # Helper function to report file progress
            def report_file_progress(percentage: float, step: str) -> None:
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass2",
                            message=f"Processing {_get_display_name(artifact)}...",
                            scanned_count=index,
                            total_candidates=total_candidates,
                            current_file=str(artifact.path),
                            file_progress_percentage=percentage,
                            file_progress_step=step
                        )
                    )
            
            try:
                # Step 1: Load/Download file (0-30%)
                report_file_progress(0, "Loading file")
                
                if artifact.is_gdrive and artifact.gdrive_file:
                    # Download from Google Drive
                    report_file_progress(10, "Downloading from Google Drive")
                    
                    def download_progress(downloaded: int, total: int) -> None:
                        if total > 0:
                            pct = 10 + (downloaded / total) * 20  # 10-30%
                            report_file_progress(pct, f"Downloading ({downloaded}/{total} bytes)")
                    
                    content = self.gdrive_manager.download_file_content(
                        drive_name=artifact.gdrive_file.drive_name,
                        file=artifact.gdrive_file,
                        progress_callback=download_progress
                    )
                    
                    if content:
                        # Save to temp file
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(artifact.gdrive_file.name).suffix)
                        temp_file.write(content)
                        temp_file.close()
                        artifact.temp_path = Path(temp_file.name)
                        file_path = artifact.temp_path
                    else:
                        console.log(f"[yellow]Failed to download {artifact.gdrive_file.name}")
                        continue
                else:
                    file_path = artifact.path
                
                report_file_progress(30, "File loaded")
                
                # Step 2: Gather metadata (30-45%)
                report_file_progress(30, "Reading metadata")
                meta = gather_metadata(file_path)
                artifact.metadata = meta.raw
                report_file_progress(45, "Metadata extracted")
                
                # Step 3: Extract text (45-70%)
                report_file_progress(45, "Extracting text content")
                artifact.text = extract_text(file_path)
                report_file_progress(70, "Text extracted")
                
                # Step 4: Classify (70-85%)
                report_file_progress(70, "Classifying document")
                artifact.classification = self._classify_artifact(file_path, artifact.text or "", meta.raw)
                report_file_progress(85, "Classification complete")
                
                # Step 5: Estimate hours (85-90%)
                report_file_progress(85, "Estimating effort")
                artifact.hours_spent = _estimate_hours(artifact, self.config.metadata)
                report_file_progress(90, "Effort estimated")
                
                bucket = "Unclassified"
                if artifact.classification:
                    bucket = artifact.classification.primary_category
                bucket_totals[bucket] += 1
                
                # Step 6: Apply Finder tags (90-100%) - only for local files
                finder_tagged = False
                if apply_tags and artifact.classification and self.config.macos.enable_finder_tags and not artifact.is_gdrive:
                    report_file_progress(90, "Applying Finder tags")
                    desired_tags = _finder_tags_for_enhanced(artifact.classification, self.config.macos.tag_colors)
                    write_finder_tags(file_path, desired_tags)
                    updated_tags = read_finder_tags(file_path)
                    finder_tagged = all(tag in updated_tags for tag in desired_tags)
                    report_file_progress(100, "Finder tags applied")
                else:
                    report_file_progress(100, "Complete")
                
                enriched.append(artifact)
                
                # Calculate ETA
                eta_seconds = None
                elapsed = perf_counter() - start_time
                if index and elapsed > 0:
                    remaining = total_candidates - index
                    if remaining > 0:
                        eta_seconds = (elapsed / index) * remaining
                
                # Final progress report for this file
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass2",
                            message=f"Completed {_get_display_name(artifact)}",
                            scanned_count=index,
                            total_candidates=total_candidates,
                            bucket=bucket,
                            bucket_totals=dict(bucket_totals),
                            finder_tagged=finder_tagged if apply_tags else None,
                            eta_seconds=eta_seconds,
                            current_file=str(artifact.path),
                            stage_progress=f"Classified as: {bucket}",
                            file_progress_percentage=100,
                            file_progress_step="Complete"
                        )
                    )
                
                # Clean up temp file if it exists
                if artifact.temp_path and artifact.temp_path.exists():
                    try:
                        artifact.temp_path.unlink()
                    except Exception:
                        pass
            
            except Exception as e:
                console.log(f"[red]Error processing {_get_display_name(artifact)}: {e}")
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            stage="pass2",
                            message=f"Error processing {_get_display_name(artifact)}: {str(e)[:50]}",
                            scanned_count=index,
                            total_candidates=total_candidates,
                            file_progress_percentage=0,
                            file_progress_step="Error"
                        )
                    )
        
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
                fieldnames=["path", "primary_category", "all_categories", "subcategories", "destination", "score", "rationale", "hours_spent"],
            )
            writer.writeheader()
            for artifact in artifacts_list:
                classification = artifact.classification
                
                # Handle enhanced classification format
                if classification:
                    all_categories = ", ".join(classification.categories.keys())
                    subcategories = "; ".join(
                        f"{cat}: {', '.join(subs)}" for cat, subs in classification.categories.items()
                    )
                    
                    writer.writerow(
                        {
                            "path": str(artifact.path),
                            "primary_category": classification.primary_category,
                            "all_categories": all_categories,
                            "subcategories": subcategories,
                            "destination": classification.portfolio_destination,
                            "score": f"{classification.score:.2f}",
                            "rationale": classification.rationale,
                            "hours_spent": artifact.hours_spent or "",
                        }
                    )
                else:
                    writer.writerow(
                        {
                            "path": str(artifact.path),
                            "primary_category": "Unclassified",
                            "all_categories": "",
                            "subcategories": "",
                            "destination": "",
                            "score": "0.00",
                            "rationale": "No patterns matched",
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
        years: Optional[Collection[int]] = None,
        apply_tags: bool = True,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> RunAllResult:
        artifacts = self.pass_one_surface_scan(years=years, progress_callback=progress_callback)
        enriched = self.pass_two_deep_analysis(
            artifacts,
            apply_tags=apply_tags,
            progress_callback=progress_callback,
        )
        reporting_path = None
        if self.config.reporting:
            output_dir = self.config.reporting.output_directory
            output_dir.mkdir(parents=True, exist_ok=True)
            year_suffix = "all"
            if years:
                year_suffix = "-".join(str(y) for y in sorted(set(years)))
            reporting_path = self.pass_three_report(
                enriched,
                output=output_dir / f"dossier_report_{year_suffix}.csv",
                progress_callback=progress_callback,
            )
        else:
            reporting_path = self.pass_three_report(enriched, progress_callback=progress_callback)
        return RunAllResult(
            report_path=reporting_path,
            pass_one_count=len(artifacts),
            pass_two_count=len(enriched),
        )


def _finder_tags_for_enhanced(result: EnhancedClassificationResult, tag_colors: dict[str, str]) -> List[str]:
    """Generate Finder tags for enhanced classification results."""
    tags = []
    
    # Add primary category tag
    tags.append(result.primary_category)
    
    # Add subcategory tags for the primary category
    if result.primary_category in result.categories:
        for subcategory in result.categories[result.primary_category]:
            tags.append(subcategory)
    
    return tags


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


def _get_display_name(artifact: Artifact) -> str:
    """Get a display-friendly name for an artifact."""
    if artifact.is_gdrive and artifact.gdrive_file:
        return artifact.gdrive_file.name
    elif isinstance(artifact.path, Path):
        return artifact.path.name
    else:
        return str(artifact.path)


def _iter_files(root: Path) -> Iterator[Path]:
    try:
        yield from root.rglob("*")
    except PermissionError as exc:  # noqa: BLE001
        console.log(f"[yellow]Permission denied while scanning {root}: {exc}")
        return
