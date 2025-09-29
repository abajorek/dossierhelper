"""Enhanced configuration loading utilities for dossierhelper with academic-evidence-finder support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Any
import re
import yaml


def _expand_paths(paths: Iterable[str]) -> List[Path]:
    return [Path(p).expanduser().resolve() for p in paths]


@dataclass
class CategoryRule:
    """A category rule with regex patterns."""
    
    name: str
    patterns: List[str]
    compiled_patterns: List[re.Pattern] = field(default_factory=list, init=False)
    
    def __post_init__(self):
        """Compile regex patterns for efficient matching."""
        self.compiled_patterns = []
        for pattern in self.patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                # If regex compilation fails, treat as literal string
                escaped = re.escape(pattern)
                self.compiled_patterns.append(re.compile(escaped, re.IGNORECASE))
    
    def matches(self, text: str) -> bool:
        """Check if text matches any of the patterns."""
        return any(pattern.search(text) for pattern in self.compiled_patterns)


@dataclass
class FileFilters:
    """File filtering configuration."""
    
    include_extensions: List[str] = field(default_factory=list)
    exclude_dirs: List[str] = field(default_factory=list)


@dataclass
class ScoringConfig:
    """Scoring and weighting configuration."""
    
    per_hit_points: int = 1
    cap_per_file: int = 25
    category_weights: Dict[str, float] = field(default_factory=dict)
    bonus_keywords: Dict[str, int] = field(default_factory=dict)


@dataclass
class FileProcessingConfig:
    """File processing configuration."""
    
    proprietary_formats: List[str] = field(default_factory=list)
    filename_analysis: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class EffortAnalysisConfig:
    """Effort estimation configuration."""
    
    work_session_max_gap_hours: int = 4
    minimum_work_session_minutes: int = 5
    typical_save_intervals: Dict[str, int] = field(default_factory=dict)
    complexity_multipliers: Dict[str, float] = field(default_factory=dict)


@dataclass
class MacOSConfig:
    """macOS specific configuration."""
    
    enable_finder_tags: bool = True
    tag_colors: Dict[str, str] = field(default_factory=dict)


@dataclass
class GoogleDriveConfig:
    """Google Drive configuration for a single drive."""
    
    name: str  # Friendly name (e.g., "personal", "work")
    folder_id: Optional[str] = None  # Optional root folder ID to search
    client_secrets_file: Optional[str] = None  # Path to OAuth credentials
    enabled: bool = True


@dataclass
class ReportingConfig:
    """Output and analytics configuration."""

    output_directory: Path
    include_text_snippets: bool = False


@dataclass
class AppConfig:
    """Enhanced user configurable settings loaded from YAML."""

    search_roots: List[Path]
    categories: Dict[str, Dict[str, CategoryRule]] = field(default_factory=dict)
    file_filters: FileFilters = field(default_factory=FileFilters)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    file_processing: FileProcessingConfig = field(default_factory=FileProcessingConfig)
    effort_analysis: EffortAnalysisConfig = field(default_factory=EffortAnalysisConfig)
    macos: MacOSConfig = field(default_factory=MacOSConfig)
    google_drives: List[GoogleDriveConfig] = field(default_factory=list)
    
    # Legacy support
    ignored_directories: List[str] = field(default_factory=list)
    extensions: dict[str, List[str]] = field(default_factory=dict)
    metadata: dict[str, str | list[str]] = field(default_factory=dict)
    reporting: Optional[ReportingConfig] = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        data = yaml.safe_load(Path(path).read_text()) or {}
        
        # Handle search roots
        search_roots = _expand_paths(data.get("search_roots", ["."]))
        
        # Parse categories
        categories = {}
        categories_data = data.get("categories", {})
        for category_name, subcategories in categories_data.items():
            categories[category_name] = {}
            for subcategory_name, rules in subcategories.items():
                if isinstance(rules, dict) and "any" in rules:
                    patterns = rules["any"]
                    categories[category_name][subcategory_name] = CategoryRule(
                        name=subcategory_name,
                        patterns=patterns
                    )
        
        # Parse file filters
        file_filters_data = data.get("file_filters", {})
        file_filters = FileFilters(
            include_extensions=file_filters_data.get("include_extensions", []),
            exclude_dirs=file_filters_data.get("exclude_dirs", [])
        )
        
        # Parse scoring
        scoring_data = data.get("scoring", {})
        scoring = ScoringConfig(
            per_hit_points=scoring_data.get("per_hit_points", 1),
            cap_per_file=scoring_data.get("cap_per_file", 25),
            category_weights=scoring_data.get("category_weights", {}),
            bonus_keywords=scoring_data.get("bonus_keywords", {})
        )
        
        # Parse file processing
        file_proc_data = data.get("file_processing", {})
        file_processing = FileProcessingConfig(
            proprietary_formats=file_proc_data.get("proprietary_formats", []),
            filename_analysis=file_proc_data.get("filename_analysis", {})
        )
        
        # Parse effort analysis
        effort_data = data.get("effort_analysis", {})
        effort_analysis = EffortAnalysisConfig(
            work_session_max_gap_hours=effort_data.get("work_session_max_gap_hours", 4),
            minimum_work_session_minutes=effort_data.get("minimum_work_session_minutes", 5),
            typical_save_intervals=effort_data.get("typical_save_intervals", {}),
            complexity_multipliers=effort_data.get("complexity_multipliers", {})
        )
        
        # Parse macOS config
        macos_data = data.get("macos", {})
        macos = MacOSConfig(
            enable_finder_tags=macos_data.get("enable_finder_tags", True),
            tag_colors=macos_data.get("tag_colors", {})
        )
        
        # Legacy support
        ignored_directories = data.get("ignored_directories", []) or file_filters.exclude_dirs
        extensions = data.get("extensions", {})
        metadata = data.get("metadata", {})
        
        # Google Drives
        google_drives_data = data.get("google_drives", [])
        google_drives = []
        for drive_data in google_drives_data:
            client_secrets = drive_data.get("client_secrets_file")
            if client_secrets:
                client_secrets = str(Path(client_secrets).expanduser().resolve())
            
            google_drives.append(GoogleDriveConfig(
                name=drive_data["name"],
                folder_id=drive_data.get("folder_id"),
                client_secrets_file=client_secrets,
                enabled=drive_data.get("enabled", True)
            ))
        
        # Reporting
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
            categories=categories,
            file_filters=file_filters,
            scoring=scoring,
            file_processing=file_processing,
            effort_analysis=effort_analysis,
            macos=macos,
            google_drives=google_drives,
            ignored_directories=ignored_directories,
            extensions=extensions,
            metadata=metadata,
            reporting=reporting,
        )

    def should_scan_path(self, path: Path) -> bool:
        """Return True if the provided path should be processed."""
        parts = {part for part in path.parts}
        
        # Check against new exclude_dirs
        if any(excluded in parts for excluded in self.file_filters.exclude_dirs):
            return False
            
        # Check against legacy ignored_directories for backward compatibility
        if any(ignored in parts for ignored in self.ignored_directories):
            return False
            
        return True
    
    def should_process_file(self, file_path: Path) -> bool:
        """Return True if the file should be processed based on extension."""
        if not self.file_filters.include_extensions:
            return True  # No filter means process all
            
        file_ext = file_path.suffix.lower()
        return file_ext in self.file_filters.include_extensions
    
    def classify_text(self, text: str, filename: str = "") -> Dict[str, List[str]]:
        """Classify text into categories based on configured rules."""
        results = {}
        
        # Combine text and filename for analysis
        full_text = f"{text} {filename}"
        
        for category_name, subcategories in self.categories.items():
            matches = []
            for subcategory_name, rule in subcategories.items():
                if rule.matches(full_text):
                    matches.append(subcategory_name)
            
            if matches:
                results[category_name] = matches
        
        return results
    
    def calculate_score(self, text: str, filename: str, categories: Dict[str, List[str]]) -> float:
        """Calculate relevance score for a document."""
        score = 0.0
        full_text = f"{text} {filename}".lower()
        
        # Base scoring for category matches
        for category_name, subcategories in categories.items():
            category_weight = self.scoring.category_weights.get(category_name, 1.0)
            base_points = len(subcategories) * self.scoring.per_hit_points * category_weight
            score += base_points
        
        # Bonus keyword scoring
        for keyword, bonus_points in self.scoring.bonus_keywords.items():
            keyword_lower = keyword.lower()
            if keyword_lower in full_text:
                score += bonus_points
        
        # Apply per-file cap
        return min(score, self.scoring.cap_per_file)


def _default_config_path() -> Optional[Path]:
    """Return the path to the packaged example configuration, if it exists."""
    candidate = Path(__file__).resolve().parent.parent.parent / "example_config.yaml"
    return candidate if candidate.exists() else None


def _load_default_config() -> AppConfig:
    """Load the default configuration bundled with the project."""
    example_path = _default_config_path()
    if example_path:
        try:
            return AppConfig.from_yaml(example_path)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not load default config: {e}")
            pass
    
    # Fallback minimal config
    return AppConfig(
        search_roots=[Path.home()],
        file_filters=FileFilters(
            include_extensions=[".pdf", ".docx", ".txt"],
            exclude_dirs=[".git", "node_modules", "__pycache__", ".venv"]
        )
    )


DEFAULT_CONFIG = _load_default_config()
DEFAULT_CONFIG_PATH = _default_config_path()
