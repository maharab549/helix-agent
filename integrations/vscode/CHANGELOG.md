# Changelog

## 0.1.4

- Add Codex-style editable Helix setup files: `~/.helix-agent/config.toml`, `~/.helix-agent/auth.json`, and `.helix/config.toml`.
- Add VS Code commands to open the user config, auth file, and project config directly.
- Teach the CLI to load auth keys from `auth.json` and project overrides from `.helix/config.toml`.

## 0.1.3

- Add `Helix: Setup LLM / Login` for OpenAI, OpenRouter, Ollama, and custom OpenAI-compatible endpoints.
- Store provider API keys in VS Code Secret Storage and inject them into local Helix CLI runs.
- Add `Helix: Setup Details`, right-side panel setup actions, sidebar setup actions, and `@helix /setup`.

## 0.1.2

- Expand the right-side panel into a Helix Command Center covering core, code, context, state, plugin, and fine-tuning workflows.
- Add raw CLI argument runner inside VS Code.

## 0.1.1

- Add right-side Helix Agent webview panel for a Codex/Claude-style layout beside the editor.

## 0.1.0

- Add Helix Activity Bar icon and sidebar panel with quick actions.
- Add `@helix` chat participant.
- Add command palette actions for ask, selection fix, selection rewrite, workspace review, file explanation, and learning status.
- Add Copilot agent-mode tool reference `#helix`.
- Connect VS Code to the local Helix CLI.
