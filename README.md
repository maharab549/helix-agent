# Helix Agent

Helix Agent is a small standalone CLI AI agent. It works with OpenAI-compatible chat APIs, OpenRouter, custom endpoints, and local Ollama models without depending on any other agent repo.

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
helix ask --skill code-review "review this change"
helix providers list
helix skills list
helix skills search "repo"
helix skills create my-skill "When to use it" "Instructions..."
helix mission create --gate "pytest" "ship a clean CLI"
helix mission run ship-a-clean-cli
helix history
helix doctor --json
```

## Files

- User config: `~/.helix-agent/config.json`
- Project state: `.helix/`
- Project skills: `.helix/skills/<name>/SKILL.md`
- Built-in skills: `helix_agent/skills/`

## Development

```powershell
python -m unittest discover -s tests -v
python -m compileall helix_agent tests
```

## License

MIT
