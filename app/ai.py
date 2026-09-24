from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass
class AIResult:
    text: str
    provider: str

class AIProvider:
    def generate(self, instruction: str, context: str = "") -> AIResult:
        raise NotImplementedError

class TemplateProvider(AIProvider):
    def generate(self, instruction: str, context: str = "") -> AIResult:
        return AIResult(f"{instruction}\n\n{context}".strip(), "template")

def get_provider() -> AIProvider:
    provider=os.getenv("LLM_PROVIDER","none").lower()
    # Deliberately keep provider adapters optional; no API key is required for core operation.
    if provider in {"none","template"}:
        return TemplateProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER={provider}")
