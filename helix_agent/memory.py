from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .paths import app_home, project_state_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class MemoryEntry:
    text: str
    scope: str = "project"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def memory_file(scope: str = "project", *, cwd: Path | None = None) -> Path:
    if scope == "global":
        return app_home() / "memory.jsonl"
    return project_state_dir(cwd) / "memory.jsonl"


def remember(text: str, *, scope: str = "project", tags: list[str] | None = None, cwd: Path | None = None) -> Path:
    entry = MemoryEntry(text=text, scope=scope, tags=tags or [])
    out = memory_file(scope, cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_json(), ensure_ascii=False) + "\n")
    return out


def iter_memories(*, scopes: Iterable[str] = ("project", "global"), cwd: Path | None = None) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for scope in scopes:
        path = memory_file(scope, cwd=cwd)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(MemoryEntry(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
    entries.sort(key=lambda item: item.created_at, reverse=True)
    return entries


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9-]*", text.lower()))


def search_memories(query: str, *, limit: int = 10, cwd: Path | None = None) -> list[MemoryEntry]:
    terms = _tokens(query)
    if not terms:
        return iter_memories(cwd=cwd)[:limit]
    scored: list[tuple[int, MemoryEntry]] = []
    for entry in iter_memories(cwd=cwd):
        hay = _tokens(" ".join([entry.text, *entry.tags]))
        score = len(terms & hay)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1].created_at), reverse=False)
    return [entry for _, entry in scored[:limit]]


def format_memory_context(query: str, *, limit: int = 6, cwd: Path | None = None) -> str:
    entries = search_memories(query, limit=limit, cwd=cwd)
    if not entries:
        return ""
    lines = ["Relevant memory:"]
    for entry in entries:
        tag_text = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        lines.append(f"- ({entry.scope}){tag_text} {entry.text}")
    return "\n".join(lines)
