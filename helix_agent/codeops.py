from __future__ import annotations

from pathlib import Path

from .workspace import WorkspaceIndex, scan_workspace, workspace_map_markdown


def infer_test_commands(index: WorkspaceIndex) -> list[str]:
    paths = {item.path for item in index.files}
    commands: list[str] = []
    if "pyproject.toml" in paths or "setup.py" in paths or "requirements.txt" in paths:
        if any(path.startswith("tests/") or path.startswith("test") for path in paths):
            commands.append("python -m unittest discover -s tests -v")
        commands.append("python -m compileall .")
    if "package.json" in paths:
        commands.append("npm test")
    if "go.mod" in paths:
        commands.append("go test ./...")
    if "Cargo.toml" in paths:
        commands.append("cargo test")
    if "pom.xml" in paths:
        commands.append("mvn test")
    return commands


def codebase_context(*, cwd: Path | None = None, max_files: int = 120) -> str:
    return workspace_map_markdown(scan_workspace(cwd=cwd), max_files=max_files)


def build_review_prompt(*, cwd: Path | None = None) -> str:
    index = scan_workspace(cwd=cwd)
    test_commands = infer_test_commands(index)
    tests = "\n".join(f"- {command}" for command in test_commands) or "- No obvious test command inferred"
    return (
        "You are reviewing this workspace like a senior coding agent.\n\n"
        f"{workspace_map_markdown(index, max_files=80)}\n"
        "Focus on bugs, regressions, security risks, maintainability issues, and missing tests. "
        "Use git_status and git_diff before making claims about changed files.\n\n"
        "Likely verification commands:\n"
        f"{tests}\n"
    )


def build_explain_prompt(path: str, *, cwd: Path | None = None, max_chars: int = 30000) -> str:
    root = (cwd or Path.cwd()).resolve()
    target = (root / path).resolve()
    text = target.read_text(encoding="utf-8", errors="replace")
    suffix = "\n[truncated]" if len(text) > max_chars else ""
    return (
        f"Explain `{path}` for a developer joining this project. "
        "Cover purpose, important functions/classes, dependencies, risks, and how to test changes.\n\n"
        f"```text\n{text[:max_chars]}{suffix}\n```"
    )


def build_fix_prompt(request: str, *, cwd: Path | None = None) -> str:
    index = scan_workspace(cwd=cwd)
    return (
        "Act as a coding agent for this workspace. Inspect relevant files, make the smallest correct change, "
        "run appropriate verification when allowed, and summarize changed files.\n\n"
        f"{workspace_map_markdown(index, max_files=80)}\n"
        f"Task: {request}"
    )
