from __future__ import annotations


STANDOUT = (
    "Helix is an owner-controlled agent OS for the terminal: a provider-agnostic core loop "
    "that combines project context, memory, automatic learning, fine-tuning automation, "
    "skills, tools, plugins, sessions, missions, subagents, schedules, and RPC in plain local files."
)


CAPABILITIES = [
    {
        "area": "Models",
        "name": "Provider routing",
        "status": "available",
        "description": "OpenAI-compatible APIs, OpenRouter, custom endpoints, and Ollama.",
    },
    {
        "area": "Interaction",
        "name": "Ask and chat",
        "status": "available",
        "description": "One-shot prompts and interactive chat.",
    },
    {
        "area": "Autonomy",
        "name": "Agent loop",
        "status": "available",
        "description": "XML tool-call loop with bounded steps and opt-in execution.",
    },
    {
        "area": "Context",
        "name": "Workspace awareness",
        "status": "available",
        "description": "Loads AGENTS.md, HELIX.md, .helix/CONTEXT.md, README.md, and project metadata.",
    },
    {
        "area": "Context",
        "name": "Skills",
        "status": "available",
        "description": "Built-in, user, and project skills with search and creation commands.",
    },
    {
        "area": "Context",
        "name": "Memory",
        "status": "available",
        "description": "Project and global JSONL memory with search and agent recall.",
    },
    {
        "area": "Learning",
        "name": "Automatic learning",
        "status": "available",
        "description": "Captures successful interactions, redacts secrets, scores examples, and supports ratings.",
    },
    {
        "area": "Learning",
        "name": "Dataset curation",
        "status": "available",
        "description": "Mines history, exports chat JSONL, validates datasets, and distills .helix/LEARNED.md.",
    },
    {
        "area": "Learning",
        "name": "Fine-tuning automation",
        "status": "available",
        "description": "Prepares datasets, uploads OpenAI training files, creates jobs, checks status, and adopts tuned models.",
    },
    {
        "area": "Tools",
        "name": "Local tools",
        "status": "available",
        "description": "List, read, write, append, search, shell, Python, Git status/diff, HTTP fetch.",
    },
    {
        "area": "Tools",
        "name": "Plugins",
        "status": "available",
        "description": "Project and user plugin manifests that expose local commands as agent tools.",
    },
    {
        "area": "Workflow",
        "name": "Sessions",
        "status": "available",
        "description": "Persistent sessions with markdown export.",
    },
    {
        "area": "Workflow",
        "name": "Missions",
        "status": "available",
        "description": "Named objectives, gates, notes, and run prompts.",
    },
    {
        "area": "Workflow",
        "name": "Subagents",
        "status": "available",
        "description": "Parallel focused LLM calls for review, research, tests, and alternatives.",
    },
    {
        "area": "Workflow",
        "name": "Recurring prompts",
        "status": "available",
        "description": "Schedule file plus manual/cron-friendly runner.",
    },
    {
        "area": "Automation",
        "name": "JSONL RPC",
        "status": "available",
        "description": "Script Helix from editors, dashboards, bots, and other command-line tools.",
    },
    {
        "area": "Distribution",
        "name": "Standalone package",
        "status": "available",
        "description": "No Prime/Hermes repo dependency; includes launchers, tests, CI, and MIT license.",
    },
    {
        "area": "Future",
        "name": "Daemon, MCP, browser, TUI, registry",
        "status": "planned",
        "description": "High-end layers that can now be added cleanly on top of plugins/RPC.",
    },
]


def capability_report() -> dict[str, object]:
    return {"standout": STANDOUT, "capabilities": CAPABILITIES}
