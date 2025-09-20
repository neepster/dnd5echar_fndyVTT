from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .loader import DataRepository, IndexedCollection, get_repository

__all__ = [
    "index_from_url",
    "SRDData",
]


def index_from_url(url: str) -> str:
    """Extract the SRD index identifier from an API-style URL."""

    return url.rstrip("/").split("/")[-1].lower()


def _resolve(entries: Iterable[dict], collection: IndexedCollection) -> List[dict]:
    resolved: List[dict] = []
    for entry in entries:
        url = entry.get("url")
        idx = entry.get("index")
        if url:
            idx = index_from_url(url)
        if not idx:
            continue
        resolved_entry = collection.by_index.get(idx.lower())
        if resolved_entry:
            resolved.append(resolved_entry)
    return resolved


@dataclass(slots=True)
class ClassLevel:
    level: int
    prof_bonus: int
    ability_score_bonuses: int
    features: List[dict]
    spellcasting: Optional[dict] = None
    class_specific: Optional[dict] = None


@dataclass(slots=True)
class SubclassData:
    index: str
    name: str
    description: List[str]
    class_index: str
    flavor: Optional[str]
    features_by_level: Dict[int, List[dict]] = field(default_factory=dict)


@dataclass(slots=True)
class ClassData:
    index: str
    name: str
    hit_die: int
    proficiencies: List[dict]
    proficiency_choices: List[dict]
    saving_throws: List[dict]
    starting_equipment: dict
    spellcasting: Optional[dict]
    levels: Dict[int, ClassLevel]
    subclasses: Dict[str, SubclassData]


@dataclass(slots=True)
class SubraceData:
    index: str
    name: str
    description: List[str]
    ability_bonuses: List[dict]
    proficiencies: List[dict]
    traits: List[dict]
    languages: List[dict]
    language_options: Optional[dict] = None


@dataclass(slots=True)
class RaceData:
    index: str
    name: str
    speed: int
    ability_bonuses: List[dict]
    alignment: Optional[str]
    age: Optional[str]
    size: Optional[str]
    size_description: Optional[str]
    starting_proficiencies: List[dict]
    starting_proficiency_options: Optional[dict]
    languages: List[dict]
    language_desc: Optional[str]
    language_options: Optional[dict]
    traits: List[dict]
    subraces: Dict[str, SubraceData]


@dataclass(slots=True)
class BackgroundData:
    index: str
    name: str
    starting_proficiencies: List[dict]
    starting_proficiencies_options: Optional[dict]
    language_options: Optional[dict]
    equipment: List[str]
    feature: Optional[dict]
    personality_traits: Optional[dict]
    ideals: Optional[dict]
    bonds: Optional[dict]
    flaws: Optional[dict]


class SRDData:
    """High-level façade across SRD resources with resolved relationships."""

    def __init__(self, repository: Optional[DataRepository] = None) -> None:
        self.repo = repository or get_repository()
        self._features = self.repo.features()
        self._traits = self.repo.traits()
        self._proficiencies = self.repo.proficiencies()
        self._languages = self.repo.load("languages")
        self._spells = self.repo.spells()

        self.classes = self._build_classes()
        self.races = self._build_races()
        self.backgrounds = self._build_backgrounds()
        self.feats = {feat["index"]: feat for feat in self.repo.feats().entries}
        self.spells = {spell["index"]: spell for spell in self._spells.entries}
        self.equipment = {item["index"]: item for item in self.repo.equipment().entries}
        self.skills = {skill["index"]: skill for skill in self.repo.skills().entries}
        self.proficiencies = self._proficiencies.by_index
        self.alignments = self.repo.load("alignments").entries

    # ------------------------------------------------------------------
    def _build_classes(self) -> Dict[str, ClassData]:
        classes: Dict[str, ClassData] = {}
        levels = self.repo.levels().entries
        subclass_index: Dict[str, Dict[int, List[dict]]] = {}

        for level_entry in levels:
            if "subclass" in level_entry:
                subclass_idx = level_entry["subclass"]["index"].lower()
                feature_refs = level_entry.get("features", [])
                resolved_features = _resolve(feature_refs, self._features)
                level = level_entry["level"]
                by_level = subclass_index.setdefault(subclass_idx, {})
                by_level[level] = resolved_features

        subclass_payload: Dict[str, SubclassData] = {}
        for subclass in self.repo.subclasses().entries:
            idx = subclass["index"].lower()
            class_idx = subclass["class"]["index"].lower()
            features_by_level = subclass_index.get(idx, {})
            subclass_payload.setdefault(class_idx, {})[idx] = SubclassData(
                index=idx,
                name=subclass["name"],
                description=subclass.get("desc", []),
                class_index=class_idx,
                flavor=subclass.get("subclass_flavor"),
                features_by_level=features_by_level,
            )

        for class_entry in self.repo.classes().entries:
            idx = class_entry["index"].lower()
            class_levels = {
                entry["level"]: ClassLevel(
                    level=entry["level"],
                    prof_bonus=entry.get("prof_bonus", 0),
                    ability_score_bonuses=entry.get("ability_score_bonuses", 0),
                    features=_resolve(entry.get("features", []), self._features),
                    spellcasting=entry.get("spellcasting"),
                    class_specific=entry.get("class_specific"),
                )
                for entry in levels
                if entry["class"]["index"].lower() == idx and "subclass" not in entry
            }

            classes[idx] = ClassData(
                index=idx,
                name=class_entry["name"],
                hit_die=class_entry.get("hit_die", 0),
                proficiencies=_resolve(class_entry.get("proficiencies", []), self._proficiencies),
                proficiency_choices=class_entry.get("proficiency_choices", []),
                saving_throws=_resolve(class_entry.get("saving_throws", []), self._proficiencies),
                starting_equipment=class_entry.get("starting_equipment", {}),
                spellcasting=class_entry.get("spellcasting"),
                levels=class_levels,
                subclasses=subclass_payload.get(idx, {}),
            )
        return classes

    def _build_races(self) -> Dict[str, RaceData]:
        subraces_by_index: Dict[str, SubraceData] = {}
        for subrace in self.repo.subraces().entries:
            idx = subrace["index"].lower()
            subraces_by_index[idx] = SubraceData(
                index=idx,
                name=subrace["name"],
                description=subrace.get("desc", []),
                ability_bonuses=subrace.get("ability_bonuses", []),
                proficiencies=_resolve(subrace.get("proficiencies", []), self._proficiencies),
                traits=_resolve(subrace.get("racial_traits", []), self._traits),
                languages=_resolve(subrace.get("languages", []), self._languages),
                language_options=subrace.get("language_options"),
            )

        races: Dict[str, RaceData] = {}
        for race in self.repo.races().entries:
            idx = race["index"].lower()
            subrace_map: Dict[str, SubraceData] = {}
            for subrace_ref in race.get("subraces", []):
                subrace_idx = subrace_ref.get("index") or index_from_url(subrace_ref.get("url", ""))
                if subrace_idx:
                    subrace = subraces_by_index.get(subrace_idx.lower())
                    if subrace:
                        subrace_map[subrace.index] = subrace

            races[idx] = RaceData(
                index=idx,
                name=race["name"],
                speed=race.get("speed", 30),
                ability_bonuses=race.get("ability_bonuses", []),
                alignment=race.get("alignment"),
                age=race.get("age"),
                size=race.get("size"),
                size_description=race.get("size_description"),
                starting_proficiencies=_resolve(race.get("starting_proficiencies", []), self._proficiencies),
                starting_proficiency_options=race.get("starting_proficiency_options"),
                languages=_resolve(race.get("languages", []), self._languages),
                language_desc=race.get("language_desc"),
                language_options=race.get("language_options"),
                traits=_resolve(race.get("traits", []), self._traits),
                subraces=subrace_map,
            )
        return races

    def _build_backgrounds(self) -> Dict[str, BackgroundData]:
        backgrounds: Dict[str, BackgroundData] = {}
        equipment_collection = self.repo.equipment()
        for background in self.repo.backgrounds().entries:
            idx = background["index"].lower()
            equipment = []
            for item in background.get("equipment", []) or []:
                name = item.get("equipment", {}).get("name") if isinstance(item, dict) else None
                if name:
                    equipment.append(name)
            backgrounds[idx] = BackgroundData(
                index=idx,
                name=background["name"],
                starting_proficiencies=_resolve(background.get("starting_proficiencies", []), self._proficiencies),
                starting_proficiencies_options=background.get("starting_proficiencies_options"),
                language_options=background.get("language_options"),
                equipment=equipment,
                feature=background.get("feature"),
                personality_traits=background.get("personality_traits"),
                ideals=background.get("ideals"),
                bonds=background.get("bonds"),
                flaws=background.get("flaws"),
            )
        return backgrounds

    # Convenience ------------------------------------------------------
    def spells_for_class(self, class_index: str) -> List[dict]:
        class_index = class_index.lower()
        result: List[dict] = []
        for spell in self._spells.entries:
            for ref in spell.get("classes", []):
                idx = (ref.get("index") or index_from_url(ref.get("url", ""))).lower()
                if idx == class_index:
                    result.append(spell)
                    break
        return result

    def spells_for_subclass(self, subclass_index: str) -> List[dict]:
        subclass_index = subclass_index.lower()
        result: List[dict] = []
        for spell in self._spells.entries:
            for ref in spell.get("subclasses", []):
                idx = (ref.get("index") or index_from_url(ref.get("url", ""))).lower()
                if idx == subclass_index:
                    result.append(spell)
                    break
        return result
