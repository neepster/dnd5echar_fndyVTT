from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

from ..constants import ABILITY_NAMES, ABILITY_SCORES, SKILL_NAMES
from .. import rules
from ..flavor import generate_biography

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..state import CharacterViewModel


CR_XP_TABLE: Dict[int, int] = {
    0: 10,
    1: 200,
    2: 450,
    3: 700,
    4: 1100,
    5: 1800,
    6: 2300,
    7: 2900,
    8: 3900,
    9: 5000,
    10: 5900,
    11: 7200,
    12: 8400,
    13: 10000,
    14: 11500,
    15: 13000,
    16: 15000,
    17: 18000,
    18: 20000,
    19: 22000,
    20: 25000,
    21: 33000,
    22: 41000,
    23: 50000,
    24: 62000,
    25: 75000,
    26: 90000,
    27: 105000,
    28: 120000,
    29: 135000,
    30: 155000,
}

SIZE_LABELS = {
    "tiny": "Tiny",
    "small": "Small",
    "medium": "Medium",
    "large": "Large",
    "huge": "Huge",
    "gargantuan": "Gargantuan",
}

ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def _ordinal(value: int) -> str:
    if value <= 0:
        return str(value)
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = ORDINAL_SUFFIXES.get(value % 10, "th")
    return f"{value}{suffix}"


def export_character_to_statblock(viewmodel: "CharacterViewModel", destination: Path) -> None:
    """Write a plain-text NPC statblock suitable for 5e Statblock Importer."""

    text = build_statblock_text(viewmodel)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text.rstrip() + "\n", encoding="utf-8")


def build_statblock_text(viewmodel: "CharacterViewModel") -> str:
    state = viewmodel.state
    race = viewmodel.srd.races.get(state.race) if state.race else None
    class_data = viewmodel.srd.classes.get(state.character_class) if state.character_class else None
    subclass = None
    if class_data and state.subclass and state.subclass in class_data.subclasses:
        subclass = class_data.subclasses[state.subclass]

    alignment_label = _alignment_label(viewmodel, state.alignment)
    size_label = SIZE_LABELS.get(race.size.lower(), "Medium") if race and race.size else "Medium"
    race_descriptor = race.name if race else "humanoid"
    subtitle_parts = [f"{size_label} humanoid ({race_descriptor.lower()})"]
    subtitle_parts.append(alignment_label or "unaligned")

    lines: List[str] = []
    lines.append(state.name)
    lines.append(", ".join(subtitle_parts))
    lines.append("")

    armor_detail = _armor_detail(viewmodel)
    lines.append(f"Armor Class {state.derived.armor_class}{armor_detail}")

    hp_detail = f" ({state.derived.hit_die})" if state.derived.hit_die else ""
    lines.append(f"Hit Points {max(state.derived.max_hit_points, 1)}{hp_detail}")

    lines.append(f"Speed {state.derived.speed} ft.")
    lines.append("")

    lines.extend(_ability_block(state))
    lines.append("")

    saving_line = _saving_throws_line(viewmodel)
    if saving_line:
        lines.append(f"Saving Throws {saving_line}")
    skills_line = _skills_line(viewmodel)
    if skills_line:
        lines.append(f"Skills {skills_line}")

    lines.append(f"Senses passive Perception {state.derived.passive_perception}")

    languages_line = _languages_line(viewmodel)
    if languages_line:
        lines.append(f"Languages {languages_line}")

    class_line = _class_line(state, class_data, subclass)
    if class_line:
        lines.append(class_line)

    challenge_line = _challenge_line(state.level)
    if challenge_line:
        lines.append(challenge_line)

    lines.append(f"Proficiency Bonus +{state.derived.proficiency_bonus}")
    lines.append("")

    traits = _collect_traits(viewmodel, class_data, subclass)
    spellcasting_trait = _spellcasting_trait(viewmodel, class_data)
    if spellcasting_trait:
        traits.insert(0, ("Spellcasting", spellcasting_trait))

    if traits:
        lines.append("Traits")
        for name, desc in traits:
            lines.append(f"{name}. {desc}")
        lines.append("")

    actions = _actions_list(viewmodel)
    lines.append("Actions")
    if actions:
        lines.extend(actions)
    else:
        lines.append(_fallback_unarmed_action(viewmodel))

    biography = (state.biography or "").strip()
    if not biography:
        biography = generate_biography(state, viewmodel.srd)
        state.biography = biography
    if biography:
        lines.append("")
        lines.append("Description")
        lines.append(biography)

    return "\n".join(lines)


def _ability_block(state) -> List[str]:
    header = " ".join(score.upper() for score in ABILITY_SCORES)
    values = []
    for ability in ABILITY_SCORES:
        score = state.total_ability_score(ability)
        mod = state.ability_modifier(ability)
        values.append(f"{score} ({mod:+d})")
    return [header, "  ".join(values)]


def _saving_throws_line(viewmodel: "CharacterViewModel") -> str:
    profs = viewmodel.saving_throw_proficiencies()
    if not profs:
        return ""
    state = viewmodel.state
    entries = []
    for ability in ABILITY_SCORES:
        if ability in profs:
            bonus = state.derived.saving_throws.get(ability, state.ability_modifier(ability))
            entries.append(f"{ability.upper()} {bonus:+d}")
    return ", ".join(entries)


def _skills_line(viewmodel: "CharacterViewModel") -> str:
    proficient = viewmodel.selected_skills()
    if not proficient:
        return ""
    state = viewmodel.state
    entries = []
    for skill in sorted(proficient):
        bonus = state.derived.skill_bonuses.get(skill)
        if bonus is None:
            continue
        name = SKILL_NAMES.get(skill, skill.replace("-", " ").title())
        entries.append(f"{name} {bonus:+d}")
    return ", ".join(entries)


def _languages_line(viewmodel: "CharacterViewModel") -> str:
    languages = sorted(viewmodel.selected_languages())
    if not languages:
        return ""
    repo = viewmodel.srd.repo.load("languages")
    labels = []
    for lang in languages:
        if not lang:
            continue
        key = str(lang).lower()
        entry = repo.by_index.get(key)
        if entry:
            labels.append(entry.get("name", lang.title()))
        else:
            labels.append(lang.replace("-", " ").title())
    return ", ".join(labels)


def _challenge_line(level: int) -> str:
    if level <= 0:
        return ""
    challenge = min(level, 30)
    xp = CR_XP_TABLE.get(challenge, 0)
    xp_text = f"{xp:,}" if xp else "—"
    return f"Challenge {challenge} ({xp_text} XP)"


def _class_line(state, class_data, subclass) -> str:
    if not class_data:
        return ""

    level = max(int(state.level or 0), 0)
    parts: List[str] = []
    if level > 0:
        parts.append(f"{_ordinal(level)}-level")
    if subclass:
        parts.append(subclass.name)
    parts.append(class_data.name)

    return "Class " + " ".join(parts)


def _collect_traits(viewmodel: "CharacterViewModel", class_data, subclass) -> List[Tuple[str, str]]:
    state = viewmodel.state
    traits: List[Tuple[str, str]] = []
    race = viewmodel.srd.races.get(state.race) if state.race else None
    if race:
        for trait in race.traits:
            traits.append((trait.get("name", "Trait"), _collapse_text(trait.get("desc", []), state.name)))
        if state.subrace and state.subrace in race.subraces:
            subrace = race.subraces[state.subrace]
            for trait in subrace.traits:
                traits.append((trait.get("name", "Trait"), _collapse_text(trait.get("desc", []), state.name)))

    if class_data:
        for lvl in sorted(class_data.levels.keys()):
            if lvl > state.level:
                continue
            for feature in class_data.levels[lvl].features:
                traits.append((feature.get("name", "Class Feature"), _collapse_text(feature.get("desc", []), state.name)))
        if subclass:
            for lvl, feats in subclass.features_by_level.items():
                if lvl > state.level:
                    continue
                for feat in feats:
                    traits.append((feat.get("name", "Subclass Feature"), _collapse_text(feat.get("desc", []), state.name)))

    background = viewmodel.srd.backgrounds.get(state.background) if state.background else None
    if background and background.feature:
        feature = background.feature
        traits.append((feature.get("name", "Background Feature"), _collapse_text(feature.get("desc", []), state.name)))

    return traits


def _spellcasting_trait(viewmodel: "CharacterViewModel", class_data) -> str:
    state = viewmodel.state
    known = state.selected_spells.get("prepared") or state.selected_spells.get("known")
    if not known:
        return ""

    ability_idx = rules.spellcasting_ability_index(class_data) if class_data else None
    if ability_idx is None:
        return ""

    ability_name = ABILITY_NAMES.get(ability_idx, ability_idx.upper())
    dc = state.derived.spell_dc or (8 + state.derived.proficiency_bonus + state.ability_modifier(ability_idx))
    attack = state.derived.spell_attack or (state.derived.proficiency_bonus + state.ability_modifier(ability_idx))

    spells_by_level: Dict[int, List[str]] = {}
    for spell_idx in known:
        key = (spell_idx or "").lower()
        entry = viewmodel.srd.spells.get(key)
        if not entry:
            continue
        level = entry.get("level", 0)
        spells_by_level.setdefault(level, []).append(entry.get("name", spell_idx.title()))

    if not spells_by_level:
        return ""

    lines = [
        f"{state.name} is a {state.level}th-level spellcaster."
        f" Their spellcasting ability is {ability_name} (spell save DC {dc}, +{attack} to hit with spell attacks).",
    ]

    slot_map = state.derived.spell_slots or {}
    for level in sorted(spells_by_level.keys()):
        names = sorted(spells_by_level[level])
        if not names:
            continue
        if level == 0:
            prefix = "Cantrips (at will)"
        else:
            ordinal = _ordinal(level)
            slots = slot_map.get(level)
            slot_text = f" ({slots} slots)" if slots else ""
            prefix = f"{ordinal} level{slot_text}"
        lines.append(f"{prefix}: {', '.join(names)}")

    return " ".join(lines)


def _actions_list(viewmodel: "CharacterViewModel") -> List[str]:
    state = viewmodel.state
    equipment = state.equipment or []
    if not equipment:
        return []
    catalog = viewmodel.srd.equipment
    actions: List[str] = []
    seen: set[str] = set()
    for idx in equipment:
        base_idx, magic_bonus = _split_magic_index(idx)
        if base_idx in seen:
            continue
        entry = catalog.get(base_idx)
        if not entry:
            continue
        if (entry.get("equipment_category", {}).get("index") or "").lower() != "weapon":
            continue
        action = _weapon_action_entry(viewmodel, entry, magic_bonus)
        if action:
            actions.append(action)
            seen.add(base_idx)
    return actions


def _weapon_action_entry(viewmodel: "CharacterViewModel", entry: dict, magic_bonus: int) -> str:
    state = viewmodel.state
    name = entry.get("name", "Weapon")
    if magic_bonus > 0 and not name.endswith(f"+{magic_bonus}"):
        name = f"{name} +{magic_bonus}"
    weapon_range = (entry.get("weapon_range") or "").lower()
    properties = [prop.get("index", "") for prop in entry.get("properties", [])]

    ability = "dex" if weapon_range == "ranged" or "finesse" in properties else "str"
    str_mod = state.ability_modifier("str")
    dex_mod = state.ability_modifier("dex")
    if ability == "str" and "finesse" in properties and dex_mod > str_mod:
        ability = "dex"
    ability_mod = state.ability_modifier(ability)

    attack_bonus = ability_mod + state.derived.proficiency_bonus + magic_bonus

    damage = entry.get("damage", {})
    damage_dice = damage.get("damage_dice")
    damage_type = damage.get("damage_type", {}).get("name", "")
    if not damage_dice:
        return ""

    damage_bonus = ability_mod + magic_bonus
    damage_notation = _format_damage_notation(damage_dice, damage_bonus)
    avg_damage = _average_damage(damage_dice, damage_bonus)
    damage_type_name = damage_type.lower() if damage_type else "damage"

    if weapon_range == "ranged":
        range_block = entry.get("range", {})
        normal = range_block.get("normal") or 20
        long = range_block.get("long") or 60
        attack_prefix = "Ranged Weapon Attack"
        range_text = f"range {normal}/{long} ft."
    else:
        reach = 10 if "reach" in properties else 5
        attack_prefix = "Melee Weapon Attack"
        range_text = f"reach {reach} ft."

    return (
        f"{name}. {attack_prefix}: {attack_bonus:+d} to hit, {range_text}, one target. "
        f"Hit: {max(avg_damage, 0)} ({damage_notation}) {damage_type_name} damage."
    )


def _fallback_unarmed_action(viewmodel: "CharacterViewModel") -> str:
    state = viewmodel.state
    ability_mod = state.ability_modifier("str")
    attack_bonus = ability_mod + state.derived.proficiency_bonus
    damage_bonus = max(1, 1 + ability_mod)
    return (
        f"Unarmed Strike. Melee Weapon Attack: {attack_bonus:+d} to hit, reach 5 ft., one target. "
        f"Hit: {damage_bonus} bludgeoning damage."
    )


def _average_damage(damage_dice: str, bonus: int) -> int:
    count, faces = _parse_damage_dice(damage_dice)
    if count == 0 or faces == 0:
        return max(bonus, 0)
    average = count * (faces + 1) / 2
    return max(int(math.floor(average + bonus)), 0)


def _format_damage_notation(damage_dice: str, bonus: int) -> str:
    if bonus > 0:
        return f"{damage_dice} + {bonus}"
    if bonus < 0:
        return f"{damage_dice} - {abs(bonus)}"
    return damage_dice


def _parse_damage_dice(damage_dice: str) -> Tuple[int, int]:
    match = re.match(r"^(\d+)d(\d+)", damage_dice)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _split_magic_index(index: str) -> Tuple[str, int]:
    if "+" in index:
        base, bonus = index.split("+", 1)
        try:
            return base, int(bonus)
        except ValueError:
            return base, 0
    return index, 0


def _armor_detail(viewmodel: "CharacterViewModel") -> str:
    state = viewmodel.state
    catalog = viewmodel.srd.equipment
    for idx in state.equipment or []:
        base_idx, _ = _split_magic_index(idx)
        entry = catalog.get(base_idx)
        if not entry:
            continue
        if (entry.get("equipment_category", {}).get("index") or "").lower() == "armor":
            return f" ({entry.get('name')})"
    return ""


def _collapse_text(lines: Iterable[str], subject: Optional[str] = None) -> str:
    if isinstance(lines, str):
        return _to_third_person(lines.strip(), subject)
    parts = []
    for line in lines or []:
        if isinstance(line, str):
            cleaned = line.strip()
            if cleaned:
                parts.append(_to_third_person(cleaned, subject))
    return " ".join(parts)


def _to_third_person(text: str, subject: Optional[str]) -> str:
    if not text:
        return text
    subject = subject or "the creature"
    subject_lower = subject.lower()
    possessive = f"{subject}'s"
    possessive_lower = f"{subject_lower}'s"

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()
        if lower == "you":
            return subject if word[0].isupper() else subject_lower
        if lower == "your":
            return possessive if word[0].isupper() else possessive_lower
        return word

    return re.sub(r"\b(You|you|Your|your)\b", replace, text)


def _alignment_label(viewmodel: "CharacterViewModel", alignment_index: Optional[str]) -> str:
    if not alignment_index:
        return ""
    for entry in viewmodel.srd.alignments:
        if entry.get("index") == alignment_index:
            return entry.get("name", alignment_index).lower()
    return alignment_index.lower()
