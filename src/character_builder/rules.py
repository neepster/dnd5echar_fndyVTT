from __future__ import annotations

from typing import Dict, Iterable, Optional, Set

from .constants import ABILITY_SCORES, ABILITY_NAMES, SKILL_TO_ABILITY
from .models import CharacterState, DerivedStats
from .data.srd import ClassData, RaceData


def proficiency_bonus(level: int) -> int:
    level = max(1, min(level, 20))
    return 2 + (level - 1) // 4


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def average_hit_die(hit_die: int) -> int:
    return (hit_die // 2) + 1


def compute_hit_points(state: CharacterState, class_data: Optional[ClassData]) -> int:
    if state.manual_hit_points is not None:
        return max(state.manual_hit_points, state.level)
    if not class_data:
        return max(state.level, 1)
    con_mod = state.ability_modifier("con")
    hit_die = class_data.hit_die or 8
    total = hit_die + con_mod
    if state.level > 1:
        per_level = max(1, average_hit_die(hit_die) + con_mod)
        total += per_level * (state.level - 1)
    return max(total, state.level)


def compute_passive_perception(state: CharacterState, skill_bonus: Dict[str, int]) -> int:
    return 10 + skill_bonus.get("perception", state.ability_modifier("wis"))


def compute_speed(race: Optional[RaceData]) -> int:
    if race:
        return race.speed
    return 30


def compute_saving_throws(
    state: CharacterState,
    proficient_abilities: Iterable[str],
    prof_bonus: int,
) -> Dict[str, int]:
    bonuses: Dict[str, int] = {}
    for ability in ABILITY_SCORES:
        mod = state.ability_modifier(ability)
        if ability in proficient_abilities:
            mod += prof_bonus
        bonuses[ability] = mod
    return bonuses


def compute_skill_bonuses(
    state: CharacterState,
    proficient_skills: Set[str],
    expertise_skills: Set[str],
    prof_bonus: int,
) -> Dict[str, int]:
    bonuses: Dict[str, int] = {}
    for skill, ability in SKILL_TO_ABILITY.items():
        score_mod = state.ability_modifier(ability)
        total = score_mod
        if skill in expertise_skills:
            total += prof_bonus * 2
        elif skill in proficient_skills:
            total += prof_bonus
        bonuses[skill] = total
    return bonuses


def spellcasting_ability_index(class_data: Optional[ClassData]) -> Optional[str]:
    if not class_data or not class_data.spellcasting:
        return None
    ref = class_data.spellcasting.get("spellcasting_ability")
    if isinstance(ref, dict):
        idx = ref.get("index")
        if idx:
            return idx.lower()
    return None


def compute_spell_stats(state: CharacterState, class_data: Optional[ClassData], prof_bonus: int) -> Dict[str, Optional[int]]:
    ability_idx = spellcasting_ability_index(class_data)
    if not ability_idx:
        return {"dc": None, "attack": None, "ability": None}
    ability_mod = state.ability_modifier(ability_idx)
    return {
        "dc": 8 + prof_bonus + ability_mod,
        "attack": prof_bonus + ability_mod,
        "ability": ability_idx,
    }


def update_derived_stats(
    state: CharacterState,
    class_data: Optional[ClassData],
    race_data: Optional[RaceData],
    proficient_skills: Set[str],
    expertise_skills: Set[str],
    saving_throw_proficiencies: Iterable[str],
) -> None:
    prof = proficiency_bonus(state.level)
    state.derived.proficiency_bonus = prof
    state.derived.max_hit_points = compute_hit_points(state, class_data)
    hit_die = class_data.hit_die if class_data else 0
    state.derived.hit_die = f"d{hit_die}" if hit_die else None
    state.derived.initiative = state.ability_modifier("dex")
    state.derived.armor_class = 10 + state.ability_modifier("dex")
    state.derived.speed = compute_speed(race_data)
    saving = compute_saving_throws(state, saving_throw_proficiencies, prof)
    state.derived.saving_throws = saving
    skills = compute_skill_bonuses(state, proficient_skills, expertise_skills, prof)
    state.derived.skill_bonuses = skills
    state.derived.passive_perception = compute_passive_perception(state, skills)
    spell_stats = compute_spell_stats(state, class_data, prof)
    state.derived.spell_dc = spell_stats["dc"]
    state.derived.spell_attack = spell_stats["attack"]
    state.derived.spell_slots = _compute_spell_slots(class_data, state.level)

def _compute_spell_slots(class_data: Optional[ClassData], level: int) -> Dict[int, int]:
    if not class_data:
        return {}
    level_data = class_data.levels.get(level) if class_data.levels else None
    if not level_data or not level_data.spellcasting:
        return {}
    slots: Dict[int, int] = {}
    for key, value in level_data.spellcasting.items():
        if key.startswith("spell_slots_level_") and isinstance(value, int):
            try:
                slot_level = int(key.split("_")[-1])
            except ValueError:
                continue
            if value > 0:
                slots[slot_level] = value
    return {lvl: slots[lvl] for lvl in sorted(slots)}
