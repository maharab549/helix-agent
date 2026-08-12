# Helix Agent

Helix Agent is a standalone CLI AI agent. It works with OpenAI-compatible chat APIs, OpenRouter, custom endpoints, and local Ollama models without depending on any other agent repo.

It is designed to bring the useful ideas from larger agents into a clean independent project: persistent sessions, skills, memory, local tools, autonomous tool loops, subagents, recurring prompts, project missions, plugins, workspace context, and JSONL automation.

## What Makes Helix Different

Helix is an owner-controlled agent OS for the terminal.

Most CLI agents are either a thin chat wrapper or a large locked-in app. Helix aims for the middle path: one portable command that keeps its brain in plain project files and can grow through skills, memories, sessions, schedules, local tools, plugins, and RPC. That makes it easy to inspect, fork, automate, and publish.

The main feature is the Helix Core Loop:

- it reads project context from files such as `AGENTS.md`, `HELIX.md`, `.helix/CONTEXT.md`, and `README.md`
- it recalls project and global memory
- it loads reusable skills
- it can call local tools, Git tools, HTTP fetches, and plugin tools
- it saves sessions and history so work can continue later
- it can split work across subagents or recurring schedules
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

## Feature Map

Already available:

- provider routing for OpenAI-compatible APIs, OpenRouter, custom endpoints, and Ollama
- one-shot ask, interactive chat, autonomous agent loop
- project/user/built-in skills
- project/global memory
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
