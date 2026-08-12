from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .agent_runtime import build_messages as build_agent_messages
from .agent_runtime import run_agent_loop
from .capabilities import capability_report
from .config import init_config, load_config, save_config, set_config_value
from .context import collect_context_blocks, format_workspace_context
from .doctor import collect_diagnostics
from .history import list_history, save_exchange
from .memory import iter_memories, remember, search_memories
from .missions import build_mission_prompt, create_mission, list_missions, load_mission, save_mission
from .output import Palette, format_table, print_json
from .plugins import PluginError, create_project_plugin, execute_plugin_tool, find_plugin, load_plugin_tools, load_plugins
from .provider import ProviderError, complete
from .rpc import run_rpc
from .scheduler import add_job, load_jobs, remove_job, run_due_jobs
from .sessions import create_session, export_markdown, list_sessions, load_session
from .skills import create_project_skill, find_skill, load_skill_index, read_skill, save_index, search_skills
from .subagents import run_subagents
from .tools_runtime import TOOL_DESCRIPTIONS, execute_tool


COMMANDS = {
    "agent",
    "ask",
    "capabilities",
    "chat",
    "completion",
    "config",
    "context",
    "doctor",
    "history",
    "init",
    "memory",
    "mission",
    "plugins",
    "providers",
    "rpc",
    "schedule",
    "sessions",
    "skills",
    "subagents",
    "tools",
    "version",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helix", description="Helix Agent: a standalone CLI AI agent.")
    parser.add_argument("--json", action="store_true", help="Print JSON when supported")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")

    ask = sub.add_parser("ask", help="Ask a one-shot prompt")
    add_model_options(ask)
    ask.add_argument("--system", default=None, help="Override system prompt")
    ask.add_argument("--skill", action="append", default=[], help="Load a matching skill into context")
    ask.add_argument("--temperature", type=float, default=0.2)
    ask.add_argument("--timeout", type=int, default=120)
    ask.add_argument("--no-save", action="store_true")
    ask.add_argument("prompt", nargs=argparse.REMAINDER)

    agent = sub.add_parser("agent", help="Run an autonomous local-tool loop")
    add_model_options(agent)
    agent.add_argument("--system", default=None)
    agent.add_argument("--skill", action="append", default=[])
    agent.add_argument("--temperature", type=float, default=0.2)
    agent.add_argument("--timeout", type=int, default=120)
    agent.add_argument("--max-steps", type=int, default=6)
    agent.add_argument("--yes", action="store_true", help="Allow file writes and shell/python execution")
    agent.add_argument("--no-save", action="store_true")
    agent.add_argument("prompt", nargs=argparse.REMAINDER)

    chat = sub.add_parser("chat", help="Start an interactive chat")
    add_model_options(chat)
    chat.add_argument("--system", default=None)
    chat.add_argument("--temperature", type=float, default=0.2)

    capabilities = sub.add_parser("capabilities", help="Show what makes Helix different")
    capabilities.add_argument("--json", action="store_true")

    config = sub.add_parser("config", help="Show or update config")
    config_sub = config.add_subparsers(dest="config_command")
    config_sub.add_parser("show")
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")

    providers = sub.add_parser("providers", help="List providers")
    providers_sub = providers.add_subparsers(dest="providers_command")
    providers_sub.add_parser("list")

    context = sub.add_parser("context", help="Show workspace context Helix will load")
    context_sub = context.add_subparsers(dest="context_command")
    context_show = context_sub.add_parser("show")
    context_show.add_argument("--max-chars", type=int, default=12000)
    context_show.add_argument("--json", action="store_true")

    skills = sub.add_parser("skills", help="List, search, show, or create skills")
    skills_sub = skills.add_subparsers(dest="skills_command")
    skills_list = skills_sub.add_parser("list")
    skills_list.add_argument("--limit", type=int, default=80)
    skills_list.add_argument("--json", action="store_true")
    skills_list.add_argument("--save-index", action="store_true")
    skills_search = skills_sub.add_parser("search")
    skills_search.add_argument("--limit", type=int, default=10)
    skills_search.add_argument("--json", action="store_true")
    skills_search.add_argument("query", nargs="+")
    skills_show = skills_sub.add_parser("show")
    skills_show.add_argument("query", nargs="+")
    skills_create = skills_sub.add_parser("create")
    skills_create.add_argument("name")
    skills_create.add_argument("description")
    skills_create.add_argument("body", nargs=argparse.REMAINDER)

    mission = sub.add_parser("mission", help="Create and run missions")
    mission_sub = mission.add_subparsers(dest="mission_command")
    mission_create = mission_sub.add_parser("create")
    mission_create.add_argument("--name", default=None)
    mission_create.add_argument("--workspace", default=None)
    mission_create.add_argument("--gate", action="append", default=[])
    mission_create.add_argument("objective", nargs=argparse.REMAINDER)
    mission_sub.add_parser("list")
    mission_show = mission_sub.add_parser("show")
    mission_show.add_argument("name")
    mission_run = mission_sub.add_parser("run")
    add_model_options(mission_run)
    mission_run.add_argument("--dry-run", action="store_true")
    mission_run.add_argument("--timeout", type=int, default=120)
    mission_run.add_argument("name")
    mission_note = mission_sub.add_parser("note")
    mission_note.add_argument("name")
    mission_note.add_argument("note", nargs=argparse.REMAINDER)

    history = sub.add_parser("history", help="List saved exchanges")
    history.add_argument("--limit", type=int, default=20)

    sessions = sub.add_parser("sessions", help="Manage persistent chat sessions")
    sessions_sub = sessions.add_subparsers(dest="sessions_command")
    sessions_sub.add_parser("list")
    sessions_new = sessions_sub.add_parser("new")
    sessions_new.add_argument("name", nargs="?", default="session")
    sessions_show = sessions_sub.add_parser("show")
    sessions_show.add_argument("selector")
    sessions_export = sessions_sub.add_parser("export")
    sessions_export.add_argument("selector")
    sessions_export.add_argument("output", nargs="?")

    memory = sub.add_parser("memory", help="Remember and recall useful facts")
    memory_sub = memory.add_subparsers(dest="memory_command")
    memory_add = memory_sub.add_parser("add")
    memory_add.add_argument("--global", dest="global_scope", action="store_true")
    memory_add.add_argument("--tag", action="append", default=[])
    memory_add.add_argument("text", nargs=argparse.REMAINDER)
    memory_search = memory_sub.add_parser("search")
    memory_search.add_argument("--limit", type=int, default=10)
    memory_search.add_argument("query", nargs=argparse.REMAINDER)
    memory_sub.add_parser("list")

    tools = sub.add_parser("tools", help="Inspect and run local tools")
    tools_sub = tools.add_subparsers(dest="tools_command")
    tools_sub.add_parser("list")
    tools_run = tools_sub.add_parser("run")
    tools_run.add_argument("--yes", action="store_true", help="Allow write/shell/python tools")
    tools_run.add_argument("tool")
    tools_run.add_argument("args_json", nargs="?")

    plugins = sub.add_parser("plugins", help="Manage Helix plugins")
    plugins_sub = plugins.add_subparsers(dest="plugins_command")
    plugins_list = plugins_sub.add_parser("list")
    plugins_list.add_argument("--json", action="store_true")
    plugins_tools = plugins_sub.add_parser("tools")
    plugins_tools.add_argument("--json", action="store_true")
    plugins_show = plugins_sub.add_parser("show")
    plugins_show.add_argument("name")
    plugins_create = plugins_sub.add_parser("create")
    plugins_create.add_argument("name")
    plugins_create.add_argument("description", nargs=argparse.REMAINDER)
    plugins_run = plugins_sub.add_parser("run")
    plugins_run.add_argument("--yes", action="store_true", help="Required to execute plugin commands")
    plugins_run.add_argument("tool")
    plugins_run.add_argument("args_json", nargs="?")

    subagents = sub.add_parser("subagents", help="Run parallel focused subagents")
    add_model_options(subagents)
    subagents.add_argument("--task", action="append", default=[], help="name=prompt; repeatable")
    subagents.add_argument("--timeout", type=int, default=120)
    subagents.add_argument("prompt", nargs=argparse.REMAINDER)

    schedule = sub.add_parser("schedule", help="Manage recurring prompts")
    schedule_sub = schedule.add_subparsers(dest="schedule_command")
    schedule_sub.add_parser("list")
    schedule_add = schedule_sub.add_parser("add")
    add_model_options(schedule_add)
    schedule_add.add_argument("--every", type=int, required=True, help="Interval in seconds")
    schedule_add.add_argument("prompt", nargs=argparse.REMAINDER)
    schedule_run = schedule_sub.add_parser("run")
    schedule_run.add_argument("--force", action="store_true")
    schedule_run.add_argument("--timeout", type=int, default=120)
    schedule_remove = schedule_sub.add_parser("remove")
    schedule_remove.add_argument("selector")

    doctor = sub.add_parser("doctor", help="Check local readiness")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--fix", action="store_true")

    init = sub.add_parser("init", help="Create user config and project folders")
    init.add_argument("--force", action="store_true")

    completion = sub.add_parser("completion")
    completion.add_argument("shell", choices=["bash", "zsh", "powershell"])
    sub.add_parser("rpc", help="Run JSONL RPC on stdin/stdout")
    sub.add_parser("version")
    return parser


def add_model_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)


def preprocess_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["chat"]
    if argv[0].startswith("-"):
        return argv
    if argv[0] not in COMMANDS:
        return ["ask", *argv]
    return argv


def clean_remainder(args: Sequence[str]) -> list[str]:
    result = list(args)
    return result[1:] if result and result[0] == "--" else result


def prompt_from_parts(parts: Sequence[str]) -> str:
    return " ".join(clean_remainder(parts)).strip()


def build_messages(config, prompt: str, *, system: str | None, skill_queries: list[str]) -> list[dict[str, str]]:
    return build_agent_messages(
        config,
        prompt,
        system=system,
        skill_queries=skill_queries,
        include_tools=False,
        include_memory=True,
        include_context=True,
    )


def run_ask(config, ns, palette: Palette) -> int:
    prompt = prompt_from_parts(ns.prompt)
    if not prompt:
        print("Usage: helix ask <prompt>", file=sys.stderr)
        return 2
    messages = build_messages(config, prompt, system=ns.system, skill_queries=ns.skill)
    try:
        result = complete(
            config,
            messages,
            provider_name=ns.provider,
            model=ns.model,
            temperature=ns.temperature,
            timeout=ns.timeout,
        )
    except ProviderError as exc:
        print(palette.red(str(exc)), file=sys.stderr)
        return 1
    if getattr(ns, "json", False):
        print_json(result)
    else:
        print(result.content)
    if not ns.no_save:
        save_exchange(messages, result.content, provider=result.provider, model=result.model)
    return 0


def run_agent(config, ns, palette: Palette) -> int:
    prompt = prompt_from_parts(ns.prompt)
    if not prompt:
        print("Usage: helix agent <prompt>", file=sys.stderr)
        return 2
    try:
        result = run_agent_loop(
            config,
            prompt,
            provider_name=ns.provider,
            model=ns.model,
            system=ns.system,
            skill_queries=ns.skill,
            temperature=ns.temperature,
            timeout=ns.timeout,
            max_steps=ns.max_steps,
            allow_write=ns.yes,
            allow_shell=ns.yes,
            save=not ns.no_save,
        )
    except ProviderError as exc:
        print(palette.red(str(exc)), file=sys.stderr)
        return 1
    if result.tool_steps:
        print(palette.dim(f"Tool steps: {len(result.tool_steps)}"))
        for step in result.tool_steps:
            print(palette.dim(f"- {step['tool']}: {'ok' if step['ok'] == 'True' else 'error'}"))
    print(result.content)
    print(palette.dim(f"Session: {result.session.id}"))
    return 0


def run_chat(config, ns, palette: Palette) -> int:
    messages = [{"role": "system", "content": ns.system or config.system_prompt}]
    provider = ns.provider
    model = ns.model
    print(palette.bold("Helix Agent"))
    print(palette.dim("Type /help for commands, /exit to quit."))
    while True:
        try:
            user_text = input(palette.cyan("you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_text:
            continue
        if user_text.startswith("/"):
            if handle_chat_command(user_text, messages, config, palette):
                continue
            if user_text in {"/exit", "/quit"}:
                return 0
            continue
        messages.append({"role": "user", "content": user_text})
        try:
            result = complete(config, messages, provider_name=provider, model=model, temperature=ns.temperature)
        except ProviderError as exc:
            print(palette.red(str(exc)))
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": result.content})
        print(palette.green("helix> ") + result.content)
        save_exchange(messages[-3:] if len(messages) > 3 else messages, result.content, provider=result.provider, model=result.model)


def handle_chat_command(command: str, messages: list[dict[str, str]], config, palette: Palette) -> bool:
    parts = command.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if verb == "/help":
        print("/help, /exit, /clear, /context, /skills [query], /use <query>, /providers, /remember <text>, /recall [query], /tools")
        return True
    if verb == "/clear":
        del messages[1:]
        print("Conversation cleared.")
        return True
    if verb == "/providers":
        print_provider_table(config)
        return True
    if verb == "/context":
        text = format_workspace_context()
        print(text or "No workspace context files found.")
        return True
    if verb == "/tools":
        print(format_table(
            [{"name": name, "description": description} for name, description in TOOL_DESCRIPTIONS.items()],
            [("name", "Tool"), ("description", "Description")],
        ))
        return True
    if verb == "/remember" and arg:
        remember(arg)
        print("Remembered.")
        return True
    if verb == "/recall":
        entries = search_memories(arg, limit=8) if arg else iter_memories()[:8]
        print(format_table(
            [{"scope": entry.scope, "text": entry.text, "tags": ", ".join(entry.tags)} for entry in entries],
            [("scope", "Scope"), ("tags", "Tags"), ("text", "Text")],
        ))
        return True
    if verb == "/skills":
        entries = search_skills(load_skill_index(), arg, limit=8) if arg else load_skill_index()[:8]
        print_skill_table(entries)
        return True
    if verb == "/use" and arg:
        entry = find_skill(load_skill_index(), arg)
        if not entry:
            print("No matching skill.")
        else:
            messages[0]["content"] += f"\n\nSkill: {entry.name}\n{read_skill(entry)}"
            print(f"Loaded skill: {entry.name}")
        return True
    return False


def print_skill_table(entries) -> None:
    print(format_table(
        [entry.to_json() for entry in entries],
        [("source", "Source"), ("name", "Name"), ("description", "Description")],
    ))


def print_provider_table(config) -> None:
    rows = []
    for provider in config.providers.values():
        rows.append({
            "name": provider.name,
            "kind": provider.kind,
            "model": provider.model,
            "key": provider.api_key_env or "-",
        })
    print(format_table(rows, [("name", "Name"), ("kind", "Kind"), ("model", "Model"), ("key", "Key Env")]))


def run_skills(ns) -> int:
    entries = load_skill_index()
    if ns.skills_command in {None, "list"}:
        limited = entries[: getattr(ns, "limit", 80)]
        if getattr(ns, "save_index", False):
            save_index(entries)
        if getattr(ns, "json", False):
            print_json([entry.to_json() for entry in limited])
        else:
            print_skill_table(limited)
        return 0
    if ns.skills_command == "search":
        results = search_skills(entries, " ".join(ns.query), limit=ns.limit)
        if ns.json:
            print_json([entry.to_json() for entry in results])
        else:
            print_skill_table(results)
        return 0
    if ns.skills_command == "show":
        entry = find_skill(entries, " ".join(ns.query))
        if not entry:
            print("No matching skill.", file=sys.stderr)
            return 1
        print(read_skill(entry))
        return 0
    if ns.skills_command == "create":
        body = prompt_from_parts(ns.body) or "Write detailed instructions for this skill here."
        path = create_project_skill(ns.name, ns.description, body)
        print(path)
        return 0
    return 2


def run_context(ns) -> int:
    max_chars = getattr(ns, "max_chars", 12000)
    if getattr(ns, "json", False):
        print_json([block.to_json() for block in collect_context_blocks(max_chars=max_chars)])
    else:
        print(format_workspace_context(max_chars=max_chars) or "No workspace context files found.")
    return 0


def run_mission(config, ns, palette: Palette) -> int:
    if ns.mission_command == "create":
        objective = prompt_from_parts(ns.objective)
        if not objective:
            print("Mission objective is required.", file=sys.stderr)
            return 2
        mission = create_mission(objective, name=ns.name, workspace=ns.workspace, gates=ns.gate)
        print(palette.green(f"Created mission {mission.name}"))
        return 0
    if ns.mission_command in {None, "list"}:
        print(format_table(
            [mission.to_json() for mission in list_missions()],
            [("name", "Name"), ("status", "Status"), ("objective", "Objective")],
        ))
        return 0
    if ns.mission_command == "show":
        print_json(load_mission(ns.name).to_json())
        return 0
    if ns.mission_command == "note":
        mission = load_mission(ns.name)
        mission.notes.append(prompt_from_parts(ns.note))
        save_mission(mission)
        print("Saved note.")
        return 0
    if ns.mission_command == "run":
        mission = load_mission(ns.name)
        prompt = build_mission_prompt(mission)
        if ns.dry_run:
            print(prompt)
            return 0
        fake_ns = argparse.Namespace(
            prompt=[prompt],
            system=None,
            skill=[],
            provider=ns.provider,
            model=ns.model,
            temperature=0.2,
            timeout=ns.timeout,
            no_save=False,
            json=False,
        )
        rc = run_ask(config, fake_ns, palette)
        mission.status = "complete" if rc == 0 else "failed"
        save_mission(mission)
        return rc
    return 2


def run_sessions(ns) -> int:
    if ns.sessions_command in {None, "list"}:
        rows = [
            {
                "id": session.id,
                "name": session.name,
                "updated": session.updated_at,
                "messages": len(session.messages),
            }
            for session in list_sessions()
        ]
        print(format_table(rows, [("id", "ID"), ("name", "Name"), ("messages", "Messages"), ("updated", "Updated")]))
        return 0
    if ns.sessions_command == "new":
        session = create_session(ns.name)
        print_json(session.to_json())
        return 0
    if ns.sessions_command == "show":
        print_json(load_session(ns.selector).to_json())
        return 0
    if ns.sessions_command == "export":
        session = load_session(ns.selector)
        markdown = export_markdown(session)
        if ns.output:
            output = ns.output
            with open(output, "w", encoding="utf-8") as handle:
                handle.write(markdown)
            print(output)
        else:
            print(markdown)
        return 0
    return 2


def run_memory(ns) -> int:
    if ns.memory_command in {None, "list"}:
        entries = iter_memories()
    elif ns.memory_command == "add":
        text = prompt_from_parts(ns.text)
        if not text:
            print("Memory text is required.", file=sys.stderr)
            return 2
        scope = "global" if ns.global_scope else "project"
        print(remember(text, scope=scope, tags=ns.tag))
        return 0
    elif ns.memory_command == "search":
        entries = search_memories(prompt_from_parts(ns.query), limit=ns.limit)
    else:
        return 2
    print(format_table(
        [{"scope": entry.scope, "tags": ", ".join(entry.tags), "text": entry.text} for entry in entries],
        [("scope", "Scope"), ("tags", "Tags"), ("text", "Text")],
    ))
    return 0


def run_tools(ns) -> int:
    if ns.tools_command in {None, "list"}:
        print(format_table(
            [{"name": name, "description": description} for name, description in TOOL_DESCRIPTIONS.items()],
            [("name", "Tool"), ("description", "Description")],
        ))
        return 0
    if ns.tools_command == "run":
        args = json.loads(ns.args_json) if ns.args_json else {}
        if not isinstance(args, dict):
            print("Tool args must be a JSON object.", file=sys.stderr)
            return 2
        result = execute_tool(ns.tool, args, allow_write=ns.yes, allow_shell=ns.yes)
        print(result.output)
        return 0 if result.ok else 1
    return 2


def run_plugins(ns) -> int:
    if ns.plugins_command in {None, "list"}:
        plugins = load_plugins()
        if getattr(ns, "json", False):
            print_json([plugin.to_json() for plugin in plugins])
        else:
            rows = [
                {
                    "source": plugin.source,
                    "name": plugin.name,
                    "version": plugin.version,
                    "tools": len(plugin.tools),
                    "description": plugin.description,
                }
                for plugin in plugins
            ]
            print(format_table(rows, [("source", "Source"), ("name", "Name"), ("version", "Version"), ("tools", "Tools"), ("description", "Description")]))
        return 0
    if ns.plugins_command == "tools":
        tools = load_plugin_tools()
        if ns.json:
            print_json([tool.to_json() for tool in tools])
        else:
            rows = [
                {"source": tool.source, "tool": tool.full_name, "description": tool.description}
                for tool in tools
            ]
            print(format_table(rows, [("source", "Source"), ("tool", "Tool"), ("description", "Description")]))
        return 0
    if ns.plugins_command == "show":
        plugin = find_plugin(ns.name)
        if plugin is None:
            print("No matching plugin.", file=sys.stderr)
            return 1
        print_json(plugin.to_json())
        return 0
    if ns.plugins_command == "create":
        description = prompt_from_parts(ns.description) or "Project plugin for Helix Agent."
        print(create_project_plugin(ns.name, description))
        return 0
    if ns.plugins_command == "run":
        if not ns.yes:
            print("Plugin execution requires --yes.", file=sys.stderr)
            return 2
        args = json.loads(ns.args_json) if ns.args_json else {}
        if not isinstance(args, dict):
            print("Plugin args must be a JSON object.", file=sys.stderr)
            return 2
        try:
            result = execute_plugin_tool(ns.tool, args)
        except PluginError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(result.output)
        return 0 if result.ok else 1
    return 2


def run_capabilities(ns, palette: Palette) -> int:
    report = capability_report()
    if getattr(ns, "json", False):
        print_json(report)
        return 0
    print(palette.bold("Helix Standout"))
    print(report["standout"])
    print()
    print(format_table(
        list(report["capabilities"]),
        [("area", "Area"), ("name", "Capability"), ("status", "Status"), ("description", "Description")],
    ))
    return 0


def run_subagents_cmd(config, ns) -> int:
    tasks: list[tuple[str, str]] = []
    for raw in ns.task:
        if "=" in raw:
            name, prompt = raw.split("=", 1)
        else:
            name, prompt = f"task-{len(tasks) + 1}", raw
        tasks.append((name.strip(), prompt.strip()))
    base_prompt = prompt_from_parts(ns.prompt)
    if base_prompt:
        tasks.append((f"task-{len(tasks) + 1}", base_prompt))
    if not tasks:
        print("Provide --task name=prompt or a prompt.", file=sys.stderr)
        return 2
    results = run_subagents(config, tasks, provider_name=ns.provider, model=ns.model, timeout=ns.timeout)
    for result in results:
        status = "ok" if result.ok else "error"
        print(f"## {result.name} ({status})\n{result.content}\n")
    return 0 if all(result.ok for result in results) else 1


def run_schedule_cmd(config, ns) -> int:
    if ns.schedule_command in {None, "list"}:
        rows = [
            {
                "id": job.id,
                "every": job.every_seconds,
                "enabled": job.enabled,
                "prompt": job.prompt,
                "last": job.last_result[:80],
            }
            for job in load_jobs()
        ]
        print(format_table(rows, [("id", "ID"), ("every", "Every(s)"), ("enabled", "On"), ("prompt", "Prompt"), ("last", "Last")]))
        return 0
    if ns.schedule_command == "add":
        prompt = prompt_from_parts(ns.prompt)
        if not prompt:
            print("Prompt is required.", file=sys.stderr)
            return 2
        job = add_job(prompt, every_seconds=ns.every, provider=ns.provider, model=ns.model)
        print_json(job.to_json())
        return 0
    if ns.schedule_command == "run":
        jobs = run_due_jobs(config, force=ns.force, timeout=ns.timeout)
        print(format_table(
            [{"id": job.id, "next": int(job.next_run), "last": job.last_result[:120]} for job in jobs],
            [("id", "ID"), ("next", "Next"), ("last", "Last")],
        ))
        return 0
    if ns.schedule_command == "remove":
        return 0 if remove_job(ns.selector) else 1
    return 2


def completion_script(shell: str) -> str:
    words = " ".join(sorted(COMMANDS))
    if shell == "bash":
        return f"complete -W \"{words}\" helix\n"
    if shell == "zsh":
        return f"#compdef helix\n_arguments '1:command:({words})'\n"
    return f"""Register-ArgumentCompleter -Native -CommandName helix -ScriptBlock {{
    param($wordToComplete)
    "{words}".Split(" ") | Where-Object {{ $_ -like "$wordToComplete*" }}
}}
"""


def main(argv: Sequence[str] | None = None) -> int:
    argv = preprocess_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    ns = parser.parse_args(argv)
    palette = Palette(enabled=not getattr(ns, "no_color", False))
    if ns.version or ns.command == "version":
        print(f"helix-agent {__version__}")
        return 0
    config = load_config()

    try:
        if ns.command == "ask":
            return run_ask(config, ns, palette)
        if ns.command == "agent":
            return run_agent(config, ns, palette)
        if ns.command == "chat":
            return run_chat(config, ns, palette)
        if ns.command == "capabilities":
            return run_capabilities(ns, palette)
        if ns.command == "config":
            if ns.config_command in {None, "show"}:
                print(json.dumps({
                    "home": str(config.home),
                    "project_dir": str(config.project_dir),
                    "default_provider": config.default_provider,
                    "system_prompt": config.system_prompt,
                    "providers": {name: provider.__dict__ for name, provider in config.providers.items()},
                }, indent=2))
                return 0
            if ns.config_command == "set":
                set_config_value(config, ns.key, ns.value)
                print(save_config(config))
                return 0
        if ns.command == "providers":
            print_provider_table(config)
            return 0
        if ns.command == "context":
            return run_context(ns)
        if ns.command == "skills":
            return run_skills(ns)
        if ns.command == "mission":
            return run_mission(config, ns, palette)
        if ns.command == "sessions":
            return run_sessions(ns)
        if ns.command == "memory":
            return run_memory(ns)
        if ns.command == "tools":
            return run_tools(ns)
        if ns.command == "plugins":
            return run_plugins(ns)
        if ns.command == "subagents":
            return run_subagents_cmd(config, ns)
        if ns.command == "schedule":
            return run_schedule_cmd(config, ns)
        if ns.command == "history":
            rows = [{"file": str(path)} for path in list_history(limit=ns.limit)]
            print(format_table(rows, [("file", "File")]))
            return 0
        if ns.command == "doctor":
            if ns.fix:
                init_config()
                config.project_dir.mkdir(parents=True, exist_ok=True)
            data = collect_diagnostics(config)
            if getattr(ns, "json", False):
                print_json(data)
            else:
                print(palette.bold("Helix Doctor"))
                print(f"Home: {data['home']}")
                print(f"Project: {data['project_dir']}")
                print_provider_table(config)
            return 0
        if ns.command == "init":
            print(init_config(force=ns.force))
            config.project_dir.mkdir(parents=True, exist_ok=True)
            return 0
        if ns.command == "completion":
            print(completion_script(ns.shell))
            return 0
        if ns.command == "rpc":
            return run_rpc(config)
    except ProviderError as exc:
        print(palette.red(str(exc)), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(palette.red(str(exc)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    parser.print_help()
    return 2
