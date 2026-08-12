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
        return self.home / "config.toml"

    @property
    def legacy_config_file(self) -> Path:
        return self.home / "config.json"

    @property
    def auth_file(self) -> Path:
        return self.home / "auth.json"

    @property
    def project_config_file(self) -> Path:
        return self.project_dir / "config.toml"


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


def _strip_toml_comment(line: str) -> str:
    quote = ""
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quote:
            if char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _parse_toml_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_toml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    section: dict[str, Any] = data
    for raw_line in text.splitlines():
        line = _strip_toml_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = data
            for part in line[1:-1].split("."):
                clean = part.strip()
                if not clean:
                    section = data
                    break
                existing = section.setdefault(clean, {})
                if not isinstance(existing, dict):
                    existing = {}
                    section[clean] = existing
                section = existing
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        section[key.strip().replace("-", "_")] = _parse_toml_value(raw_value)
    return data


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore[import-not-found]

        return tomllib.loads(text)
    except ModuleNotFoundError:
        return _parse_toml(text)
    except Exception:
        return {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _merge_config_data(config: AgentConfig, data: dict[str, Any]) -> None:
    default_provider = data.get("default_provider", data.get("default-provider"))
    if default_provider:
        config.default_provider = str(default_provider)
    system_prompt = data.get("system_prompt", data.get("system-prompt"))
    if system_prompt:
        config.system_prompt = str(system_prompt)
    for name, provider_data in dict(data.get("providers", {})).items():
        if isinstance(provider_data, dict):
            normalized = {str(key).replace("-", "_"): value for key, value in provider_data.items()}
            config.providers[str(name)] = _provider_from_dict(str(name), normalized)


def load_config(*, cwd: Path | None = None, include_project: bool = True) -> AgentConfig:
    home = app_home()
    project_dir = project_state_dir(cwd)
    providers = default_providers()
    config = AgentConfig(home=home, project_dir=project_dir, providers=providers)

    _merge_config_data(config, _load_json(config.legacy_config_file))
    _merge_config_data(config, _load_toml(config.config_file))
    if include_project:
        _merge_config_data(config, _load_toml(config.project_config_file))

    env_provider = os.environ.get("HELIX_PROVIDER")
    if env_provider:
        config.default_provider = env_provider
    return config


def save_config(config: AgentConfig) -> Path:
    config.home.mkdir(parents=True, exist_ok=True)
    config.config_file.write_text(config_to_toml(config, header="Helix user configuration"), encoding="utf-8")
    return config.config_file


def _toml_quote(value: Any) -> str:
    return json.dumps(str(value))


def config_to_toml(config: AgentConfig, *, header: str) -> str:
    lines = [
        f"# {header}",
        "# Do not put API keys here. Store them in auth.json or environment variables.",
        f"default_provider = {_toml_quote(config.default_provider)}",
        f"system_prompt = {_toml_quote(config.system_prompt)}",
        "",
    ]
    for name, provider in sorted(config.providers.items()):
        lines.extend([
            f"[providers.{name}]",
            f"kind = {_toml_quote(provider.kind)}",
            f"model = {_toml_quote(provider.model)}",
            f"base_url = {_toml_quote(provider.base_url)}",
            f"api_key_env = {_toml_quote(provider.api_key_env)}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def save_project_config(config: AgentConfig, *, cwd: Path | None = None) -> Path:
    project_dir = project_state_dir(cwd)
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "config.toml"
    path.write_text(config_to_toml(config, header="Helix project configuration"), encoding="utf-8")
    return path


def init_project_config(*, cwd: Path | None = None, force: bool = False) -> Path:
    project_dir = project_state_dir(cwd)
    path = project_dir / "config.toml"
    if path.exists() and not force:
        return path
    project_dir.mkdir(parents=True, exist_ok=True)
    text = "\n".join([
        "# Helix project configuration",
        "# Project settings override ~/.helix-agent/config.toml for this repo.",
        "# Do not put API keys here. Use ~/.helix-agent/auth.json or environment variables.",
        "",
        '# default_provider = "openai"',
        "",
        "# [providers.openai]",
        '# model = "gpt-4o-mini"',
        '# base_url = "https://api.openai.com/v1/chat/completions"',
        "",
    ])
    path.write_text(text, encoding="utf-8")
    return path


def init_config(*, force: bool = False) -> Path:
    config = load_config(include_project=False)
    if config.config_file.exists() and not force:
        return config.config_file
    return save_config(config)


def _auth_template(config: AgentConfig) -> dict[str, Any]:
    providers = {
        name: {"api_key": ""}
        for name, provider in sorted(config.providers.items())
        if provider.api_key_env
    }
    return {
        "version": 1,
        "providers": providers,
        "env": {},
    }


def init_auth_file(config: AgentConfig | None = None, *, force: bool = False) -> Path:
    config = config or load_config(include_project=False)
    if config.auth_file.exists() and not force:
        return config.auth_file
    config.home.mkdir(parents=True, exist_ok=True)
    config.auth_file.write_text(json.dumps(_auth_template(config), indent=2) + "\n", encoding="utf-8")
    try:
        config.auth_file.chmod(0o600)
    except OSError:
        pass
    return config.auth_file


def _auth_key_for_provider(data: dict[str, Any], provider_name: str) -> str:
    providers = data.get("providers", {})
    if isinstance(providers, dict):
        provider_data = providers.get(provider_name, {})
        if isinstance(provider_data, dict):
            api_key = provider_data.get("api_key", "")
            if api_key:
                return str(api_key)
    legacy_provider_data = data.get(provider_name, {})
    if isinstance(legacy_provider_data, dict):
        api_key = legacy_provider_data.get("api_key", "")
        if api_key:
            return str(api_key)
    return ""


def auth_environment(config: AgentConfig) -> dict[str, str]:
    data = _load_json(config.auth_file)
    env: dict[str, str] = {}
    raw_env = data.get("env", {})
    if isinstance(raw_env, dict):
        for key, value in raw_env.items():
            if value:
                env[str(key)] = str(value)
    for name, provider in config.providers.items():
        if not provider.api_key_env:
            continue
        api_key = _auth_key_for_provider(data, name)
        if api_key:
            env[provider.api_key_env] = api_key
    return env


def apply_auth_file(config: AgentConfig, *, overwrite: bool = False) -> dict[str, str]:
    applied: dict[str, str] = {}
    for key, value in auth_environment(config).items():
        if overwrite or not os.environ.get(key):
            os.environ[key] = value
            applied[key] = value
    return applied


def save_auth_key(config: AgentConfig, provider_name: str, api_key: str) -> Path:
    provider = config.providers.get(provider_name)
    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")
    if not provider.api_key_env:
        raise ValueError(f"{provider_name} does not use an API key")
    data = _load_json(config.auth_file)
    if not data:
        data = _auth_template(config)
    data["version"] = data.get("version", 1)
    providers = data.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        data["providers"] = providers
    providers[provider_name] = {"api_key": api_key}
    config.home.mkdir(parents=True, exist_ok=True)
    config.auth_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        config.auth_file.chmod(0o600)
    except OSError:
        pass
    return config.auth_file


def auth_status(config: AgentConfig) -> dict[str, Any]:
    auth_env = auth_environment(config)
    providers: dict[str, Any] = {}
    for name, provider in sorted(config.providers.items()):
        if not provider.api_key_env:
            providers[name] = {
                "api_key_env": "",
                "auth_json": False,
                "environment": True,
                "available": True,
            }
            continue
        from_auth = provider.api_key_env in auth_env
        from_env = bool(os.environ.get(provider.api_key_env))
        providers[name] = {
            "api_key_env": provider.api_key_env,
            "auth_json": from_auth,
            "environment": from_env,
            "available": from_auth or from_env,
        }
    return {
        "auth_file": str(config.auth_file),
        "providers": providers,
    }


def setup_paths(config: AgentConfig) -> dict[str, str]:
    return {
        "user_config": str(config.config_file),
        "legacy_user_config": str(config.legacy_config_file),
        "auth": str(config.auth_file),
        "project_config": str(config.project_config_file),
    }


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
