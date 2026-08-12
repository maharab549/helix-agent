from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from .agent_runtime import build_messages, run_agent_loop
from .config import AgentConfig
from .context import collect_context_blocks
from .learning import build_dataset, capture_exchange, capture_prompt_response, learning_stats, mine_history, update_example_rating
from .memory import remember, search_memories
from .plugins import PluginError
from .provider import ProviderError, complete
from .skills import load_skill_index, search_skills
from .tuning import auto_fine_tune, start_fine_tune
from .tools_runtime import execute_tool


def _response(request_id: Any, *, ok: bool, result: Any = None, error: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"id": request_id, "ok": ok}
    if ok:
        data["result"] = result
    else:
        data["error"] = error or "Unknown error"
    return data


def handle_rpc_request(config: AgentConfig, request: dict[str, Any], *, cwd: Path | None = None) -> dict[str, Any]:
    request_id = request.get("id")
    method = str(request.get("method") or "")
    raw_params = request.get("params") or {}
    params = raw_params if isinstance(raw_params, dict) else {}
    root = (cwd or Path.cwd()).resolve()

    try:
        if method == "ping":
            return _response(request_id, ok=True, result={"message": "pong"})

        if method == "ask":
            prompt = str(params.get("prompt") or "")
            if not prompt:
                return _response(request_id, ok=False, error="params.prompt is required")
            messages = build_messages(
                config,
                prompt,
                system=params.get("system"),
                skill_queries=list(params.get("skills") or []),
                include_tools=bool(params.get("tools")),
                include_memory=True,
                include_context=True,
            )
            result = complete(
                config,
                messages,
                provider_name=params.get("provider"),
                model=params.get("model"),
                temperature=float(params.get("temperature") or 0.2),
                timeout=int(params.get("timeout") or 120),
            )
            capture_exchange(messages, result.content, provider=result.provider, model=result.model, source="rpc.ask", cwd=root)
            return _response(
                request_id,
                ok=True,
                result={
                    "content": result.content,
                    "provider": result.provider,
                    "model": result.model,
                    "usage": result.usage,
                },
            )

        if method == "agent":
            prompt = str(params.get("prompt") or "")
            if not prompt:
                return _response(request_id, ok=False, error="params.prompt is required")
            result = run_agent_loop(
                config,
                prompt,
                provider_name=params.get("provider"),
                model=params.get("model"),
                system=params.get("system"),
                skill_queries=list(params.get("skills") or []),
                temperature=float(params.get("temperature") or 0.2),
                timeout=int(params.get("timeout") or 120),
                max_steps=int(params.get("max_steps") or 6),
                allow_write=bool(params.get("yes")),
                allow_shell=bool(params.get("yes")),
            )
            return _response(
                request_id,
                ok=True,
                result={
                    "content": result.content,
                    "session": result.session.to_json(),
                    "tool_steps": result.tool_steps,
                },
            )

        if method == "tool":
            tool_args = params.get("args") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}
            result = execute_tool(
                str(params.get("name") or ""),
                tool_args,
                cwd=root,
                allow_write=bool(params.get("yes")),
                allow_shell=bool(params.get("yes")),
            )
            return _response(request_id, ok=result.ok, result={"tool": result.tool, "output": result.output}, error=result.output)

        if method == "skills.list":
            entries = load_skill_index(cwd=root)
            return _response(request_id, ok=True, result=[entry.to_json() for entry in entries])

        if method == "skills.search":
            entries = search_skills(load_skill_index(cwd=root), str(params.get("query") or ""), limit=int(params.get("limit") or 10))
            return _response(request_id, ok=True, result=[entry.to_json() for entry in entries])

        if method == "memory.add":
            text = str(params.get("text") or "")
            if not text:
                return _response(request_id, ok=False, error="params.text is required")
            path = remember(
                text,
                scope=str(params.get("scope") or "project"),
                tags=[str(tag) for tag in params.get("tags") or []],
                cwd=root,
            )
            return _response(request_id, ok=True, result={"path": str(path)})

        if method == "memory.search":
            entries = search_memories(str(params.get("query") or ""), limit=int(params.get("limit") or 10), cwd=root)
            return _response(request_id, ok=True, result=[entry.to_json() for entry in entries])

        if method == "learn.status":
            return _response(request_id, ok=True, result=learning_stats(cwd=root))

        if method == "learn.add":
            example = capture_prompt_response(
                str(params.get("prompt") or ""),
                str(params.get("response") or ""),
                rating=params.get("rating"),
                tags=[str(tag) for tag in params.get("tags") or []],
                source="rpc",
                force=True,
                cwd=root,
            )
            if example is None:
                return _response(request_id, ok=False, error="Learning example was skipped")
            return _response(request_id, ok=True, result=example.to_json())

        if method == "learn.rate":
            example = update_example_rating(str(params.get("id") or ""), int(params.get("rating") or 0), cwd=root)
            return _response(request_id, ok=True, result=example.to_json())

        if method == "learn.mine_history":
            return _response(request_id, ok=True, result={"examples": mine_history(limit=int(params.get("limit") or 200), cwd=root)})

        if method == "learn.dataset":
            dataset = build_dataset(
                output=Path(params["output"]) if params.get("output") else None,
                min_rating=params.get("min_rating"),
                min_score=params.get("min_score"),
                limit=int(params.get("limit") or 1000),
                include_system=bool(params.get("include_system")),
                cwd=root,
            )
            return _response(request_id, ok=True, result=dataset.to_json())

        if method == "finetune.start":
            dataset = Path(str(params.get("dataset") or ""))
            result = start_fine_tune(
                config,
                dataset,
                provider_name=params.get("provider"),
                base_model=str(params.get("base_model") or ""),
                n_epochs=params.get("n_epochs"),
                dry_run=bool(params.get("dry_run")),
                timeout=int(params.get("timeout") or 120),
                cwd=root,
            )
            return _response(request_id, ok=bool(result.get("ok")), result=result, error=json.dumps(result))

        if method == "finetune.auto":
            result = auto_fine_tune(
                config,
                provider_name=params.get("provider"),
                base_model=str(params.get("base_model") or ""),
                min_rating=params.get("min_rating"),
                min_score=params.get("min_score"),
                limit=int(params.get("limit") or 1000),
                min_examples=int(params.get("min_examples") or 1),
                mine_history_limit=int(params.get("mine_history") or 0),
                distill=bool(params.get("distill")),
                n_epochs=params.get("n_epochs"),
                dry_run=bool(params.get("dry_run")),
                timeout=int(params.get("timeout") or 120),
                cwd=root,
            )
            return _response(request_id, ok=bool(result.get("ok")), result=result, error=json.dumps(result))

        if method == "context":
            blocks = collect_context_blocks(cwd=root, max_chars=int(params.get("max_chars") or 12000))
            return _response(request_id, ok=True, result=[block.to_json() for block in blocks])

        return _response(request_id, ok=False, error=f"Unknown method: {method}")
    except (PluginError, ProviderError, OSError, ValueError, TimeoutError) as exc:
        return _response(request_id, ok=False, error=f"{type(exc).__name__}: {exc}")


def run_rpc(
    config: AgentConfig,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    source = input_stream or sys.stdin
    sink = output_stream or sys.stdout
    for line in source:
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except json.JSONDecodeError as exc:
            response = _response(None, ok=False, error=f"JSONDecodeError: {exc}")
        else:
            if not isinstance(request, dict):
                response = _response(None, ok=False, error="Request must be a JSON object")
            else:
                response = handle_rpc_request(config, request, cwd=cwd)
        sink.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
        sink.flush()
    return 0
