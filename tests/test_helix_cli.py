from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from helix_agent.codeops import build_explain_prompt, build_fix_prompt, infer_test_commands
from helix_agent.config import apply_auth_file, auth_status, init_auth_file, load_config, save_auth_key
from helix_agent.context import collect_context_blocks, format_workspace_context
from helix_agent.learning import (
    build_dataset,
    capture_prompt_response,
    distill_learned_profile,
    learning_stats,
    set_learning_enabled,
    update_example_rating,
    validate_dataset,
)
from helix_agent.memory import remember, search_memories
from helix_agent.plugins import create_project_plugin, execute_plugin_tool, load_plugins
from helix_agent.provider import resolve_provider
from helix_agent.rpc import handle_rpc_request
from helix_agent.sessions import append_message, create_session, export_markdown, load_session
from helix_agent.skills import load_skill_index, search_skills
from helix_agent.tuning import auto_fine_tune, fine_tune_payload
from helix_agent.tools_runtime import execute_tool, parse_tool_calls, strip_tool_calls
from helix_agent.workspace import save_workspace_index, scan_workspace, workspace_map_markdown


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

    def test_toml_config_and_project_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            with patch.dict("os.environ", {"HELIX_HOME": str(home)}, clear=False):
                home.mkdir()
                (home / "config.toml").write_text(
                    "\n".join([
                        'default_provider = "openrouter"',
                        "",
                        "[providers.openrouter]",
                        'model = "anthropic/claude-3.5-sonnet"',
                        'base_url = "https://openrouter.ai/api/v1/chat/completions"',
                        'api_key_env = "OPENROUTER_API_KEY"',
                        "",
                    ]),
                    encoding="utf-8",
                )
                (project / ".helix").mkdir()
                (project / ".helix" / "config.toml").write_text(
                    "\n".join([
                        'default_provider = "ollama"',
                        "",
                        "[providers.ollama]",
                        'model = "qwen2.5-coder"',
                        "",
                    ]),
                    encoding="utf-8",
                )
                config = load_config(cwd=project)
                self.assertEqual(config.default_provider, "ollama")
                self.assertEqual(config.providers["openrouter"].model, "anthropic/claude-3.5-sonnet")
                self.assertEqual(config.providers["ollama"].model, "qwen2.5-coder")

    def test_auth_json_applies_provider_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict("os.environ", {"HELIX_HOME": str(home)}, clear=False):
                config = load_config(include_project=False)
                auth_path = init_auth_file(config)
                self.assertTrue(auth_path.exists())
                save_auth_key(config, "openai", "sk-test")
                status = auth_status(config)
                self.assertTrue(status["providers"]["openai"]["auth_json"])
                with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
                    applied = apply_auth_file(config, overwrite=True)
                    self.assertEqual(applied["OPENAI_API_KEY"], "sk-test")
                    self.assertEqual(resolve_provider(config, None).api_key_env, "OPENAI_API_KEY")

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

    def test_learning_capture_dataset_and_distill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_learning_enabled(True, cwd=root)
            example = capture_prompt_response(
                "How should Helix answer coding requests?",
                "Helix should inspect files, make focused edits, and run tests before summarizing.",
                rating=5,
                tags=["style"],
                force=True,
                cwd=root,
            )
            self.assertIsNotNone(example)
            self.assertEqual(learning_stats(cwd=root)["examples"], 1)
            rated = update_example_rating(example.id, 4, cwd=root)
            self.assertEqual(rated.rating, 4)
            dataset = build_dataset(cwd=root, min_rating=4)
            self.assertEqual(dataset.examples, 1)
            validation = validate_dataset(dataset.path)
            self.assertTrue(validation.ok)
            profile = distill_learned_profile(cwd=root)
            self.assertTrue(profile.exists())

    def test_fine_tune_payload_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture_prompt_response(
                "Make a release checklist",
                "Inspect status, run tests, update docs, tag the release, and publish.",
                rating=5,
                force=True,
                cwd=root,
            )
            payload = fine_tune_payload(training_file="file-123", base_model="gpt-4.1-mini", n_epochs=1)
            self.assertEqual(payload["training_file"], "file-123")
            config = load_config(cwd=root)
            result = auto_fine_tune(config, provider_name="openai", base_model="gpt-4.1-mini", dry_run=True, cwd=root)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            blocked = auto_fine_tune(
                config,
                provider_name="openai",
                base_model="gpt-4.1-mini",
                min_examples=2,
                dry_run=True,
                cwd=root,
            )
            self.assertFalse(blocked["ok"])
            self.assertIn("Need at least 2", blocked["reason"])

    def test_rpc_learning_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = load_config(cwd=root)
            added = handle_rpc_request(
                config,
                {
                    "id": 3,
                    "method": "learn.add",
                    "params": {
                        "prompt": "How does Helix learn?",
                        "response": "It captures useful examples, redacts secrets, rates them, and exports JSONL datasets.",
                        "rating": 5,
                    },
                },
                cwd=root,
            )
            self.assertTrue(added["ok"])
            dataset = handle_rpc_request(config, {"id": 4, "method": "learn.dataset", "params": {"min_rating": 5}}, cwd=root)
            self.assertTrue(dataset["ok"])
            self.assertEqual(dataset["result"]["examples"], 1)

    def test_workspace_scan_and_code_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
            index = scan_workspace(cwd=root)
            self.assertIn("Python", index.languages)
            self.assertIn("app.py", index.entrypoints)
            self.assertIn("python -m unittest discover -s tests -v", infer_test_commands(index))
            self.assertIn("Workspace Map", workspace_map_markdown(index))
            saved = save_workspace_index(index, cwd=root)
            self.assertTrue(saved.exists())
            explain = build_explain_prompt("app.py", cwd=root)
            self.assertIn("print('hi')", explain)
            fix = build_fix_prompt("make app importable", cwd=root)
            self.assertIn("make app importable", fix)

    def test_workspace_map_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            result = execute_tool("workspace_map", {"max_files": 5}, cwd=root)
            self.assertTrue(result.ok)
            self.assertIn("Workspace Map", result.output)


if __name__ == "__main__":
    unittest.main()
