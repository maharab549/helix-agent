from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


CONTEXT_FILES = [
    "AGENTS.md",
    "HELIX.md",
    ".helix/CONTEXT.md",
    ".helix/context.md",
    "README.md",
    "pyproject.toml",
    "package.json",
]


@dataclass(frozen=True)
class ContextBlock:
    path: Path
    content: str
    truncated: bool = False

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def _read_limited(path: Path, max_chars: int) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def collect_context_blocks(
    *,
    cwd: Path | None = None,
    max_chars: int = 12000,
    per_file_chars: int = 4000,
) -> list[ContextBlock]:
    root = (cwd or Path.cwd()).resolve()
    remaining = max(0, max_chars)
    blocks: list[ContextBlock] = []
    seen: set[Path] = set()

    for relative in CONTEXT_FILES:
        if remaining <= 0:
            break
        path = (root / relative).resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        allowance = min(per_file_chars, remaining)
        content, truncated = _read_limited(path, allowance)
        blocks.append(ContextBlock(path=path, content=content.strip(), truncated=truncated))
        remaining -= len(content)

    return blocks


def format_workspace_context(
    *,
    cwd: Path | None = None,
    max_chars: int = 12000,
    per_file_chars: int = 4000,
) -> str:
    root = (cwd or Path.cwd()).resolve()
    blocks = collect_context_blocks(cwd=root, max_chars=max_chars, per_file_chars=per_file_chars)
    if not blocks:
        return ""

    lines = ["Workspace context:"]
    for block in blocks:
        suffix = " [truncated]" if block.truncated else ""
        lines.append(f"## {_display_path(block.path, root)}{suffix}")
        lines.append(block.content)
    return "\n\n".join(lines).strip()
