from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import project_state_dir


IGNORE_DIRS = {
    ".git",
    ".helix",
    ".helix-agent",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "venv",
}

LANGUAGE_BY_EXT = {
    ".bat": "Batch",
    ".c": "C",
    ".cc": "C++",
    ".cmd": "Batch",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".h": "C/C++",
    ".hpp": "C++",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".lua": "Lua",
    ".md": "Markdown",
    ".php": "PHP",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".yaml": "YAML",
    ".yml": "YAML",
}

IMPORTANT_FILES = {
    "AGENTS.md",
    "Dockerfile",
    "HELIX.md",
    "Makefile",
    "README.md",
    "deno.json",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "tsconfig.json",
}


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    language: str
    bytes: int
    lines: int

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceIndex:
    root: str
    files: list[WorkspaceFile] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    important_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    git: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["files"] = [item.to_json() for item in self.files]
        return data


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part in IGNORE_DIRS for part in relative.parts)


def _language_for(path: Path) -> str:
    return LANGUAGE_BY_EXT.get(path.suffix.lower(), "Other")


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _git_info(root: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(root), capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "status", "--short"], cwd=str(root), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return info
    if branch.returncode == 0 and branch.stdout.strip():
        info["branch"] = branch.stdout.strip()
    if status.returncode == 0:
        info["dirty"] = "true" if status.stdout.strip() else "false"
    return info


def scan_workspace(
    *,
    cwd: Path | None = None,
    max_files: int = 2000,
    max_file_bytes: int = 1_000_000,
) -> WorkspaceIndex:
    root = (cwd or Path.cwd()).resolve()
    files: list[WorkspaceFile] = []
    languages: dict[str, int] = {}
    important: list[str] = []
    tests: list[str] = []
    entrypoints: list[str] = []

    for path in sorted(root.rglob("*")):
        if len(files) >= max_files:
            break
        if _is_ignored(path, root) or not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_file_bytes:
            continue
        rel = path.relative_to(root).as_posix()
        language = _language_for(path)
        item = WorkspaceFile(path=rel, language=language, bytes=size, lines=_line_count(path))
        files.append(item)
        languages[language] = languages.get(language, 0) + 1
        if path.name in IMPORTANT_FILES or rel.startswith(".github/"):
            important.append(rel)
        lowered = rel.lower()
        if "/test" in lowered or lowered.startswith("test") or lowered.startswith("tests") or path.name.startswith("test_"):
            tests.append(rel)
        if path.name in {"main.py", "__main__.py", "app.py", "server.py", "index.js", "index.ts", "main.ts", "main.tsx"}:
            entrypoints.append(rel)

    return WorkspaceIndex(
        root=str(root),
        files=files,
        languages=dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        important_files=important[:80],
        test_files=tests[:120],
        entrypoints=entrypoints[:80],
        git=_git_info(root),
    )


def save_workspace_index(index: WorkspaceIndex, *, cwd: Path | None = None) -> Path:
    out = project_state_dir(cwd) / "workspace-index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index.to_json(), indent=2) + "\n", encoding="utf-8")
    return out


def workspace_map_markdown(index: WorkspaceIndex, *, max_files: int = 120) -> str:
    lines = [
        "# Workspace Map",
        "",
        f"- Root: `{index.root}`",
        f"- Files indexed: {len(index.files)}",
    ]
    if index.git:
        git_parts = ", ".join(f"{key}: {value}" for key, value in index.git.items())
        lines.append(f"- Git: {git_parts}")
    lines.extend(["", "## Languages", ""])
    for language, count in index.languages.items():
        lines.append(f"- {language}: {count}")
    if index.important_files:
        lines.extend(["", "## Important Files", ""])
        lines.extend(f"- `{path}`" for path in index.important_files)
    if index.entrypoints:
        lines.extend(["", "## Entrypoints", ""])
        lines.extend(f"- `{path}`" for path in index.entrypoints)
    if index.test_files:
        lines.extend(["", "## Tests", ""])
        lines.extend(f"- `{path}`" for path in index.test_files[:60])
    lines.extend(["", "## File Inventory", ""])
    for item in index.files[:max_files]:
        lines.append(f"- `{item.path}` ({item.language}, {item.lines} lines)")
    if len(index.files) > max_files:
        lines.append(f"- ... {len(index.files) - max_files} more files")
    return "\n".join(lines).rstrip() + "\n"
