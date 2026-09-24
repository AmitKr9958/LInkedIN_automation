from __future__ import annotations
import importlib
from dataclasses import dataclass

@dataclass
class Health:
    ok: bool
    checks: dict[str,str]

def check() -> Health:
    checks={}
    for name in ("playwright","typer","pydantic","dotenv"):
        try:
            importlib.import_module(name); checks[name]="ok"
        except Exception as exc: checks[name]=f"error: {exc}"
    return Health(all(v=="ok" for v in checks.values()),checks)
