"""JSON export / import of the complete project state (re-loadable)."""
from __future__ import annotations

import json
from pathlib import Path

from models.data_models import ProjectState


def export_json(state: ProjectState, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json(indent=1), encoding="utf-8")
    return str(path)


def load_project_json(path: str | Path) -> ProjectState:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("format") != "graphinsight-project":
        raise ValueError("Not a GraphInsight project file.")
    return ProjectState.from_dict(d)
