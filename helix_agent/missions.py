from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import project_state_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return lowered[:60] or "mission"


@dataclass
class Mission:
    name: str
    objective: str
    status: str = "draft"
    workspace: str = ""
    gates: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def missions_dir(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "missions"


def mission_file(name: str, *, cwd: Path | None = None) -> Path:
    return missions_dir(cwd=cwd) / f"{name}.json"


def load_mission(name: str, *, cwd: Path | None = None) -> Mission:
    data = json.loads(mission_file(name, cwd=cwd).read_text(encoding="utf-8"))
    return Mission(**data)


def save_mission(mission: Mission, *, cwd: Path | None = None) -> Path:
    missions_dir(cwd=cwd).mkdir(parents=True, exist_ok=True)
    mission.updated_at = now_iso()
    out = mission_file(mission.name, cwd=cwd)
    out.write_text(json.dumps(mission.to_json(), indent=2) + "\n", encoding="utf-8")
    return out


def list_missions(*, cwd: Path | None = None) -> list[Mission]:
    directory = missions_dir(cwd=cwd)
    if not directory.exists():
        return []
    result: list[Mission] = []
    for file_path in sorted(directory.glob("*.json")):
        try:
            result.append(Mission(**json.loads(file_path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return result


def create_mission(
    objective: str,
    *,
    name: str | None = None,
    workspace: str | None = None,
    gates: list[str] | None = None,
    cwd: Path | None = None,
) -> Mission:
    base_name = slugify(name or objective)
    candidate = base_name
    index = 2
    while mission_file(candidate, cwd=cwd).exists():
        candidate = f"{base_name}-{index}"
        index += 1
    mission = Mission(
        name=candidate,
        objective=objective,
        workspace=workspace or str(Path.cwd()),
        gates=gates or [],
    )
    save_mission(mission, cwd=cwd)
    return mission


def build_mission_prompt(mission: Mission) -> str:
    gates = "\n".join(f"- {gate}" for gate in mission.gates) if mission.gates else "- No explicit gates were supplied."
    notes = "\n".join(f"- {note}" for note in mission.notes) if mission.notes else "- No saved mission notes yet."
    return f"""Mission: {mission.name}
Objective: {mission.objective}
Workspace: {mission.workspace}

Work like a careful CLI-native agent:
- Clarify uncertainty only when it blocks progress.
- Break down the work into a short plan.
- Prefer concrete commands, files, tests, and verification steps.
- Keep the answer useful even if external tools are unavailable.

Gates:
{gates}

Notes:
{notes}
"""
