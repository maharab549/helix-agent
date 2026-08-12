from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import project_state_dir


def history_dir(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "history"


def save_exchange(
    messages: list[dict[str, str]],
    response: str,
    *,
    provider: str,
    model: str,
    cwd: Path | None = None,
) -> Path:
    directory = history_dir(cwd=cwd)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = directory / f"{stamp}.json"
    data: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "provider": provider,
        "model": model,
        "messages": messages,
        "response": response,
    }
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def list_history(*, cwd: Path | None = None, limit: int = 20) -> list[Path]:
    directory = history_dir(cwd=cwd)
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), reverse=True)[:limit]
