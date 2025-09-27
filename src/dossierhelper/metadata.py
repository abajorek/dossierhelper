"""macOS metadata utilities."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from rich.console import Console

console = Console()


@dataclass
class ArtifactMetadata:
    path: Path
    raw: dict[str, str]
    finder_tags: List[str]


def run_mdls(path: Path) -> dict[str, str]:
    """Fetch Spotlight metadata via mdls."""

    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemContentCreationDate", "-name", "kMDItemKind", "-name", "kMDItemUserTags", str(path)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return {}

    metadata: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        metadata[key] = value.strip().strip('"')
    return metadata


def read_finder_tags(path: Path, *, metadata: dict[str, str] | None = None) -> List[str]:
    metadata = metadata or run_mdls(path)
    tags = metadata.get("kMDItemUserTags", "")
    if tags.startswith("(") and tags.endswith(")"):
        tags = tags[1:-1]
    return [tag.strip().strip('"') for tag in tags.split(",") if tag.strip()]


def write_finder_tags(path: Path, tags: Iterable[str]) -> None:
    tag_list = list(tags)
    try:
        from Cocoa import NSURL
        from Foundation import NSArray

        url = NSURL.fileURLWithPath_(str(path))
        NSArray.arrayWithArray_(tag_list)
        url.setResourceValue_forKey_error_(tag_list, "NSURLTagNamesKey", None)
    except Exception as exc:  # noqa: BLE001
        console.log(f"[yellow]Unable to update Finder tags for {path}: {exc}")


def gather_metadata(path: Path) -> ArtifactMetadata:
    raw = run_mdls(path)
    tags = read_finder_tags(path, metadata=raw)
    return ArtifactMetadata(path=path, raw=raw, finder_tags=tags)
