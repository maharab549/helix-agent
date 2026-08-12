from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .paths import app_home, package_root, project_state_dir


@dataclass(frozen=True)
class SkillEntry:
    name: str
    description: str
    source: str
    path: Path
    category: str

    def to_json(self) -> dict[str, str]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_skill_file(path: Path, *, source: str, root: Path) -> SkillEntry | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    frontmatter: dict[str, str] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for raw_line in parts[1].splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                if key.strip() in {"name", "description"}:
                    frontmatter[key.strip()] = _strip_quotes(value)

    name = frontmatter.get("name") or path.parent.name
    description = frontmatter.get("description")
    if not description:
        return None
    try:
        relative_parent = path.parent.relative_to(root)
        category = str(relative_parent.parent).replace("\\", "/") or "."
    except ValueError:
        category = "."
    return SkillEntry(name, description, source, path.parent, category)


def iter_skill_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("SKILL.md")


def load_skill_index(*, cwd: Path | None = None, sources: set[str] | None = None) -> list[SkillEntry]:
    selected = sources or {"built-in", "user", "project"}
    roots: list[tuple[str, Path]] = []
    if "built-in" in selected:
        roots.append(("built-in", package_root() / "skills"))
    if "user" in selected:
        roots.append(("user", app_home() / "skills"))
    if "project" in selected:
        roots.append(("project", project_state_dir(cwd) / "skills"))

    entries: list[SkillEntry] = []
    seen: set[tuple[str, str]] = set()
    for source, root in roots:
        for file_path in iter_skill_files(root):
            entry = parse_skill_file(file_path, source=source, root=root)
            if entry is None:
                continue
            key = (entry.source, str(entry.path.resolve()).lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    entries.sort(key=lambda item: (item.source, item.category, item.name))
    return entries


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())


def score_skill(entry: SkillEntry, query: str) -> int:
    terms = tokenize(query)
    if not terms:
        return 0
    haystacks = {
        "name": entry.name.lower(),
        "description": entry.description.lower(),
        "category": entry.category.lower(),
    }
    score = 0
    for term in terms:
        if term == entry.name.lower():
            score += 25
        if term in haystacks["name"]:
            score += 12
        if term in haystacks["description"]:
            score += 5
        if term in haystacks["category"]:
            score += 3
    return score


def search_skills(entries: Iterable[SkillEntry], query: str, *, limit: int = 10) -> list[SkillEntry]:
    ranked = [(score_skill(entry, query), entry) for entry in entries]
    ranked = [(score, entry) for score, entry in ranked if score > 0]
    ranked.sort(key=lambda pair: (-pair[0], pair[1].source, pair[1].name))
    return [entry for _, entry in ranked[:limit]]


def find_skill(entries: Iterable[SkillEntry], name_or_query: str, *, source: str | None = None) -> SkillEntry | None:
    narrowed = [entry for entry in entries if source is None or entry.source == source]
    lowered = name_or_query.lower()
    for entry in narrowed:
        if entry.name.lower() == lowered:
            return entry
    results = search_skills(narrowed, name_or_query, limit=1)
    return results[0] if results else None


def read_skill(entry: SkillEntry) -> str:
    return (entry.path / "SKILL.md").read_text(encoding="utf-8", errors="replace")


def create_project_skill(name: str, description: str, body: str, *, cwd: Path | None = None) -> Path:
    skill_dir = project_state_dir(cwd) / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = f"---\nname: {name}\ndescription: {description}\n---\n\n{body.strip()}\n"
    out = skill_dir / "SKILL.md"
    out.write_text(text, encoding="utf-8")
    return out


def save_index(entries: list[SkillEntry], *, cwd: Path | None = None) -> Path:
    cache_dir = project_state_dir(cwd) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / "skills.json"
    out.write_text(json.dumps([entry.to_json() for entry in entries], indent=2) + "\n", encoding="utf-8")
    return out
