from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import app_home, project_state_dir


DEFAULT_SYSTEM_PROMPT = (
    "You are Helix Agent, a careful and capable CLI-native AI assistant. "
    "Be concise, practical, honest about uncertainty, and useful for real work."
)


@dataclass
class ProviderConfig:
    name: str
    kind: str
    model: str
    base_url: str
    api_key_env: str = ""


@dataclass
class AgentConfig:
    home: Path
    project_dir: Path
    default_provider: str = "openai"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @property
    def config_file(self) -> Path:
        return self.home / "config.json"


def default_providers() -> dict[str, ProviderConfig]:
    return {
        "openai": ProviderConfig(
            name="openai",
            kind="openai-compatible",
            model=os.environ.get("HELIX_MODEL", "gpt-4o-mini"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
            api_key_env="OPENAI_API_KEY",
        ),
        "openrouter": ProviderConfig(
            name="openrouter",
            kind="openai-compatible",
            model=os.environ.get("HELIX_MODEL", "openai/gpt-4o-mini"),
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
            api_key_env="OPENROUTER_API_KEY",
        ),
        "ollama": ProviderConfig(
            name="ollama",
            kind="ollama",
            model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/api/chat"),
            api_key_env="",
        ),
        "custom": ProviderConfig(
            name="custom",
            kind="openai-compatible",
            model=os.environ.get("HELIX_MODEL", "gpt-4o-mini"),
            base_url=os.environ.get("HELIX_BASE_URL", "https://api.openai.com/v1/chat/completions"),
            api_key_env="HELIX_API_KEY",
        ),
    }


def _provider_from_dict(name: str, data: dict[str, Any]) -> ProviderConfig:
    merged = asdict(default_providers().get(name, ProviderConfig(name, "openai-compatible", "", "", "")))
    merged.update(data)
    merged["name"] = name
    return ProviderConfig(**merged)


def load_config(*, cwd: Path | None = None) -> AgentConfig:
    home = app_home()
    project_dir = project_state_dir(cwd)
    providers = default_providers()
    config = AgentConfig(home=home, project_dir=project_dir, providers=providers)

    if config.config_file.exists():
        try:
            data = json.loads(config.config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        config.default_provider = str(data.get("default_provider", config.default_provider))
        config.system_prompt = str(data.get("system_prompt", config.system_prompt))
        for name, provider_data in dict(data.get("providers", {})).items():
            if isinstance(provider_data, dict):
                config.providers[name] = _provider_from_dict(name, provider_data)

    env_provider = os.environ.get("HELIX_PROVIDER")
    if env_provider:
        config.default_provider = env_provider
    return config


def save_config(config: AgentConfig) -> Path:
    config.home.mkdir(parents=True, exist_ok=True)
    data = {
        "default_provider": config.default_provider,
        "system_prompt": config.system_prompt,
        "providers": {name: asdict(provider) for name, provider in sorted(config.providers.items())},
    }
    config.config_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return config.config_file


def init_config(*, force: bool = False) -> Path:
    config = load_config()
    if config.config_file.exists() and not force:
        return config.config_file
    return save_config(config)


def set_config_value(config: AgentConfig, key: str, value: str) -> None:
    normalized = key.replace("-", "_")
    if normalized == "default_provider":
        if value not in config.providers:
            raise ValueError(f"Unknown provider: {value}")
        config.default_provider = value
        return
    if normalized == "system_prompt":
        config.system_prompt = value
        return

    parts = [part.replace("-", "_") for part in key.split(".")]
    if len(parts) == 3 and parts[0] == "providers":
        provider = config.providers.get(parts[1])
        if provider is None:
            provider = ProviderConfig(parts[1], "openai-compatible", "", "", "")
            config.providers[parts[1]] = provider
        if parts[2] not in {"kind", "model", "base_url", "api_key_env"}:
            raise ValueError(f"Unknown provider field: {parts[2]}")
        setattr(provider, parts[2], value)
        return
    raise ValueError(f"Unknown config key: {key}")
