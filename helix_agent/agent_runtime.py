from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import AgentConfig
from .context import format_workspace_context
from .memory import format_memory_context
from .provider import ChatResult, complete
from .sessions import Session, append_message, create_session, save_session
from .skills import find_skill, load_skill_index, read_skill
from .tools_runtime import execute_tool, parse_tool_calls, strip_tool_calls, tools_system_prompt


@dataclass
class AgentRunResult:
    content: str
    provider: str
    model: str
    session: Session
    tool_steps: list[dict[str, str]] = field(default_factory=list)


def build_messages(
    config: AgentConfig,
    prompt: str,
    *,
    system: str | None = None,
    skill_queries: list[str] | None = None,
    include_tools: bool = False,
    include_memory: bool = True,
    include_context: bool = True,
    cwd: Path | None = None,
) -> list[dict[str, str]]:
    root = cwd or Path.cwd()
    system_parts = [system or config.system_prompt]
    if include_context:
        workspace_context = format_workspace_context(cwd=root)
        if workspace_context:
            system_parts.append(workspace_context)
    if include_memory:
        memory_context = format_memory_context(prompt, cwd=root)
        if memory_context:
            system_parts.append(memory_context)
    if include_tools:
        system_parts.append(tools_system_prompt(cwd=root))
    entries = load_skill_index()
    for query in skill_queries or []:
        entry = find_skill(entries, query)
        if entry:
            system_parts.append(f"Skill: {entry.name}\n{read_skill(entry)}")
    return [{"role": "system", "content": "\n\n".join(system_parts)}, {"role": "user", "content": prompt}]


def run_agent_loop(
    config: AgentConfig,
    prompt: str,
    *,
    provider_name: str | None = None,
    model: str | None = None,
    system: str | None = None,
    skill_queries: list[str] | None = None,
    temperature: float = 0.2,
    timeout: int = 120,
    max_steps: int = 6,
    allow_write: bool = False,
    allow_shell: bool = False,
    session: Session | None = None,
    save: bool = True,
) -> AgentRunResult:
    active_session = session or create_session("agent-run")
    messages = build_messages(
        config,
        prompt,
        system=system,
        skill_queries=skill_queries,
        include_tools=True,
        include_memory=True,
    )
    tool_steps: list[dict[str, str]] = []
    final: ChatResult | None = None
    for _ in range(max_steps):
        final = complete(
            config,
            messages,
            provider_name=provider_name,
            model=model,
            temperature=temperature,
            timeout=timeout,
        )
        calls = parse_tool_calls(final.content)
        visible = strip_tool_calls(final.content)
        if visible:
            messages.append({"role": "assistant", "content": visible})
        else:
            messages.append({"role": "assistant", "content": final.content})
        if not calls:
            break
        for call in calls:
            result = execute_tool(
                call["tool"],
                call["args"],
                cwd=Path.cwd(),
                allow_write=allow_write,
                allow_shell=allow_shell,
            )
            tool_steps.append({"tool": call["tool"], "ok": str(result.ok), "output": result.output})
            messages.append({"role": "user", "content": result.to_message()})
    else:
        messages.append({"role": "user", "content": "Tool step limit reached. Provide the best final answer now."})
        final = complete(config, messages, provider_name=provider_name, model=model, temperature=temperature, timeout=timeout)
        messages.append({"role": "assistant", "content": final.content})

    content = strip_tool_calls(messages[-1]["content"])
    for message in messages:
        append_message(active_session, message["role"], message["content"])
    if final:
        active_session.provider = final.provider
        active_session.model = final.model
    if save:
        save_session(active_session)
    return AgentRunResult(
        content=content,
        provider=final.provider if final else "",
        model=final.model if final else "",
        session=active_session,
        tool_steps=tool_steps,
    )
