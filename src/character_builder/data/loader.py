from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

__all__ = [
    "IndexedCollection",
    "DataRepository",
    "get_repository",
]


RESOURCE_FILES = {
    "ability_scores": "5e-SRD-Ability-Scores.json",
    "alignments": "5e-SRD-Alignments.json",
    "backgrounds": "5e-SRD-Backgrounds.json",
    "classes": "5e-SRD-Classes.json",
    "conditions": "5e-SRD-Conditions.json",
    "damage_types": "5e-SRD-Damage-Types.json",
    "equipment_categories": "5e-SRD-Equipment-Categories.json",
    "equipment": "5e-SRD-Equipment.json",
    "feats": "5e-SRD-Feats.json",
    "features": "5e-SRD-Features.json",
    "languages": "5e-SRD-Languages.json",
    "levels": "5e-SRD-Levels.json",
    "magic_items": "5e-SRD-Magic-Items.json",
    "magic_schools": "5e-SRD-Magic-Schools.json",
    "monsters": "5e-SRD-Monsters.json",
    "proficiencies": "5e-SRD-Proficiencies.json",
    "races": "5e-SRD-Races.json",
    "rule_sections": "5e-SRD-Rule-Sections.json",
    "rules": "5e-SRD-Rules.json",
    "skills": "5e-SRD-Skills.json",
    "spells": "5e-SRD-Spells.json",
    "subclasses": "5e-SRD-Subclasses.json",
    "subraces": "5e-SRD-Subraces.json",
    "traits": "5e-SRD-Traits.json",
    "weapon_properties": "5e-SRD-Weapon-Properties.json",
}


@dataclass(slots=True)
class IndexedCollection:
    """Represents a JSON resource along with useful lookup indexes."""

    source_file: Path
    entries: List[dict]
    by_index: Dict[str, dict]
    by_name: Dict[str, dict]

    @classmethod
    def from_entries(cls, source_file: Path, entries: Iterable[dict]) -> "IndexedCollection":
        entries_list = list(entries)
        by_index = {entry["index"].lower(): entry for entry in entries_list if "index" in entry}
        by_name = {entry["name"].lower(): entry for entry in entries_list if "name" in entry}
        return cls(source_file=source_file, entries=entries_list, by_index=by_index, by_name=by_name)

    def get(self, key: str) -> Optional[dict]:
        """Fetch an entry by index or name (case-insensitive)."""

        if not key:
            return None
        normalized = key.lower()
        return self.by_index.get(normalized) or self.by_name.get(normalized)


class DataRepository:
    """Loads and caches SRD data from the 5e-bits JSON dataset."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = (base_path or _default_dataset_path()).resolve()
        if not self.base_path.exists():
            raise FileNotFoundError(f"SRD dataset not found at {self.base_path}")
        self._cache: Dict[str, IndexedCollection] = {}

    def resource_path(self, resource: str) -> Path:
        try:
            filename = RESOURCE_FILES[resource]
        except KeyError as exc:
            raise KeyError(f"Unknown SRD resource: {resource}") from exc
        return self.base_path / filename

    def load(self, resource: str) -> IndexedCollection:
        if resource not in self._cache:
            path = self.resource_path(resource)
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            # Ensure deterministic ordering by index/name when available.
            payload.sort(key=lambda entry: (entry.get("name") or entry.get("index") or ""))
            self._cache[resource] = IndexedCollection.from_entries(path, payload)
        return self._cache[resource]

    # Convenience accessors -------------------------------------------------
    def classes(self) -> IndexedCollection:
        return self.load("classes")

    def subclasses(self) -> IndexedCollection:
        return self.load("subclasses")

    def races(self) -> IndexedCollection:
        return self.load("races")

    def subraces(self) -> IndexedCollection:
        return self.load("subraces")

    def backgrounds(self) -> IndexedCollection:
        return self.load("backgrounds")

    def feats(self) -> IndexedCollection:
        return self.load("feats")

    def spells(self) -> IndexedCollection:
        return self.load("spells")

    def equipment(self) -> IndexedCollection:
        return self.load("equipment")

    def equipment_categories(self) -> IndexedCollection:
        return self.load("equipment_categories")

    def features(self) -> IndexedCollection:
        return self.load("features")

    def traits(self) -> IndexedCollection:
        return self.load("traits")

    def proficiencies(self) -> IndexedCollection:
        return self.load("proficiencies")

    def skills(self) -> IndexedCollection:
        return self.load("skills")

    def levels(self) -> IndexedCollection:
        return self.load("levels")


@lru_cache(maxsize=1)
def get_repository(base_path: Optional[Path] = None) -> DataRepository:
    return DataRepository(base_path=base_path)


def _default_dataset_path() -> Path:
    current = Path(__file__).resolve()
    project_root = current.parents[3]
    return project_root / "data" / "5e-database" / "src" / "2014"
