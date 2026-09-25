from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import uuid

from .media import MediaPrompt


@dataclass(frozen=True)
class MediaArtifact:
    artifact_id: str
    provider: str
    path: str
    metadata: dict


class MediaProvider:
    name = "base"

    def generate(self, prompt: MediaPrompt, output_dir: str | Path) -> MediaArtifact:
        raise NotImplementedError


class MockMediaProvider(MediaProvider):
    name = "mock"

    def generate(self, prompt: MediaPrompt, output_dir: str | Path) -> MediaArtifact:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        artifact_id = uuid.uuid4().hex
        path = directory / f"{artifact_id}.json"
        path.write_text(
            json.dumps({"prompt": prompt.to_dict(), "provider": self.name}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return MediaArtifact(artifact_id, self.name, str(path), {"kind": prompt.kind})


class LocalMediaProvider(MockMediaProvider):
    name = "local"
