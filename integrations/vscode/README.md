# Helix Agent for VS Code

This extension connects VS Code to the local `helix` CLI.

## Features

- `@helix` chat participant
- Helix Activity Bar icon and sidebar panel
- right-side Helix Agent panel beside the editor
- right-side Command Center for core, code, context, state, plugin, and fine-tuning workflows
- `@helix /map`, `/review`, `/explain`, `/fix`, `/learn`
- Copilot agent-mode tool reference: `#helix`
- `Helix: Ask`
- `Helix: Fix Selection`
- `Helix: Rewrite Selection`
- `Helix: Review Workspace`
- `Helix: Explain Current File`
- `Helix: Learning Status`

After installing the VSIX, look for the Helix icon in the left Activity Bar. Open the Helix sidebar to run quick actions beside other coding agents.

For a right-side layout like coding-agent panels, run `Helix: Open Right Side Panel` from the Command Palette or click `Open Right Side Panel` in the Helix sidebar.

The right-side panel exposes most Helix CLI groups: ask, agent, capabilities, doctor, code map/review/explain/fix/tests, context, skills, tools, providers, memory, learning, sessions, missions, schedule, history, plugins, fine-tune prepare/dry-run, and raw CLI arguments.

## Requirements

Install Helix first:

```powershell
python -m pip install -e .
helix doctor
```

Then open this extension folder in VS Code and press `F5` to run an Extension Development Host.

## Usage

Open Chat and type:

```text
@helix /map
@helix /review
@helix /explain
@helix /fix add tests for the parser
@helix /learn
```

In Copilot agent mode, reference Helix as a tool:

```text
Use #helix to map this workspace, then suggest the next test to add.
```

## Settings

- `helix.executable`: path to the Helix executable, default `helix`
- `helix.provider`: optional provider override
- `helix.model`: optional model override
