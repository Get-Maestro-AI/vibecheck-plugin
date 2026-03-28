"""Classify file paths as capturable artifacts.

classify_file(path, content=None) -> tuple[str, str] | None
  Returns (context_type, confidence) or None if the file is not an artifact.

Uses only stdlib. Never raises — returns None on error.
"""

from __future__ import annotations

import os
import re


# High-confidence patterns: filename alone is sufficient.
# Each entry: (glob-style suffix/prefix, context_type)
_HIGH_CONFIDENCE: list[tuple[str, str]] = [
    # Specs
    ("-spec.md", "spec"),
    ("-specification.md", "spec"),
    ("-design.md", "spec"),
    # Plans
    ("-plan.md", "plan"),
    ("-implementation-plan.md", "plan"),
]

_HIGH_CONFIDENCE_PREFIXES: list[tuple[str, str]] = [
    ("spec-", "spec"),
]

_HIGH_CONFIDENCE_EXACT: dict[str, str] = {
    "DESIGN.md": "spec",
}

# Known plugin directories: path segments → context_type
_KNOWN_DIRS: list[tuple[str, str]] = [
    ("docs/superpowers/specs/", "spec"),
    ("docs/superpowers/plans/", "plan"),
    ("specs/", "spec"),
    ("plans/", "plan"),
]

# Headings that indicate structured artifact content (case-insensitive)
_ARTIFACT_HEADINGS = re.compile(
    r"^##?\s+"
    r"(Requirements?|Architecture|Design|Goal|Implementation|Overview|"
    r"Motivation|Background|Acceptance Criteria|Steps|Scope|"
    r"Out of Scope|Risks?|Approach|Context|Problem|Solution)",
    re.IGNORECASE | re.MULTILINE,
)

# Filenames to always skip, even in docs/**
_SKIP_FILENAMES = {
    "README.md",
    "CHANGELOG.md",
    "CHANGES.md",
    "HISTORY.md",
    "LICENSE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CLAUDE.md",
    "MEMORY.md",
}

_MIN_WORD_COUNT = 200


def classify_file(
    path: str, content: str | None = None
) -> tuple[str, str] | None:
    """Classify a file path (and optionally content) as an artifact.

    Returns:
        ("spec"|"plan"|"note", "high"|"medium"|"low") or None
    """
    try:
        return _classify(path, content)
    except Exception:
        return None


def _classify(path: str, content: str | None) -> tuple[str, str] | None:
    # Only markdown files
    if not path.endswith(".md"):
        return None

    # Skip files under ~/.vibecheck/ — these are MCP transport files, not user artifacts
    _vc_home = os.path.expanduser("~/.vibecheck/")
    abs_path = os.path.abspath(os.path.expanduser(path))
    if abs_path.startswith(_vc_home):
        return None

    basename = os.path.basename(path)

    # Skip known non-artifact files
    if basename in _SKIP_FILENAMES:
        return None

    # Normalize path separators
    norm = path.replace("\\", "/")

    # High-confidence: filename suffix
    lower_base = basename.lower()
    for suffix, ctx_type in _HIGH_CONFIDENCE:
        if lower_base.endswith(suffix):
            return (ctx_type, "high")

    # High-confidence: filename prefix
    for prefix, ctx_type in _HIGH_CONFIDENCE_PREFIXES:
        if lower_base.startswith(prefix):
            return (ctx_type, "high")

    # High-confidence: exact match
    if basename in _HIGH_CONFIDENCE_EXACT:
        return (_HIGH_CONFIDENCE_EXACT[basename], "high")

    # Known plugin/convention directories
    for dir_pattern, ctx_type in _KNOWN_DIRS:
        if f"/{dir_pattern}" in norm or norm.startswith(dir_pattern):
            return (ctx_type, "high")

    # Low-confidence catch-all: docs/**/*.md with content heuristic
    if "/docs/" in norm or norm.startswith("docs/"):
        if content is not None:
            return _classify_by_content(content)
        # No content provided — can't classify
        return None

    return None


def _classify_by_content(content: str) -> tuple[str, str] | None:
    """Classify by content heuristics for low-confidence path matches."""
    # Word count check
    words = len(content.split())
    if words < _MIN_WORD_COUNT:
        return None

    # Must have structured headings
    headings = _ARTIFACT_HEADINGS.findall(content)
    if len(headings) < 2:
        return None

    # Heuristic: "spec-like" headings vs "plan-like" headings
    heading_text = " ".join(h.lower() for h in headings)
    if any(w in heading_text for w in ("step", "implementation")):
        return ("plan", "low")
    if any(w in heading_text for w in ("requirement", "architecture", "design")):
        return ("spec", "low")

    return ("note", "low")
