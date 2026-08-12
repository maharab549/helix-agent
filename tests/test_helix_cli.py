from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from helix_agent.config import load_config
from helix_agent.memory import remember, search_memories
from helix_agent.provider import resolve_provider
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


if __name__ == "__main__":
    unittest.main()
