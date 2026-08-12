from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import project_state_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Session:
    id: str
    name: str
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    provider: str = ""
    model: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def sessions_dir(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "sessions"


def session_file(session_id: str, *, cwd: Path | None = None) -> Path:
    return sessions_dir(cwd=cwd) / f"{session_id}.json"


def create_session(name: str = "session", *, cwd: Path | None = None) -> Session:
    session_id = uuid.uuid4().hex[:12]
    session = Session(id=session_id, name=name)
    save_session(session, cwd=cwd)
    return session


def save_session(session: Session, *, cwd: Path | None = None) -> Path:
    sessions_dir(cwd=cwd).mkdir(parents=True, exist_ok=True)
    session.updated_at = now_iso()
    out = session_file(session.id, cwd=cwd)
    out.write_text(json.dumps(session.to_json(), indent=2) + "\n", encoding="utf-8")
    return out


def load_session(selector: str, *, cwd: Path | None = None) -> Session:
    for session in list_sessions(cwd=cwd):
        if session.id.startswith(selector) or session.name == selector:
            return session
    path = session_file(selector, cwd=cwd)
    if path.exists():
        return Session(**json.loads(path.read_text(encoding="utf-8")))
    raise FileNotFoundError(f"No session found for {selector!r}")


def list_sessions(*, cwd: Path | None = None) -> list[Session]:
    directory = sessions_dir(cwd=cwd)
    if not directory.exists():
        return []
    sessions: list[Session] = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            sessions.append(Session(**json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return sessions


def append_message(session: Session, role: str, content: str) -> None:
    session.messages.append({"role": role, "content": content})


def export_markdown(session: Session) -> str:
    lines = [f"# {session.name}", "", f"- Session: `{session.id}`", f"- Created: {session.created_at}", ""]
    for message in session.messages:
        role = message.get("role", "message").title()
        content = message.get("content", "")
        lines.extend([f"## {role}", "", content, ""])
    return "\n".join(lines).rstrip() + "\n"
