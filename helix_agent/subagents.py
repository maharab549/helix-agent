from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .config import AgentConfig
from .provider import ProviderError, complete


@dataclass
class SubagentResult:
    name: str
    prompt: str
    ok: bool
    content: str


def run_subagents(
    config: AgentConfig,
    tasks: list[tuple[str, str]],
    *,
    provider_name: str | None = None,
    model: str | None = None,
    timeout: int = 120,
) -> list[SubagentResult]:
    def run_one(name: str, prompt: str) -> SubagentResult:
        messages = [
            {
                "role": "system",
                "content": "You are a focused Helix subagent. Answer only your assigned task with concrete findings.",
            },
            {"role": "user", "content": prompt},
        ]
        try:
            result = complete(config, messages, provider_name=provider_name, model=model, timeout=timeout)
        except ProviderError as exc:
            return SubagentResult(name, prompt, False, str(exc))
        return SubagentResult(name, prompt, True, result.content)

    results: list[SubagentResult] = []
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(tasks)))) as executor:
        futures = [executor.submit(run_one, name, prompt) for name, prompt in tasks]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item.name)
    return results
