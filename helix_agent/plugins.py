from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import app_home, project_state_dir


NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


class PluginError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginTool:
    plugin: str
    name: str
    full_name: str
    description: str
    command: str | list[str]
    timeout: int
    env: dict[str, str]
    source: str
    manifest_path: Path

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["manifest_path"] = str(self.manifest_path)
        return data


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    version: str
    source: str
    path: Path
    tools: list[PluginTool] = field(default_factory=list)

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["tools"] = [tool.to_json() for tool in self.tools]
        return data


@dataclass(frozen=True)
class PluginExecution:
    tool: str
    ok: bool
    output: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return slug or "plugin"


def plugin_roots(*, cwd: Path | None = None) -> list[tuple[str, Path]]:
    return [
        ("project", project_state_dir(cwd) / "plugins"),
        ("user", app_home() / "plugins"),
    ]


def _validate_name(value: str, kind: str) -> str:
    if not NAME_RE.match(value):
        raise PluginError(f"Invalid {kind} name: {value}")
    return value


def _load_manifest(path: Path, source: str) -> Plugin | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    try:
        name = _validate_name(str(data["name"]), "plugin")
    except (KeyError, PluginError):
        return None
    description = str(data.get("description") or "")
    version = str(data.get("version") or "0.1.0")
    tools: list[PluginTool] = []

    for raw_tool in data.get("tools") or []:
        if not isinstance(raw_tool, dict):
            continue
        try:
            local_name = _validate_name(str(raw_tool["name"]), "tool")
        except (KeyError, PluginError):
            continue
        command = raw_tool.get("command")
        if not isinstance(command, (str, list)):
            continue
        if isinstance(command, list) and not all(isinstance(part, str) for part in command):
            continue
        full_name = f"{name}.{local_name}"
        raw_env = raw_tool.get("env") or {}
        env = {str(key): str(value) for key, value in raw_env.items()} if isinstance(raw_env, dict) else {}
        tools.append(
            PluginTool(
                plugin=name,
                name=local_name,
                full_name=full_name,
                description=str(raw_tool.get("description") or ""),
                command=command,
                timeout=int(raw_tool.get("timeout") or 60),
                env=env,
                source=source,
                manifest_path=path,
            )
        )

    return Plugin(name=name, description=description, version=version, source=source, path=path.parent, tools=tools)


def load_plugins(*, cwd: Path | None = None) -> list[Plugin]:
    plugins: list[Plugin] = []
    seen: set[tuple[str, str]] = set()
    for source, root in plugin_roots(cwd=cwd):
        if not root.exists():
            continue
        for manifest in sorted(root.rglob("plugin.json")):
            plugin = _load_manifest(manifest, source)
            if plugin is None:
                continue
            key = (plugin.source, plugin.name.lower())
            if key in seen:
                continue
            seen.add(key)
            plugins.append(plugin)
    plugins.sort(key=lambda item: (item.source, item.name))
    return plugins


def load_plugin_tools(*, cwd: Path | None = None) -> list[PluginTool]:
    return [tool for plugin in load_plugins(cwd=cwd) for tool in plugin.tools]


def find_plugin(name: str, *, cwd: Path | None = None) -> Plugin | None:
    lowered = name.lower()
    for plugin in load_plugins(cwd=cwd):
        if plugin.name.lower() == lowered:
            return plugin
    return None


def find_plugin_tool(name: str, *, cwd: Path | None = None) -> PluginTool | None:
    lowered = name.lower()
    tools = load_plugin_tools(cwd=cwd)
    for tool in tools:
        if tool.full_name.lower() == lowered:
            return tool
    local_matches = [tool for tool in tools if tool.name.lower() == lowered]
    return local_matches[0] if len(local_matches) == 1 else None


def create_project_plugin(name: str, description: str, *, cwd: Path | None = None) -> Path:
    slug = _validate_name(slugify(name), "plugin")
    plugin_dir = project_state_dir(cwd) / "plugins" / slug
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": slug,
        "description": description,
        "version": "0.1.0",
        "tools": [
            {
                "name": "echo",
                "description": "Print the provided text. args: {text: string}",
                "command": ["{python}", "-c", "import sys; print(sys.argv[1])", "{text}"],
                "timeout": 10,
            }
        ],
    }
    out = plugin_dir / "plugin.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out


def _render_template(value: str, values: dict[str, Any]) -> str:
    try:
        return value.format_map(values)
    except KeyError as exc:
        raise PluginError(f"Missing plugin argument: {exc.args[0]}") from exc


def _render_command(tool: PluginTool, args: dict[str, Any], cwd: Path) -> str | list[str]:
    values: dict[str, Any] = {
        "args_json": json.dumps(args, ensure_ascii=False),
        "cwd": str(cwd),
        "plugin_dir": str(tool.manifest_path.parent),
        "python": sys.executable,
    }
    values.update(args)
    command = tool.command
    if isinstance(command, str):
        return _render_template(command, values)
    return [_render_template(part, values) for part in command]


def execute_plugin_tool(
    name: str,
    args: dict[str, Any] | None = None,
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> PluginExecution:
    root = (cwd or Path.cwd()).resolve()
    tool = find_plugin_tool(name, cwd=root)
    if tool is None:
        raise PluginError(f"Unknown plugin tool: {name}")
    command = _render_command(tool, args or {}, root)
    env_values = {
        "args_json": json.dumps(args or {}, ensure_ascii=False),
        "cwd": str(root),
        "plugin_dir": str(tool.manifest_path.parent),
        "python": sys.executable,
        **(args or {}),
    }
    env = os.environ.copy()
    env.update({key: _render_template(value, env_values) for key, value in tool.env.items()})
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            shell=isinstance(command, str),
            timeout=timeout or tool.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return PluginExecution(tool.full_name, False, f"Timed out after {exc.timeout} seconds.")
    output = "\n".join(
        [
            f"exit_code={result.returncode}",
            "# stdout",
            result.stdout,
            "# stderr",
            result.stderr,
        ]
    ).strip()
    return PluginExecution(tool.full_name, result.returncode == 0, output)


def format_plugin_tools_prompt(*, cwd: Path | None = None) -> str:
    tools = load_plugin_tools(cwd=cwd)
    if not tools:
        return ""
    lines = ["Installed plugin tools are available through the `plugin` tool:"]
    lines.extend(f"- {tool.full_name}: {tool.description}" for tool in tools)
    return "\n".join(lines)
