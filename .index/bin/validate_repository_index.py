#!/usr/bin/env python3
"""Validate `.index/` run, manifest, and entry payloads."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import jsonschema

SCRIPT = Path(__file__).resolve()
INDEX_ROOT = SCRIPT.parents[1]
REPO_ROOT = SCRIPT.parents[2]
CONTRACT_ROOT = INDEX_ROOT / "contracts"

RUN_CONTRACT_PATH = CONTRACT_ROOT / "repository-index-run-v1.json"
MANIFEST_CONTRACT_PATH = CONTRACT_ROOT / "repository-index-manifest-v1.json"
ENTRY_CONTRACT_PATH = CONTRACT_ROOT / "repository-index-entry-v1.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_contract(path: Path) -> dict[str, Any]:
    return load_json(path)


def resolve_repo_path(path_str: str) -> tuple[Path | None, str | None]:
    candidate = (REPO_ROOT / path_str).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None, f"path escapes repo root: {path_str}"
    return candidate, None


def ensure_datetime(value: Any, label: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{label} must be a non-empty date-time string"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{label} must be a valid date-time string"
    return None


def validate_schema(payload: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    return [f"{label}: {error.message}" for error in validator.iter_errors(payload)]


def path_within_scope(path_str: str, scope_paths: list[str]) -> bool:
    resolved, error = resolve_repo_path(path_str)
    if error or resolved is None:
        return False
    for scope_path in scope_paths:
        scope_resolved, scope_error = resolve_repo_path(scope_path)
        if scope_error or scope_resolved is None:
            continue
        if resolved == scope_resolved or scope_resolved in resolved.parents:
            return True
    return False


def gather_entry_paths(entry: dict[str, Any]) -> list[str]:
    collected: list[str] = []
    for field in ("boundary_paths", "important_files"):
        value = entry.get(field, [])
        if isinstance(value, list):
            collected.extend(item for item in value if isinstance(item, str))
    for field in ("inputs", "outputs"):
        value = entry.get(field, [])
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                paths = item.get("paths", [])
                if isinstance(paths, list):
                    collected.extend(path for path in paths if isinstance(path, str))
    interfaces = entry.get("public_interfaces", [])
    if isinstance(interfaces, list):
        for item in interfaces:
            if isinstance(item, dict) and isinstance(item.get("location"), str):
                collected.append(item["location"])
    return collected


def validate_entry_payload(
    entry_path: Path,
    scope_mode: str,
    scope_paths: list[str],
    expected_entry_id: str | None = None,
) -> list[str]:
    errors: list[str] = []
    entry = load_json(entry_path)
    entry_contract = load_contract(ENTRY_CONTRACT_PATH)
    errors.extend(validate_schema(entry, entry_contract, str(entry_path)))

    contract_error = ensure_datetime(entry.get("captured_at"), f"{entry_path}: captured_at") if "captured_at" in entry else None
    if contract_error is not None:
        errors.append(contract_error)

    if expected_entry_id is not None and entry.get("entry_id") != expected_entry_id:
        errors.append(
            f"{entry_path}: entry_id mismatch; manifest has {expected_entry_id!r} but entry has {entry.get('entry_id')!r}"
        )

    path_fields = gather_entry_paths(entry)
    for path_str in path_fields:
        resolved, path_error = resolve_repo_path(path_str)
        if path_error is not None:
            errors.append(f"{entry_path}: {path_error}")
            continue
        if resolved is None or not resolved.exists():
            errors.append(f"{entry_path}: referenced path does not exist: {path_str}")
            continue
        if scope_mode == "scoped_refresh" and not path_within_scope(path_str, scope_paths):
            errors.append(
                f"{entry_path}: referenced path escapes declared scope: {path_str}"
            )

    return errors


def validate_manifest_payload(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    manifest = load_json(manifest_path)
    manifest_contract = load_contract(MANIFEST_CONTRACT_PATH)
    errors.extend(validate_schema(manifest, manifest_contract, str(manifest_path)))

    generated_error = ensure_datetime(manifest.get("generated_at"), f"{manifest_path}: generated_at")
    if generated_error is not None:
        errors.append(generated_error)

    entries = manifest.get("entries", [])
    counters = manifest.get("counters", {})
    if isinstance(entries, list) and isinstance(counters, dict):
        if counters.get("entry_count") != len(entries):
            errors.append(
                f"{manifest_path}: counters.entry_count must equal len(entries)"
            )
        status_counts = {
            "fresh": 0,
            "reused": 0,
            "stale": 0,
            "error": 0,
        }
        for item in entries:
            if isinstance(item, dict):
                status = item.get("status")
                if status in status_counts:
                    status_counts[status] += 1
        for status, counter_field in (
            ("fresh", "fresh_count"),
            ("reused", "reused_count"),
            ("stale", "stale_count"),
            ("error", "error_count"),
        ):
            if counters.get(counter_field) != status_counts[status]:
                errors.append(
                    f"{manifest_path}: counters.{counter_field} must match entry status counts"
                )

    error_block = manifest.get("errors", {})
    if isinstance(error_block, dict):
        items = error_block.get("items", [])
        if error_block.get("count") != len(items):
            errors.append(f"{manifest_path}: errors.count must equal len(errors.items)")

    stale_block = manifest.get("stale", {})
    stale_ids = stale_block.get("entry_ids", []) if isinstance(stale_block, dict) else []
    entry_ids_by_status = {
        item.get("entry_id")
        for item in entries
        if isinstance(item, dict) and item.get("status") == "stale"
    }
    if any(entry_id not in entry_ids_by_status for entry_id in stale_ids):
        errors.append(
            f"{manifest_path}: stale.entry_ids must reference only manifest entries with status='stale'"
        )

    scope = manifest.get("scope", {})
    scope_paths = scope.get("paths", []) if isinstance(scope, dict) else []
    mode = manifest.get("mode")

    for item in entries:
        if not isinstance(item, dict):
            continue
        entry_rel = item.get("path")
        if not isinstance(entry_rel, str) or not entry_rel.strip():
            continue
        resolved_entry, entry_error = resolve_repo_path(entry_rel)
        if entry_error is not None:
            errors.append(f"{manifest_path}: {entry_error}")
            continue
        if resolved_entry is None or not resolved_entry.exists():
            errors.append(f"{manifest_path}: manifest entry points to missing file: {entry_rel}")
            continue
        errors.extend(
            validate_entry_payload(
                resolved_entry,
                scope_mode=mode,
                scope_paths=scope_paths,
                expected_entry_id=item.get("entry_id") if isinstance(item.get("entry_id"), str) else None,
            )
        )

    return errors


def validate_run_payload(run_path: Path) -> list[str]:
    errors: list[str] = []
    run = load_json(run_path)
    run_contract = load_contract(RUN_CONTRACT_PATH)
    errors.extend(validate_schema(run, run_contract, str(run_path)))

    generated_error = ensure_datetime(run.get("generated_at"), f"{run_path}: generated_at")
    if generated_error is not None:
        errors.append(generated_error)

    manifest_rel = run.get("manifest_path")
    summary_rel = run.get("summary_path")
    if isinstance(manifest_rel, str):
        manifest_path, manifest_error = resolve_repo_path(manifest_rel)
        if manifest_error is not None:
            errors.append(f"{run_path}: {manifest_error}")
        elif manifest_path is None or not manifest_path.exists():
            errors.append(f"{run_path}: manifest_path does not exist: {manifest_rel}")
        else:
            errors.extend(validate_manifest_payload(manifest_path))
            manifest = load_json(manifest_path)
            for field in ("repo_id", "mode", "scope"):
                if manifest.get(field) != run.get(field):
                    errors.append(
                        f"{run_path}: run.{field} must match manifest.{field}"
                    )
    if isinstance(summary_rel, str):
        summary_path, summary_error = resolve_repo_path(summary_rel)
        if summary_error is not None:
            errors.append(f"{run_path}: {summary_error}")
        elif summary_path is None or not summary_path.exists() or not summary_path.is_file():
            errors.append(f"{run_path}: summary_path does not exist as a file: {summary_rel}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="Path to a repository-index run JSON.")
    parser.add_argument("--manifest", type=Path, help="Path to a repository-index manifest JSON.")
    parser.add_argument("--entry", type=Path, help="Path to a repository-index entry JSON.")
    args = parser.parse_args()

    requested = [value for value in (args.run, args.manifest, args.entry) if value is not None]
    if len(requested) != 1:
        parser.error("provide exactly one of --run, --manifest, or --entry")

    target = requested[0]
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()

    if args.run is not None:
        errors = validate_run_payload(target)
    elif args.manifest is not None:
        errors = validate_manifest_payload(target)
    else:
        errors = validate_entry_payload(target, scope_mode="full_refresh", scope_paths=[])

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"repository index validation passed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
