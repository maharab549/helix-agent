# Helix Agent for VS Code

This extension connects VS Code to the local `helix` CLI.

## Features

- `@helix` chat participant
- Helix Activity Bar icon and sidebar panel
- right-side Helix Agent panel beside the editor
- right-side Command Center for core, code, context, state, plugin, and fine-tuning workflows
- LLM setup/login wizard with OpenAI, OpenRouter, Ollama, and custom endpoint support
- `@helix /map`, `/review`, `/explain`, `/fix`, `/learn`
- Copilot agent-mode tool reference: `#helix`
- `Helix: Ask`
- `Helix: Fix Selection`
- `Helix: Rewrite Selection`
- `Helix: Review Workspace`
- `Helix: Explain Current File`
- `Helix: Learning Status`
- `Helix: Setup LLM / Login`
- `Helix: Setup Details`

After installing the VSIX, look for the Helix icon in the left Activity Bar. Open the Helix sidebar to run quick actions beside other coding agents.

For a right-side layout like coding-agent panels, run `Helix: Open Right Side Panel` from the Command Palette or click `Open Right Side Panel` in the Helix sidebar.

The right-side panel exposes most Helix CLI groups: setup, ask, agent, capabilities, doctor, code map/review/explain/fix/tests, context, skills, tools, providers, memory, learning, sessions, missions, schedule, history, plugins, fine-tune prepare/dry-run, and raw CLI arguments.

## Requirements

Install Helix first:

```powershell
python -m pip install -e .
helix doctor
```

Then open this extension folder in VS Code and press `F5` to run an Extension Development Host.

## LLM Setup / Login

Run `Helix: Setup LLM / Login` from the Command Palette or click `Setup LLM / Login` in the Helix sidebar.

The wizard lets you choose OpenAI, OpenRouter, Ollama, or a custom OpenAI-compatible endpoint; enter a model ID; enter a base URL; and paste the API key if the provider needs one. API keys are stored in VS Code Secret Storage and injected into the local `helix` process as `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `HELIX_API_KEY`; they are not written to the workspace.

Run `Helix: Setup Details` to inspect the active provider, model, base URL, key status, `helix providers list`, and `helix doctor` output without revealing secrets.

## Usage

Open Chat and type:

```text
@helix /map
@helix /review
@helix /explain
@helix /fix add tests for the parser
@helix /learn
@helix /setup
```

In Copilot agent mode, reference Helix as a tool:

```text
Use #helix to map this workspace, then suggest the next test to add.
```

## Settings

- `helix.executable`: path to the Helix executable, default `helix`
- `helix.provider`: optional provider override
- `helix.model`: optional model override
- `helix.openaiBaseUrl`: optional OpenAI chat completions URL
- `helix.openrouterBaseUrl`: optional OpenRouter chat completions URL
- `helix.ollamaBaseUrl`: optional Ollama chat URL
- `helix.customBaseUrl`: optional custom OpenAI-compatible chat completions URL
