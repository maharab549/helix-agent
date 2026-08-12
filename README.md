# Helix Agent

Helix Agent is a standalone CLI AI agent. It works with OpenAI-compatible chat APIs, OpenRouter, custom endpoints, and local Ollama models without depending on any other agent repo.

It is designed to bring the useful ideas from larger agents into a clean independent project: persistent sessions, skills, memory, automatic learning, fine-tuning automation, coding-agent workflows, local tools, autonomous tool loops, subagents, recurring prompts, project missions, plugins, workspace context, VS Code integration, and JSONL automation.

## What Makes Helix Different

Helix is an owner-controlled agent OS for the terminal.

Most CLI agents are either a thin chat wrapper or a large locked-in app. Helix aims for the middle path: one portable command that keeps its brain in plain project files and can grow through skills, memories, sessions, schedules, local tools, plugins, and RPC. That makes it easy to inspect, fork, automate, and publish.

The main feature is the Helix Core Loop:

- it reads project context from files such as `AGENTS.md`, `HELIX.md`, `.helix/CONTEXT.md`, and `README.md`
- it recalls project and global memory
- it learns from successful interactions and can write `.helix/LEARNED.md`
- it maps codebases, infers tests, reviews diffs, explains files, and runs fix workflows
- it loads reusable skills
- it can call local tools, Git tools, HTTP fetches, and plugin tools
- it saves sessions and history so work can continue later
- it can split work across subagents or recurring schedules
- it can curate fine-tuning datasets and start provider fine-tune jobs
- it can be controlled by another program through JSONL RPC

That is the reason Helix can stand apart: it is not only a chatbot in your shell; it is a hackable local agent platform.

## Install From Source

```powershell
git clone https://github.com/maharab549/helix-agent.git
cd helix-agent
python -m pip install -e .
helix doctor
```

You can also run it directly from the folder:

```powershell
python -m helix_agent doctor
.\helix.ps1 doctor
```

## Configure A Provider

OpenAI:

```powershell
$env:OPENAI_API_KEY="sk-..."
helix ask "Give me a compact project checklist"
```

OpenRouter:

```powershell
$env:OPENROUTER_API_KEY="..."
helix config set default-provider openrouter
helix ask "Explain this repo in one paragraph"
```

Ollama:

```powershell
ollama serve
ollama pull llama3.1
helix ask --provider ollama "Write a short release note"
```

Custom OpenAI-compatible endpoint:

```powershell
$env:HELIX_API_KEY="..."
helix config set default-provider custom
helix config set providers.custom.base-url "https://example.com/v1/chat/completions"
helix config set providers.custom.model "your-model"
helix ask "Hello"
```

## Commands

```powershell
helix chat                         # interactive chat
helix ask "your prompt"             # one-shot prompt
helix agent "inspect this repo"      # autonomous loop with local tools
helix agent --yes "create tests"     # allow writes/shell/python tools
helix capabilities                  # show Helix's feature map
helix code map
helix code tests
helix code review
helix code explain helix_agent/cli.py
helix code fix --yes "add a focused test for provider resolution"
helix learn status
helix learn mine-history
helix learn dataset --min-rating 4
helix learn distill
helix finetune prepare --min-rating 4
helix finetune auto --base-model gpt-4.1-mini --mine-history 200 --distill --dry-run
helix ask --skill code-review "review this change"
helix providers list
helix context show
helix skills list
helix skills search "repo"
helix skills create my-skill "When to use it" "Instructions..."
helix tools list
helix tools run git_status
helix tools run http_get '{"url":"https://example.com","max_chars":1000}'
helix plugins create my-plugin "Local commands for my workflow"
helix plugins tools
helix plugins run --yes my-plugin.echo '{"text":"hello"}'
helix tools run read_file '{"path":"README.md"}'
helix memory add --tag style "Prefer concise CLI output"
helix memory search "CLI output"
helix sessions list
helix sessions export <session-id> session.md
helix subagents --task "review=Find risks" --task "tests=Find missing tests"
helix schedule add --every 86400 "Summarize repo status"
helix schedule run --force
helix mission create --gate "pytest" "ship a clean CLI"
helix mission run ship-a-clean-cli
helix history
helix rpc
helix doctor --json
```

Inside `helix chat`, useful slash commands include:

```text
/skills [query]
/use <skill>
/context
/remember <text>
/recall [query]
/tools
/providers
/clear
/exit
```

## Autonomous Tools

`helix agent` gives the model a local tool protocol. Read/search/list/memory tools are available by default. Write, shell, and Python execution require `--yes`.

Available built-in tools:

- `list_dir`
- `read_file`
- `write_file`
- `append_file`
- `search_files`
- `git_status`
- `git_diff`
- `http_get`
- `workspace_map`
- `shell`
- `python`
- `plugin`
- `remember`
- `recall`

## Plugins

Plugins let Helix grow without copying another agent repo into this project. A plugin is a small `plugin.json` file stored in `.helix/plugins/<name>/` or `~/.helix-agent/plugins/<name>/`.

Create one:

```powershell
helix plugins create release-tools "Release helpers"
helix plugins tools
helix plugins run --yes release-tools.echo '{"text":"ship it"}'
```

Plugin tools are available to `helix agent` through the built-in `plugin` tool. They require `--yes` because they execute local commands.

## JSONL RPC

`helix rpc` reads one JSON object per line from stdin and writes one JSON object per line to stdout. This makes it usable from editors, dashboards, bots, and other CLIs.

```powershell
'{"id":1,"method":"ping"}' | helix rpc
'{"id":2,"method":"tool","params":{"name":"read_file","args":{"path":"README.md"}}}' | helix rpc
```

Supported methods include `ping`, `ask`, `agent`, `tool`, `skills.list`, `skills.search`, `memory.add`, `memory.search`, and `context`.

## Automatic Learning

Helix can automatically capture successful `ask`, `chat`, and `agent` exchanges into `.helix/learning/examples.jsonl`. Captured examples are redacted for obvious secrets, scored, and deduplicated. You can rate examples, mine older history, build fine-tuning datasets, and distill a local learned profile.

```powershell
helix learn status
helix learn on --mine-history
helix learn add --rating 5 --tag style --response "Use concise verification notes." "How should Helix summarize work?"
helix learn list
helix learn rate <example-id> 5
helix learn dataset --min-rating 4
helix learn validate .helix/learning/datasets/<file>.jsonl
helix learn distill
```

`helix learn distill` writes `.helix/LEARNED.md`, and Helix loads that file as workspace context on later runs.

## Fine-Tuning

Helix includes an OpenAI-compatible fine-tuning pipeline with no extra Python dependencies. The current OpenAI flow is: upload a JSONL training file with purpose `fine-tune`, create a fine-tuning job with a `training_file` and base `model`, then poll the job until a fine-tuned model is available.

```powershell
helix finetune prepare --min-rating 4
helix finetune start --provider openai --dataset .helix/learning/datasets/<file>.jsonl --base-model gpt-4.1-mini --dry-run
helix finetune start --provider openai --dataset .helix/learning/datasets/<file>.jsonl --base-model gpt-4.1-mini
helix finetune auto --provider openai --base-model gpt-4.1-mini --mine-history 200 --distill --min-examples 20 --dry-run
helix finetune status <job-id>
helix finetune adopt <job-id> --name helix-tuned
```

`--dry-run` validates the dataset and shows the job payload without uploading anything. Real fine-tuning requires `OPENAI_API_KEY` and can incur provider costs.

## Coding Workflows

Helix has first-class coding-agent commands:

```powershell
helix code map                         # summarize files, languages, entrypoints, tests, Git state
helix code map --save                  # write .helix/workspace-index.json
helix code tests                       # infer likely verification commands
helix code review                      # review the workspace/diff using the agent loop
helix code review --dry-run            # print the generated review prompt
helix code explain helix_agent/cli.py  # explain a file
helix code fix --yes "fix the failing tests"
```

`helix code fix` uses the autonomous local-tool loop. Reads/searches are available by default; writes, shell, Python, and plugin execution require `--yes`.

## VS Code Integration

The first-party VS Code extension lives in `integrations/vscode`.

It adds:

- `@helix` chat participant
- Helix Activity Bar icon and sidebar panel
- `@helix /map`, `/review`, `/explain`, `/fix`, `/learn`
- Copilot agent-mode tool reference: `#helix`
- `Helix: Ask`
- `Helix: Fix Selection`
- `Helix: Rewrite Selection`
- `Helix: Review Workspace`
- `Helix: Explain Current File`
- `Helix: Learning Status`

Development run:

```powershell
cd integrations/vscode
code .
```

Then press `F5` in VS Code to launch an Extension Development Host. The extension calls your local `helix` executable, so run `python -m pip install -e .` from the repo root first.

To publish it so it appears in VS Code extension search, create a Visual Studio Marketplace publisher, set the exact publisher ID in `integrations/vscode/package.json`, add a GitHub Actions secret named `VSCE_PAT`, then run the `VS Code Extension` workflow with `publish=true`.

Local package test:

```powershell
cd integrations/vscode
npm install
npm run check
npx vsce package --no-dependencies
```

Full release notes are in `docs/vscode-marketplace.md`.

## Feature Map

Already available:

- provider routing for OpenAI-compatible APIs, OpenRouter, custom endpoints, and Ollama
- one-shot ask, interactive chat, autonomous agent loop
- codebase map, inferred test commands, review/explain/fix workflows
- VS Code extension scaffold with chat participant and command palette actions
- project/user/built-in skills
- project/global memory
- automatic learning capture with redaction, scoring, rating, and deduplication
- history mining and `.helix/LEARNED.md` distillation
- JSONL fine-tuning dataset generation and validation
- OpenAI training-file upload, fine-tune job creation, status refresh, and tuned-model adoption
- sessions and markdown export
- missions and recurring schedules
- parallel subagents
- local read/search/write/shell/Python tools with approval
- Git status/diff tools
- HTTP fetch tool
- project and user plugins
- workspace context loading
- JSONL RPC automation
- diagnostics, shell completions, launchers, tests, and CI

Planned high-end layers:

- long-running daemon mode with attach/resume
- MCP-compatible tool adapters
- browser automation and visual inspection plugins
- richer TUI
- package publishing to PyPI
- signed plugin registry
- deeper benchmark/eval harness

## Files

- User config: `~/.helix-agent/config.json`
- Project state: `.helix/`
- Project skills: `.helix/skills/<name>/SKILL.md`
- Project plugins: `.helix/plugins/<name>/plugin.json`
- Project learning examples: `.helix/learning/examples.jsonl`
- Project learned profile: `.helix/LEARNED.md`
- Project fine-tune records: `.helix/fine_tunes.json`
- Workspace index: `.helix/workspace-index.json`
- Project sessions: `.helix/sessions/`
- Project memory: `.helix/memory.jsonl`
- Project schedule: `.helix/schedule.json`
- Built-in skills: `helix_agent/skills/`

## Development

```powershell
python -m unittest discover -s tests -v
python -m compileall helix_agent tests
```

## License

MIT
