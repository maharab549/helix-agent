from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from typing import Any

from .config import AgentConfig


def _version(command: str) -> str | None:
    resolved = shutil.which(command)
    if not resolved:
        return None
    try:
        result = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else None


def _ollama_available(base_url: str) -> bool:
    if "/api/chat" not in base_url:
        return False
    url = base_url.split("/api/chat", 1)[0] + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status < 500
    except OSError:
        return False


def collect_diagnostics(config: AgentConfig) -> dict[str, Any]:
    providers: dict[str, Any] = {}
    for name, provider in sorted(config.providers.items()):
        has_key = bool(os.environ.get(provider.api_key_env)) if provider.api_key_env else True
        providers[name] = {
            "kind": provider.kind,
            "model": provider.model,
            "base_url": provider.base_url,
            "api_key_env": provider.api_key_env,
            "api_key_available": has_key,
            "local_server_available": _ollama_available(provider.base_url) if provider.kind == "ollama" else None,
        }

    return {
        "home": str(config.home),
        "project_dir": str(config.project_dir),
        "default_provider": config.default_provider,
        "tools": {
            "python": _version("python"),
            "git": _version("git"),
            "rg": _version("rg"),
        },
        "providers": providers,
    }
