from __future__ import annotations

import json
import os
import uuid
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import AgentConfig, ProviderConfig, save_config
from .learning import build_dataset, distill_learned_profile, mine_history, validate_dataset
from .paths import project_state_dir
from .provider import ProviderError, resolve_provider


@dataclass
class FineTuneRecord:
    id: str
    provider: str
    base_model: str
    dataset: str
    file_id: str = ""
    status: str = "created"
    fine_tuned_model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def fine_tune_records_file(*, cwd: Path | None = None) -> Path:
    return project_state_dir(cwd) / "fine_tunes.json"


def load_records(*, cwd: Path | None = None) -> list[FineTuneRecord]:
    path = fine_tune_records_file(cwd=cwd)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records: list[FineTuneRecord] = []
    for item in data if isinstance(data, list) else []:
        try:
            records.append(FineTuneRecord(**item))
        except TypeError:
            continue
    return records


def save_records(records: list[FineTuneRecord], *, cwd: Path | None = None) -> Path:
    out = fine_tune_records_file(cwd=cwd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([record.to_json() for record in records], indent=2) + "\n", encoding="utf-8")
    return out


def upsert_record(record: FineTuneRecord, *, cwd: Path | None = None) -> Path:
    records = load_records(cwd=cwd)
    kept = [item for item in records if item.id != record.id]
    kept.append(record)
    return save_records(kept, cwd=cwd)


def api_base_from_provider(provider: ProviderConfig) -> str:
    base = provider.base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1") if provider.name == "openai" else base


def _api_key(provider: ProviderConfig) -> str:
    api_key = os.environ.get(provider.api_key_env) if provider.api_key_env else ""
    if not api_key:
        raise ProviderError(
            f"{provider.name} needs {provider.api_key_env} for fine-tuning. "
            f"Set it or run `helix auth set {provider.name} <api-key>`."
        )
    return api_key


def _request_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None, *, timeout: int = 120) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach fine-tuning API: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Fine-tuning API returned invalid JSON") from exc


def _multipart_body(path: Path, *, purpose: str) -> tuple[bytes, str]:
    boundary = f"helix-{uuid.uuid4().hex}"
    file_bytes = path.read_bytes()
    filename = path.name.replace('"', "")
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\n{purpose}\r\n".encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/jsonl\r\n\r\n"
        ).encode("utf-8"),
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(chunks), boundary


def upload_training_file(provider: ProviderConfig, dataset_path: Path, *, timeout: int = 120) -> dict[str, Any]:
    api_key = _api_key(provider)
    body, boundary = _multipart_body(dataset_path, purpose="fine-tune")
    request = urllib.request.Request(
        f"{api_base_from_provider(provider)}/files",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not upload training file: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("File upload returned invalid JSON") from exc


def fine_tune_payload(
    *,
    training_file: str,
    base_model: str,
    validation_file: str | None = None,
    n_epochs: int | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"training_file": training_file, "model": base_model}
    if validation_file:
        payload["validation_file"] = validation_file
    if n_epochs is not None:
        payload["method"] = {
            "type": "supervised",
            "supervised": {"hyperparameters": {"n_epochs": n_epochs}},
        }
    if metadata:
        payload["metadata"] = metadata
    return payload


def create_fine_tune_job(
    provider: ProviderConfig,
    *,
    training_file: str,
    base_model: str,
    validation_file: str | None = None,
    n_epochs: int | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    payload = fine_tune_payload(
        training_file=training_file,
        base_model=base_model,
        validation_file=validation_file,
        n_epochs=n_epochs,
        metadata={"created_by": "helix-agent"},
    )
    return _request_json("POST", f"{api_base_from_provider(provider)}/fine_tuning/jobs", _api_key(provider), payload, timeout=timeout)


def retrieve_fine_tune_job(provider: ProviderConfig, job_id: str, *, timeout: int = 120) -> dict[str, Any]:
    return _request_json("GET", f"{api_base_from_provider(provider)}/fine_tuning/jobs/{job_id}", _api_key(provider), timeout=timeout)


def list_fine_tune_jobs(provider: ProviderConfig, *, limit: int = 20, timeout: int = 120) -> dict[str, Any]:
    return _request_json("GET", f"{api_base_from_provider(provider)}/fine_tuning/jobs?limit={limit}", _api_key(provider), timeout=timeout)


def cancel_fine_tune_job(provider: ProviderConfig, job_id: str, *, timeout: int = 120) -> dict[str, Any]:
    return _request_json("POST", f"{api_base_from_provider(provider)}/fine_tuning/jobs/{job_id}/cancel", _api_key(provider), {}, timeout=timeout)


def start_fine_tune(
    config: AgentConfig,
    dataset_path: Path,
    *,
    provider_name: str | None,
    base_model: str,
    n_epochs: int | None = None,
    dry_run: bool = False,
    timeout: int = 120,
    cwd: Path | None = None,
) -> dict[str, Any]:
    validation = validate_dataset(dataset_path)
    if not validation.ok:
        return {"ok": False, "validation": validation.to_json()}
    provider = resolve_provider(config, provider_name)
    payload = fine_tune_payload(
        training_file="file-will-be-created",
        base_model=base_model,
        n_epochs=n_epochs,
        metadata={"created_by": "helix-agent"},
    )
    if dry_run:
        return {"ok": True, "dry_run": True, "provider": provider.name, "dataset": str(dataset_path), "payload": payload}

    file_data = upload_training_file(provider, dataset_path, timeout=timeout)
    file_id = str(file_data.get("id") or "")
    job_data = create_fine_tune_job(
        provider,
        training_file=file_id,
        base_model=base_model,
        n_epochs=n_epochs,
        timeout=timeout,
    )
    record = FineTuneRecord(
        id=str(job_data.get("id") or ""),
        provider=provider.name,
        base_model=base_model,
        dataset=str(dataset_path),
        file_id=file_id,
        status=str(job_data.get("status") or "created"),
        fine_tuned_model=str(job_data.get("fine_tuned_model") or ""),
        raw=job_data,
    )
    upsert_record(record, cwd=cwd)
    return {"ok": True, "file": file_data, "job": job_data, "record": record.to_json()}


def auto_fine_tune(
    config: AgentConfig,
    *,
    provider_name: str | None,
    base_model: str,
    min_rating: int | None = None,
    min_score: float | None = None,
    limit: int = 1000,
    n_epochs: int | None = None,
    min_examples: int = 1,
    mine_history_limit: int = 0,
    distill: bool = False,
    dry_run: bool = False,
    timeout: int = 120,
    cwd: Path | None = None,
) -> dict[str, Any]:
    mined = mine_history(limit=mine_history_limit, cwd=cwd) if mine_history_limit > 0 else 0
    profile_path = distill_learned_profile(cwd=cwd) if distill else None
    dataset = build_dataset(min_rating=min_rating, min_score=min_score, limit=limit, cwd=cwd)
    if dataset.examples < min_examples:
        return {
            "ok": False,
            "reason": f"Need at least {min_examples} training examples; dataset has {dataset.examples}.",
            "mined": mined,
            "learned_profile": str(profile_path) if profile_path else "",
            "dataset_stats": dataset.to_json(),
            "validation": validate_dataset(dataset.path).to_json(),
        }
    result = start_fine_tune(
        config,
        dataset.path,
        provider_name=provider_name,
        base_model=base_model,
        n_epochs=n_epochs,
        dry_run=dry_run,
        timeout=timeout,
        cwd=cwd,
    )
    result["mined"] = mined
    result["learned_profile"] = str(profile_path) if profile_path else ""
    result["dataset_stats"] = dataset.to_json()
    return result


def refresh_record(config: AgentConfig, job_id: str, *, provider_name: str | None = None, timeout: int = 120, cwd: Path | None = None) -> dict[str, Any]:
    existing = next((record for record in load_records(cwd=cwd) if record.id.startswith(job_id)), None)
    provider = resolve_provider(config, provider_name or (existing.provider if existing else None))
    data = retrieve_fine_tune_job(provider, existing.id if existing else job_id, timeout=timeout)
    record = FineTuneRecord(
        id=str(data.get("id") or (existing.id if existing else job_id)),
        provider=provider.name,
        base_model=str(data.get("model") or (existing.base_model if existing else "")),
        dataset=existing.dataset if existing else "",
        file_id=str(data.get("training_file") or (existing.file_id if existing else "")),
        status=str(data.get("status") or ""),
        fine_tuned_model=str(data.get("fine_tuned_model") or ""),
        raw=data,
    )
    upsert_record(record, cwd=cwd)
    return data


def adopt_fine_tuned_model(
    config: AgentConfig,
    job_id: str,
    *,
    provider_name: str,
    new_provider_name: str,
    cwd: Path | None = None,
) -> FineTuneRecord:
    record = next((item for item in load_records(cwd=cwd) if item.id.startswith(job_id)), None)
    if record is None:
        raise FileNotFoundError(f"No fine-tune record found for {job_id!r}.")
    if not record.fine_tuned_model:
        raise ValueError("Fine-tuned model is not ready yet. Run `helix finetune status <job-id>` first.")
    source = resolve_provider(config, provider_name or record.provider)
    provider = ProviderConfig(
        name=new_provider_name,
        kind=source.kind,
        model=record.fine_tuned_model,
        base_url=source.base_url,
        api_key_env=source.api_key_env,
    )
    config.providers[new_provider_name] = provider
    config.default_provider = new_provider_name
    save_config(config)
    return record
