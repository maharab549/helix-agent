from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .history import list_history
from .paths import project_state_dir


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^'\"\s]+"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class LearningConfig:
    enabled: bool = True
    auto_capture: bool = True
    min_prompt_chars: int = 4
    min_response_chars: int = 20
    min_score_for_dataset: float = 0.55
    min_rating_for_dataset: int = 4
    max_examples: int = 5000

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class LearningExample:
    id: str
    created_at: str
    source: str
    prompt: str
    response: str
    system: str = ""
    provider: str = ""
    model: str = ""
    rating: int | None = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetStats:
    path: Path
    examples: int
    skipped: int

    def to_json(self) -> dict[str, object]:
        return {"path": str(self.path), "examples": self.examples, "skipped": self.skipped}


@dataclass(frozen=True)
class DatasetValidation:
    path: Path
    ok: bool
    examples: int
    errors: list[str]

    def to_json(self) -> dict[str, object]:
        return {"path": str(self.path), "ok": self.ok, "examples": self.examples, "errors": self.errors}


def learning_dir(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "learning"


def learning_config_file(*, cwd: Path | None = None) -> Path:
    return learning_dir(cwd=cwd) / "config.json"


def examples_file(*, cwd: Path | None = None) -> Path:
    return learning_dir(cwd=cwd) / "examples.jsonl"


def datasets_dir(*, cwd: Path | None = None) -> Path:
    return learning_dir(cwd=cwd) / "datasets"


def learned_profile_file(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "LEARNED.md"


def load_learning_config(*, cwd: Path | None = None) -> LearningConfig:
    path = learning_config_file(cwd=cwd)
    if not path.exists():
        return LearningConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return LearningConfig()
    if not isinstance(data, dict):
        return LearningConfig()
    config = LearningConfig()
    for key in config.to_json():
        if key in data:
            setattr(config, key, data[key])
    return config


def save_learning_config(config: LearningConfig, *, cwd: Path | None = None) -> Path:
    out = learning_config_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config.to_json(), indent=2) + "\n", encoding="utf-8")
    return out


def set_learning_enabled(enabled: bool, *, cwd: Path | None = None) -> Path:
    config = load_learning_config(cwd=cwd)
    config.enabled = enabled
    config.auto_capture = enabled
    return save_learning_config(config, cwd=cwd)


def redact_text(text: str) -> str:
    cleaned = text
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def fingerprint_example(prompt: str, response: str) -> str:
    digest = hashlib.sha256()
    digest.update(prompt.strip().encode("utf-8", errors="ignore"))
    digest.update(b"\0")
    digest.update(response.strip().encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def score_example(prompt: str, response: str, *, success: bool = True, rating: int | None = None) -> float:
    if rating is not None:
        return max(0.0, min(1.0, rating / 5))
    score = 0.35
    if success:
        score += 0.2
    if len(prompt.strip()) >= 20:
        score += 0.1
    if len(response.strip()) >= 120:
        score += 0.15
    if "```" in response or any(token in response.lower() for token in ["step", "because", "command", "test"]):
        score += 0.1
    if any(token in response.lower() for token in ["traceback", "error:", "i cannot", "i can't"]):
        score -= 0.2
    return round(max(0.0, min(1.0, score)), 3)


def iter_learning_examples(*, cwd: Path | None = None) -> list[LearningExample]:
    path = examples_file(cwd=cwd)
    if not path.exists():
        return []
    examples: list[LearningExample] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            examples.append(LearningExample(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    examples.sort(key=lambda item: item.created_at, reverse=True)
    return examples


def _known_fingerprints(*, cwd: Path | None = None) -> set[str]:
    return {example.fingerprint for example in iter_learning_examples(cwd=cwd) if example.fingerprint}


def _trim_examples(config: LearningConfig, *, cwd: Path | None = None) -> None:
    examples = iter_learning_examples(cwd=cwd)
    if len(examples) <= config.max_examples:
        return
    kept = examples[: config.max_examples]
    out = examples_file(cwd=cwd)
    out.write_text("".join(json.dumps(example.to_json(), ensure_ascii=False) + "\n" for example in kept), encoding="utf-8")


def capture_prompt_response(
    prompt: str,
    response: str,
    *,
    system: str = "",
    provider: str = "",
    model: str = "",
    source: str = "manual",
    rating: int | None = None,
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    success: bool = True,
    force: bool = False,
    cwd: Path | None = None,
) -> LearningExample | None:
    config = load_learning_config(cwd=cwd)
    if not force and (not config.enabled or not config.auto_capture):
        return None

    clean_prompt = redact_text(prompt.strip())
    clean_response = redact_text(response.strip())
    if len(clean_prompt) < config.min_prompt_chars or len(clean_response) < config.min_response_chars:
        return None

    fingerprint = fingerprint_example(clean_prompt, clean_response)
    if fingerprint in _known_fingerprints(cwd=cwd):
        return None

    example = LearningExample(
        id=uuid.uuid4().hex[:12],
        created_at=now_iso(),
        source=source,
        prompt=clean_prompt,
        response=clean_response,
        system=redact_text(system.strip()),
        provider=provider,
        model=model,
        rating=rating,
        score=score_example(clean_prompt, clean_response, success=success, rating=rating),
        tags=[str(tag) for tag in tags or []],
        metadata=metadata or {},
        fingerprint=fingerprint,
    )
    out = examples_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(example.to_json(), ensure_ascii=False) + "\n")
    _trim_examples(config, cwd=cwd)
    return example


def capture_exchange(
    messages: list[dict[str, str]],
    response: str,
    *,
    provider: str = "",
    model: str = "",
    source: str = "exchange",
    rating: int | None = None,
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    capture_system: bool = False,
    force: bool = False,
    cwd: Path | None = None,
) -> LearningExample | None:
    system = ""
    prompt = ""
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system" and not system:
            system = content
        if role == "user" and not content.lstrip().startswith("<tool_result"):
            prompt = content
    return capture_prompt_response(
        prompt,
        response,
        system=system if capture_system else "",
        provider=provider,
        model=model,
        source=source,
        rating=rating,
        tags=tags,
        metadata=metadata,
        force=force,
        cwd=cwd,
    )


def update_example_rating(example_id: str, rating: int, *, cwd: Path | None = None) -> LearningExample:
    if rating < 1 or rating > 5:
        raise ValueError("Rating must be between 1 and 5.")
    examples = iter_learning_examples(cwd=cwd)
    selected: LearningExample | None = None
    for example in examples:
        if example.id.startswith(example_id):
            example.rating = rating
            example.score = score_example(example.prompt, example.response, rating=rating)
            selected = example
            break
    if selected is None:
        raise FileNotFoundError(f"No learning example found for {example_id!r}.")
    out = examples_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(example.to_json(), ensure_ascii=False) + "\n" for example in reversed(examples)), encoding="utf-8")
    return selected


def mine_history(*, limit: int = 200, cwd: Path | None = None) -> int:
    count = 0
    for path in list_history(cwd=cwd, limit=limit):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        messages = data.get("messages")
        response = data.get("response")
        if not isinstance(messages, list) or not isinstance(response, str):
            continue
        example = capture_exchange(
            messages,
            response,
            provider=str(data.get("provider") or ""),
            model=str(data.get("model") or ""),
            source="history",
            metadata={"history_file": str(path)},
            force=True,
            cwd=cwd,
        )
        if example is not None:
            count += 1
    return count


def learning_stats(*, cwd: Path | None = None) -> dict[str, object]:
    examples = iter_learning_examples(cwd=cwd)
    rated = [example for example in examples if example.rating is not None]
    avg_score = round(sum(example.score for example in examples) / len(examples), 3) if examples else 0.0
    return {
        "enabled": load_learning_config(cwd=cwd).enabled,
        "auto_capture": load_learning_config(cwd=cwd).auto_capture,
        "examples": len(examples),
        "rated": len(rated),
        "avg_score": avg_score,
        "examples_file": str(examples_file(cwd=cwd)),
    }


def training_record(example: LearningExample, *, include_system: bool = False) -> dict[str, object]:
    messages: list[dict[str, str]] = []
    if include_system and example.system:
        messages.append({"role": "system", "content": example.system})
    messages.append({"role": "user", "content": example.prompt})
    messages.append({"role": "assistant", "content": example.response})
    return {"messages": messages}


def should_include_example(example: LearningExample, *, min_rating: int | None, min_score: float) -> bool:
    if example.rating is not None:
        return min_rating is None or example.rating >= min_rating
    return example.score >= min_score


def build_dataset(
    *,
    output: Path | None = None,
    min_rating: int | None = None,
    min_score: float | None = None,
    limit: int = 1000,
    include_system: bool = False,
    cwd: Path | None = None,
) -> DatasetStats:
    config = load_learning_config(cwd=cwd)
    resolved_min_rating = config.min_rating_for_dataset if min_rating is None else min_rating
    resolved_min_score = config.min_score_for_dataset if min_score is None else min_score
    selected: list[LearningExample] = []
    skipped = 0
    for example in iter_learning_examples(cwd=cwd):
        if should_include_example(example, min_rating=resolved_min_rating, min_score=resolved_min_score):
            selected.append(example)
        else:
            skipped += 1
        if len(selected) >= limit:
            break

    out = output or datasets_dir(cwd=cwd) / f"helix-train-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for example in reversed(selected):
            handle.write(json.dumps(training_record(example, include_system=include_system), ensure_ascii=False) + "\n")
    return DatasetStats(path=out, examples=len(selected), skipped=skipped)


def validate_dataset(path: Path) -> DatasetValidation:
    errors: list[str] = []
    examples = 0
    allowed_roles = {"system", "developer", "user", "assistant"}
    if not path.exists():
        return DatasetValidation(path=path, ok=False, examples=0, errors=[f"File not found: {path}"])
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue
        messages = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(messages, list) or len(messages) < 2:
            errors.append(f"line {line_number}: expected messages list with at least two messages")
            continue
        roles = [message.get("role") for message in messages if isinstance(message, dict)]
        if "user" not in roles or "assistant" not in roles:
            errors.append(f"line {line_number}: expected at least one user and one assistant message")
        for index, message in enumerate(messages, 1):
            if not isinstance(message, dict):
                errors.append(f"line {line_number} message {index}: expected object")
                continue
            if message.get("role") not in allowed_roles:
                errors.append(f"line {line_number} message {index}: invalid role")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                errors.append(f"line {line_number} message {index}: content is required")
        examples += 1
    return DatasetValidation(path=path, ok=not errors and examples > 0, examples=examples, errors=errors)


def distill_learned_profile(*, cwd: Path | None = None) -> Path:
    examples = iter_learning_examples(cwd=cwd)
    high_quality = [example for example in examples if should_include_example(example, min_rating=4, min_score=0.7)]
    avg_response = int(sum(len(example.response) for example in high_quality) / len(high_quality)) if high_quality else 0
    code_examples = sum(1 for example in high_quality if "```" in example.response)
    tag_counts: dict[str, int] = {}
    for example in high_quality:
        for tag in example.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    common_tags = ", ".join(tag for tag, _ in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:8]) or "none yet"

    lines = [
        "# Helix Learned Profile",
        "",
        f"- Examples reviewed: {len(examples)}",
        f"- High-quality examples: {len(high_quality)}",
        f"- Average high-quality response length: {avg_response} characters",
        f"- High-quality code-heavy examples: {code_examples}",
        f"- Common tags: {common_tags}",
        "",
        "## Operating Preference",
        "",
    ]
    if avg_response and avg_response < 900:
        lines.append("- Prefer concise, direct answers unless the task needs implementation detail.")
    elif avg_response:
        lines.append("- Prefer thorough implementation notes and verification details.")
    else:
        lines.append("- Keep answers practical, explicit, and grounded in the current workspace.")
    if code_examples:
        lines.append("- Include commands, files, and verification steps for coding tasks.")
    lines.append("- Preserve user intent from prior successful examples when similar work appears.")
    out = learned_profile_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out
