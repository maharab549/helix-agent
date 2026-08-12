from __future__ import annotations

import unittest

from helix_agent.config import load_config
from helix_agent.provider import resolve_provider
from helix_agent.skills import load_skill_index, search_skills


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


if __name__ == "__main__":
    unittest.main()
