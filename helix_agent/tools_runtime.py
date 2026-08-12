from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory import remember, search_memories
from .plugins import PluginError, execute_plugin_tool, format_plugin_tools_prompt
from .workspace import scan_workspace, workspace_map_markdown


TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


@dataclass
class ToolResult:
    tool: str
    ok: bool
    output: str

    def to_message(self) -> str:
        status = "ok" if self.ok else "error"
        return f"<tool_result tool={self.tool!r} status={status!r}>\n{self.output}\n</tool_result>"


TOOL_DESCRIPTIONS = {
    "list_dir": "List directory entries. args: {path?: string}",
    "read_file": "Read a UTF-8 text file. args: {path: string, max_chars?: number}",
    "write_file": "Write a UTF-8 text file. Requires --yes. args: {path: string, content: string}",
    "append_file": "Append text to a UTF-8 file. Requires --yes. args: {path: string, content: string}",
    "search_files": "Search files by regex. args: {pattern: string, path?: string, max_results?: number}",
    "git_status": "Show concise Git status for the workspace. args: {}",
    "git_diff": "Show Git diff. args: {path?: string, cached?: boolean, max_chars?: number}",
    "http_get": "Fetch text from an HTTP(S) URL. args: {url: string, max_chars?: number}",
    "workspace_map": "Summarize repository files, languages, tests, and entrypoints. args: {max_files?: number}",
    "shell": "Run a shell command. Requires --yes. args: {command: string, timeout?: number}",
    "python": "Run a short Python snippet. Requires --yes. args: {code: string, timeout?: number}",
    "plugin": "Run an installed Helix plugin tool. Requires --yes. args: {name: string, args?: object}",
    "remember": "Save memory. args: {text: string, scope?: 'project'|'global', tags?: string[]}",
    "recall": "Search memory. args: {query: string, limit?: number}",
}


def tools_system_prompt(*, cwd: Path | None = None) -> str:
    lines = [
        "You can use local tools by replying with one or more XML-wrapped JSON tool calls.",
        "Use this exact format and no markdown fences:",
        '<tool_call>{"tool":"read_file","args":{"path":"README.md"}}</tool_call>',
        "Available tools:",
    ]
    lines.extend(f"- {name}: {description}" for name, description in TOOL_DESCRIPTIONS.items())
    plugin_prompt = format_plugin_tools_prompt(cwd=cwd)
    if plugin_prompt:
        lines.append(plugin_prompt)
    lines.append("After a tool result is returned, continue normally or call another tool.")
    return "\n".join(lines)


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in TOOL_CALL_RE.finditer(text):
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("tool"), str):
            args = value.get("args", {})
            if not isinstance(args, dict):
                args = {}
            calls.append({"tool": value["tool"], "args": args})
    return calls


def strip_tool_calls(text: str) -> str:
    return TOOL_CALL_RE.sub("", text).strip()


def _resolve_path(path: str | None, cwd: Path) -> Path:
    raw = path or "."
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


def execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    cwd: Path | None = None,
    allow_write: bool = False,
    allow_shell: bool = False,
) -> ToolResult:
    root = (cwd or Path.cwd()).resolve()
    try:
        if name == "list_dir":
            path = _resolve_path(str(args.get("path") or "."), root)
            rows = []
            for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                kind = "dir" if entry.is_dir() else "file"
                size = "" if entry.is_dir() else str(entry.stat().st_size)
                rows.append(f"{kind}\t{size}\t{entry.name}")
            return ToolResult(name, True, "\n".join(rows) or "(empty)")

        if name == "read_file":
            path = _resolve_path(str(args["path"]), root)
            max_chars = int(args.get("max_chars") or 20000)
            text = path.read_text(encoding="utf-8", errors="replace")
            suffix = "\n[truncated]" if len(text) > max_chars else ""
            return ToolResult(name, True, text[:max_chars] + suffix)

        if name in {"write_file", "append_file"}:
            if not allow_write:
                return ToolResult(name, False, "File writes require --yes.")
            path = _resolve_path(str(args["path"]), root)
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(args.get("content", ""))
            if name == "write_file":
                path.write_text(content, encoding="utf-8")
            else:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(content)
            return ToolResult(name, True, f"Wrote {len(content)} characters to {path}")

        if name == "search_files":
            pattern = str(args["pattern"])
            search_root = _resolve_path(str(args.get("path") or "."), root)
            max_results = int(args.get("max_results") or 80)
            rg = shutil.which("rg")
            if rg:
                result = subprocess.run(
                    [rg, "-n", "--hidden", "--glob", "!.git", pattern, str(search_root)],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                lines = result.stdout.splitlines()[:max_results]
                return ToolResult(name, result.returncode in {0, 1}, "\n".join(lines) or "(no matches)")
            regex = re.compile(pattern)
            found: list[str] = []
            for file_path in search_root.rglob("*"):
                if len(found) >= max_results or not file_path.is_file() or ".git" in file_path.parts:
                    continue
                try:
                    for index, line in enumerate(file_path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if regex.search(line):
                            found.append(f"{file_path}:{index}:{line}")
                            if len(found) >= max_results:
                                break
                except OSError:
                    continue
            return ToolResult(name, True, "\n".join(found) or "(no matches)")

        if name == "git_status":
            result = subprocess.run(["git", "status", "--short"], cwd=str(root), capture_output=True, text=True, timeout=20)
            output = result.stdout.strip() or result.stderr.strip() or "(clean)"
            return ToolResult(name, result.returncode == 0, output)

        if name == "git_diff":
            max_chars = int(args.get("max_chars") or 20000)
            command = ["git", "diff"]
            if bool(args.get("cached")):
                command.append("--cached")
            path_arg = args.get("path")
            if path_arg:
                command.extend(["--", str(path_arg)])
            result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, timeout=30)
            output = result.stdout if result.stdout else result.stderr
            suffix = "\n[truncated]" if len(output) > max_chars else ""
            return ToolResult(name, result.returncode == 0, (output[:max_chars] + suffix).strip() or "(no diff)")

        if name == "http_get":
            url = str(args["url"])
            if not url.startswith(("http://", "https://")):
                return ToolResult(name, False, "Only http:// and https:// URLs are supported.")
            max_chars = int(args.get("max_chars") or 20000)
            request = urllib.request.Request(url, headers={"User-Agent": "helix-agent/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    content_type = response.headers.get("Content-Type", "")
                    body = response.read(max_chars + 1)
            except urllib.error.URLError as exc:
                return ToolResult(name, False, f"Could not fetch URL: {exc.reason}")
            text = body.decode("utf-8", errors="replace")
            suffix = "\n[truncated]" if len(text) > max_chars else ""
            return ToolResult(name, True, f"Content-Type: {content_type}\n\n{text[:max_chars]}{suffix}")

        if name == "workspace_map":
            max_files = int(args.get("max_files") or 120)
            return ToolResult(name, True, workspace_map_markdown(scan_workspace(cwd=root), max_files=max_files))

        if name == "shell":
            if not allow_shell:
                return ToolResult(name, False, "Shell commands require --yes.")
            command = str(args["command"])
            timeout = int(args.get("timeout") or 60)
            result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, shell=True, timeout=timeout)
            output = "\n".join([
                f"exit_code={result.returncode}",
                "# stdout",
                result.stdout,
                "# stderr",
                result.stderr,
            ]).strip()
            return ToolResult(name, result.returncode == 0, output)

        if name == "python":
            if not allow_shell:
                return ToolResult(name, False, "Python execution requires --yes.")
            code = str(args["code"])
            timeout = int(args.get("timeout") or 60)
            result = subprocess.run([sys.executable, "-c", code], cwd=str(root), capture_output=True, text=True, timeout=timeout)
            output = "\n".join([
                f"exit_code={result.returncode}",
                "# stdout",
                result.stdout,
                "# stderr",
                result.stderr,
            ]).strip()
            return ToolResult(name, result.returncode == 0, output)

        if name == "plugin":
            if not allow_shell:
                return ToolResult(name, False, "Plugin tools require --yes.")
            plugin_args = args.get("args") or {}
            if not isinstance(plugin_args, dict):
                return ToolResult(name, False, "Plugin args must be a JSON object.")
            try:
                result = execute_plugin_tool(str(args["name"]), plugin_args, cwd=root)
            except PluginError as exc:
                return ToolResult(name, False, str(exc))
            return ToolResult(name, result.ok, result.output)

        if name == "remember":
            text = str(args["text"])
            scope = str(args.get("scope") or "project")
            tags = args.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            path = remember(text, scope=scope, tags=[str(tag) for tag in tags], cwd=root)
            return ToolResult(name, True, f"Saved memory to {path}")

        if name == "recall":
            query = str(args.get("query") or "")
            limit = int(args.get("limit") or 8)
            entries = search_memories(query, limit=limit, cwd=root)
            lines = [f"- ({entry.scope}) {entry.text}" for entry in entries]
            return ToolResult(name, True, "\n".join(lines) or "(no matching memory)")

        return ToolResult(name, False, f"Unknown tool: {name}")
    except Exception as exc:  # noqa: BLE001 - tool errors must be returned to the model.
        return ToolResult(name, False, f"{type(exc).__name__}: {exc}")
