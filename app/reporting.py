from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable


def export_rows(rows: Iterable[dict], path: str | Path, fmt: str = "json") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = [dict(row) for row in rows]
    if fmt == "json":
        destination.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    elif fmt == "csv":
        fields = sorted({key for row in data for key in row})
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    else:
        raise ValueError("fmt must be json or csv")
    return destination


def application_rows(rows: Iterable[tuple]) -> list[dict]:
    fields = ["job_url", "title", "company", "status", "updated_at", "notes"]
    return [dict(zip(fields, row)) for row in rows]
