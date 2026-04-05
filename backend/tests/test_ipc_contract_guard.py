from __future__ import annotations

import ast
from pathlib import Path

WIRE_FIELDS = {
    "v",
    "type",
    "id",
    "method",
    "params",
    "result",
    "error",
    "event",
    "data",
    "meta",
}


def _is_dataclass_decorator(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "dataclass"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id == "dataclass"
    return False


def _dataclass_field_names(node: ast.ClassDef) -> set[str]:
    fields: set[str] = set()
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    fields.add(target.id)
    return fields


def _looks_like_wire_dataclass(node: ast.ClassDef) -> bool:
    if not any(_is_dataclass_decorator(deco) for deco in node.decorator_list):
        return False
    fields = _dataclass_field_names(node)
    return len(fields & WIRE_FIELDS) >= 2


def test_no_local_wire_model_class_definitions_outside_shared_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_dirs = [
        repo_root / "backend" / "flow_engine" / "ipc",
        repo_root / "frontend" / "flow_hud" / "plugins" / "ipc",
    ]

    offenders: list[str] = []
    for runtime_dir in runtime_dirs:
        for path in runtime_dir.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and _looks_like_wire_dataclass(node):
                    offenders.append(f"{path}: class {node.name}")

    assert offenders == [], (
        "IPC wire-like dataclasses must live in shared/flow_ipc only; local runtime definitions are forbidden.\n"
        + "\n".join(offenders)
    )


def test_contract_guard_detects_renamed_wire_like_dataclass() -> None:
    sample = """
from dataclasses import dataclass

@dataclass
class TransportEnvelope:
    id: str
    method: str
    params: dict
    v: int = 2
    type: str = "request"
"""
    tree = ast.parse(sample)
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert any(_looks_like_wire_dataclass(node) for node in classes)
