# Helix Agent

Helix Agent is a standalone CLI AI agent. It works with OpenAI-compatible chat APIs, OpenRouter, custom endpoints, and local Ollama models without depending on any other agent repo.

It is designed to bring the useful ideas from larger agents into a clean independent project: persistent sessions, skills, memory, local tools, autonomous tool loops, subagents, recurring prompts, and project missions.

## Install From Source

```powershell
git clone https://github.com/YOUR-USER/helix-agent.git
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
helix ask --skill code-review "review this change"
helix providers list
helix skills list
helix skills search "repo"
helix skills create my-skill "When to use it" "Instructions..."
helix tools list
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
helix doctor --json
```

Inside `helix chat`, useful slash commands include:

```text
/skills [query]
/use <skill>
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
- `shell`
- `python`
- `remember`
- `recall`

## Files

- User config: `~/.helix-agent/config.json`
- Project state: `.helix/`
- Project skills: `.helix/skills/<name>/SKILL.md`
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
