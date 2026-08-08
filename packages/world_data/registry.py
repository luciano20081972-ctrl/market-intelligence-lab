from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, HttpUrl


class DatasetDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    provider: str
    title: str
    transport: str
    official_url: HttpUrl
    expected_frequency: str
    license: str
    temporal_mode: str


class DatasetRegistry(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    datasets: tuple[DatasetDefinition, ...]

    def get(self, dataset_id: str) -> DatasetDefinition:
        try:
            return next(item for item in self.datasets if item.id == dataset_id)
        except StopIteration as exc:
            raise KeyError(dataset_id) from exc


@lru_cache
def load_dataset_registry(path: Path | None = None) -> DatasetRegistry:
    registry_path = path or Path(__file__).parents[2] / "config" / "datasets.yaml"
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    return DatasetRegistry.model_validate(payload)
