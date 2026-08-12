from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import AgentConfig, ProviderConfig


class ProviderError(RuntimeError):
    pass


@dataclass
class ChatResult:
    provider: str
    model: str
    content: str
    usage: dict[str, Any]
    raw: dict[str, Any]


def resolve_provider(config: AgentConfig, name: str | None, model: str | None = None) -> ProviderConfig:
    provider_name = name or config.default_provider
    provider = config.providers.get(provider_name)
    if provider is None:
        raise ProviderError(f"Unknown provider '{provider_name}'. Run `helix providers list`.")
    resolved = ProviderConfig(**provider.__dict__)
    if model:
        resolved.model = model
    return resolved


def complete(
    config: AgentConfig,
    messages: list[dict[str, str]],
    *,
    provider_name: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: int = 120,
) -> ChatResult:
    provider = resolve_provider(config, provider_name, model)
    if provider.kind == "ollama":
        return _complete_ollama(provider, messages, temperature=temperature, timeout=timeout)
    if provider.kind == "openai-compatible":
        return _complete_openai_compatible(provider, messages, temperature=temperature, timeout=timeout)
    raise ProviderError(f"Unsupported provider kind: {provider.kind}")


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str], *, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code} from provider: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach provider: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned invalid JSON") from exc


def _complete_openai_compatible(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    timeout: int,
) -> ChatResult:
    api_key = os.environ.get(provider.api_key_env) if provider.api_key_env else ""
    if provider.api_key_env and not api_key:
        raise ProviderError(
            f"{provider.name} needs {provider.api_key_env}. "
            f"Set it, run `helix auth set {provider.name} <api-key>`, "
            f"or choose `--provider ollama` for a local model."
        )
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    if provider.name == "openrouter":
        headers.update({"HTTP-Referer": "https://github.com/", "X-Title": "Helix Agent"})
    data = _request_json(
        provider.base_url,
        {"model": provider.model, "messages": messages, "temperature": temperature},
        headers,
        timeout=timeout,
    )
    try:
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"Unexpected provider response: {data}") from exc
    return ChatResult(provider.name, provider.model, content, dict(data.get("usage", {})), data)


def _complete_ollama(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    timeout: int,
) -> ChatResult:
    data = _request_json(
        provider.base_url,
        {"model": provider.model, "messages": messages, "stream": False, "options": {"temperature": temperature}},
        {},
        timeout=timeout,
    )
    try:
        content = data["message"]["content"] or ""
    except (KeyError, TypeError) as exc:
        raise ProviderError(f"Unexpected Ollama response: {data}") from exc
    usage = {
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
    }
    return ChatResult(provider.name, provider.model, content, usage, data)
