from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .history import save_exchange
from .paths import project_state_dir
from .provider import ProviderError, complete


def now_ts() -> float:
    return time.time()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ScheduledJob:
    id: str
    prompt: str
    every_seconds: int
    provider: str | None = None
    model: str | None = None
    enabled: bool = True
    next_run: float = field(default_factory=now_ts)
    created_at: str = field(default_factory=now_iso)
    last_result: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def schedule_file(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "schedule.json"


def load_jobs(*, cwd: Path | None = None) -> list[ScheduledJob]:
    path = schedule_file(cwd=cwd)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    jobs: list[ScheduledJob] = []
    for item in data:
        try:
            jobs.append(ScheduledJob(**item))
        except TypeError:
            continue
    return jobs


def save_jobs(jobs: list[ScheduledJob], *, cwd: Path | None = None) -> Path:
    out = schedule_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([job.to_json() for job in jobs], indent=2) + "\n", encoding="utf-8")
    return out


def add_job(prompt: str, *, every_seconds: int, provider: str | None = None, model: str | None = None) -> ScheduledJob:
    jobs = load_jobs()
    job = ScheduledJob(id=uuid.uuid4().hex[:10], prompt=prompt, every_seconds=every_seconds, provider=provider, model=model)
    jobs.append(job)
    save_jobs(jobs)
    return job


def remove_job(selector: str) -> bool:
    jobs = load_jobs()
    kept = [job for job in jobs if not job.id.startswith(selector)]
    changed = len(kept) != len(jobs)
    if changed:
        save_jobs(kept)
    return changed


def run_due_jobs(config: AgentConfig, *, force: bool = False, timeout: int = 120) -> list[ScheduledJob]:
    jobs = load_jobs()
    updated: list[ScheduledJob] = []
    current = now_ts()
    for job in jobs:
        if not job.enabled or (not force and job.next_run > current):
            updated.append(job)
            continue
        messages = [{"role": "system", "content": config.system_prompt}, {"role": "user", "content": job.prompt}]
        try:
            result = complete(config, messages, provider_name=job.provider, model=job.model, timeout=timeout)
            job.last_result = result.content
            save_exchange(messages, result.content, provider=result.provider, model=result.model)
        except ProviderError as exc:
            job.last_result = f"ERROR: {exc}"
        job.next_run = current + job.every_seconds
        updated.append(job)
    save_jobs(updated)
    return updated
