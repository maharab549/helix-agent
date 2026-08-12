from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = ".helix-agent"
PROJECT_DIR_NAME = ".helix"


def package_root() -> Path:
    return Path(__file__).resolve().parent


def app_home() -> Path:
    override = os.environ.get("HELIX_HOME")
    if override:
        return normalize_path(override)
    return Path.home() / APP_DIR_NAME


def project_state_dir(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()).resolve() / PROJECT_DIR_NAME


def normalize_path(value: str | os.PathLike[str], *, base: Path | None = None) -> Path:
    text = os.fspath(value)
    if text == "~":
        return Path.home()
    if text.startswith("~/") or text.startswith("~\\"):
        return Path.home() / text[2:]
    path = Path(text)
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()
