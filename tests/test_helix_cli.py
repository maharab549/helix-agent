from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from helix_agent.config import load_config
from helix_agent.context import collect_context_blocks, format_workspace_context
from helix_agent.memory import remember, search_memories
from helix_agent.plugins import create_project_plugin, execute_plugin_tool, load_plugins
from helix_agent.provider import resolve_provider
from helix_agent.rpc import handle_rpc_request
from helix_agent.sessions import append_message, create_session, export_markdown, load_session
from helix_agent.skills import load_skill_index, search_skills
from helix_agent.tools_runtime import execute_tool, parse_tool_calls, strip_tool_calls


class HelixCliTests(unittest.TestCase):
    def test_builtin_skills_load(self) -> None:
        entries = load_skill_index(sources={"built-in"})
        names = {entry.name for entry in entries}
        self.assertIn("agent-architect", names)
        self.assertIn("code-review", names)

    def test_skill_search_finds_code_review(self) -> None:
        entries = load_skill_index(sources={"built-in"})
        results = search_skills(entries, "review bugs tests", limit=3)
        self.assertTrue(any(entry.name == "code-review" for entry in results))

    def test_default_provider_resolves(self) -> None:
        config = load_config()
        provider = resolve_provider(config, None)
        self.assertEqual(provider.name, config.default_provider)

    def test_tool_call_parser(self) -> None:
        text = 'before <tool_call>{"tool":"read_file","args":{"path":"README.md"}}</tool_call> after'
        calls = parse_tool_calls(text)
        self.assertEqual(calls[0]["tool"], "read_file")
        self.assertEqual(strip_tool_calls(text), "before  after")

    def test_read_file_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello", encoding="utf-8")
            result = execute_tool("read_file", {"path": "note.txt"}, cwd=root)
            self.assertTrue(result.ok)
            self.assertIn("hello", result.output)

    def test_sessions_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = create_session("demo", cwd=root)
            append_message(session, "user", "hello")
            from helix_agent.sessions import save_session
            save_session(session, cwd=root)
            loaded = load_session(session.id, cwd=root)
            self.assertEqual(loaded.messages[0]["content"], "hello")
            self.assertIn("hello", export_markdown(loaded))

    def test_memory_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remember("Prefer concise CLI output", tags=["style"], cwd=root)
            results = search_memories("concise", cwd=root)
            self.assertEqual(results[0].text, "Prefer concise CLI output")

    def test_workspace_context_loads_known_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "HELIX.md").write_text("Project rules live here.", encoding="utf-8")
            blocks = collect_context_blocks(cwd=root)
            self.assertEqual(blocks[0].content, "Project rules live here.")
            self.assertIn("HELIX.md", format_workspace_context(cwd=root))

    def test_plugin_create_and_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = create_project_plugin("demo", "Demo plugin", cwd=root)
            self.assertTrue(manifest.exists())
            plugins = load_plugins(cwd=root)
            self.assertEqual(plugins[0].name, "demo")
            result = execute_plugin_tool("demo.echo", {"text": "hello"}, cwd=root)
            self.assertTrue(result.ok)
            self.assertIn("hello", result.output)

    def test_git_status_tool_returns_result(self) -> None:
        result = execute_tool("git_status", {})
        self.assertTrue(result.ok)

    def test_rpc_ping_and_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("rpc works", encoding="utf-8")
            config = load_config(cwd=root)
            ping = handle_rpc_request(config, {"id": 1, "method": "ping"}, cwd=root)
            self.assertTrue(ping["ok"])
            response = handle_rpc_request(
                config,
                {"id": 2, "method": "tool", "params": {"name": "read_file", "args": {"path": "note.txt"}}},
                cwd=root,
            )
            self.assertTrue(response["ok"])
            self.assertIn("rpc works", response["result"]["output"])


if __name__ == "__main__":
    unittest.main()
