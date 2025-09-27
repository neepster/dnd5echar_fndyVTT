from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .constants import ABILITY_SCORES


@dataclass(slots=True)
class DerivedStats:
    proficiency_bonus: int = 2
    armor_class: int = 10
    initiative: int = 0
    speed: int = 30
    max_hit_points: int = 0
    hit_die: Optional[str] = None
    saving_throws: Dict[str, int] = field(default_factory=dict)
    skill_bonuses: Dict[str, int] = field(default_factory=dict)
    passive_perception: int = 10
    spell_slots: Dict[int, int] = field(default_factory=dict)
    spell_dc: Optional[int] = None
    spell_attack: Optional[int] = None


@dataclass(slots=True)
class CharacterState:
    """Mutable character draft that UI components bind to."""

    name: str = "New Adventurer"
    level: int = 1
    race: Optional[str] = None
    subrace: Optional[str] = None
    background: Optional[str] = None
    character_class: Optional[str] = None
    subclass: Optional[str] = None
    alignment: Optional[str] = None
    gender: Optional[str] = None

    base_ability_scores: Dict[str, int] = field(
        default_factory=lambda: {key: 10 for key in ABILITY_SCORES}
    )
    racial_ability_bonuses: Dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in ABILITY_SCORES}
    )
    subrace_ability_bonuses: Dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in ABILITY_SCORES}
    )
    manual_ability_bonuses: Dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in ABILITY_SCORES}
    )
    manual_hit_points: Optional[int] = None

    automatic_skill_proficiencies: Set[str] = field(default_factory=set)
    automatic_tool_proficiencies: Set[str] = field(default_factory=set)
    automatic_languages: Set[str] = field(default_factory=set)

    selected_skill_proficiencies: Set[str] = field(default_factory=set)
    selected_skill_expertise: Set[str] = field(default_factory=set)
    selected_tool_proficiencies: Set[str] = field(default_factory=set)
    selected_languages: Set[str] = field(default_factory=set)
    selected_feats: List[str] = field(default_factory=list)
    choice_selections: Dict[str, Set[str]] = field(default_factory=dict)
    selected_spells: Dict[str, Set[str]] = field(default_factory=dict)
    prepared_spells: Set[str] = field(default_factory=set)
    equipment: List[str] = field(default_factory=list)
    currency: Dict[str, int] = field(default_factory=lambda: {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0})
    notes: str = ""
    biography: str = ""

    derived: DerivedStats = field(default_factory=DerivedStats)
    randomization_locks: Set[str] = field(default_factory=set)

    # ------------------------------------------------------------------
    def total_bonus_for(self, ability: str) -> int:
        return (
            self.racial_ability_bonuses.get(ability, 0)
            + self.subrace_ability_bonuses.get(ability, 0)
            + self.manual_ability_bonuses.get(ability, 0)
        )

    def total_ability_score(self, ability: str) -> int:
        base = self.base_ability_scores.get(ability, 10)
        return base + self.total_bonus_for(ability)

    def ability_modifier(self, ability: str) -> int:
        return (self.total_ability_score(ability) - 10) // 2

    def set_base_ability_score(self, ability: str, value: int) -> None:
        if ability not in ABILITY_SCORES:
            raise ValueError(f"Unknown ability: {ability}")
        self.base_ability_scores[ability] = max(1, min(30, int(value)))

    def set_manual_bonus(self, ability: str, value: int) -> None:
        if ability not in ABILITY_SCORES:
            raise ValueError(f"Unknown ability: {ability}")
        self.manual_ability_bonuses[ability] = int(value)

    def reset(self) -> None:
        """Reset mutable selections but keep structural data."""

        self.level = 1
        self.race = None
        self.subrace = None
        self.background = None
        self.character_class = None
        self.subclass = None
        self.alignment = None
        self.gender = None
        self.base_ability_scores = {key: 10 for key in ABILITY_SCORES}
        self.racial_ability_bonuses = {key: 0 for key in ABILITY_SCORES}
        self.subrace_ability_bonuses = {key: 0 for key in ABILITY_SCORES}
        self.manual_ability_bonuses = {key: 0 for key in ABILITY_SCORES}
        self.manual_hit_points = None
        self.automatic_skill_proficiencies.clear()
        self.automatic_tool_proficiencies.clear()
        self.automatic_languages.clear()
        self.choice_selections.clear()
        self.selected_skill_proficiencies.clear()
        self.selected_skill_expertise.clear()
        self.selected_tool_proficiencies.clear()
        self.selected_languages.clear()
        self.selected_feats.clear()
        self.selected_spells.clear()
        self.prepared_spells.clear()
        self.equipment.clear()
        self.currency = {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0}
        self.notes = ""
        self.biography = ""
        self.derived = DerivedStats()
        self.randomization_locks.clear()
