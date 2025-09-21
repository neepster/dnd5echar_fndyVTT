from __future__ import annotations

import json
import re
import secrets
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..constants import ABILITY_NAMES, ABILITY_SCORES, SKILL_NAMES, SKILL_TO_ABILITY
from ..data.srd import ClassData, RaceData, SubclassData, SubraceData
from ..models import CharacterState
from ..state import CharacterViewModel
from .. import rules

FOUNDRY_SKILL_MAP = {
    "acrobatics": "acr",
    "animal-handling": "ani",
    "arcana": "arc",
    "athletics": "ath",
    "deception": "dec",
    "history": "his",
    "insight": "ins",
    "intimidation": "itm",
    "investigation": "inv",
    "medicine": "med",
    "nature": "nat",
    "perception": "prc",
    "performance": "prf",
    "persuasion": "per",
    "religion": "rel",
    "sleight-of-hand": "slt",
    "stealth": "ste",
    "survival": "sur",
}


def export_character_to_foundry(viewmodel: CharacterViewModel, destination: Path) -> None:
    """Serialize the current character into Foundry VTT's dnd5e actor JSON format."""

    state = viewmodel.state
    class_data = viewmodel.srd.classes.get(state.character_class) if state.character_class else None
    race_data = viewmodel.srd.races.get(state.race) if state.race else None
    subclass_data: Optional[SubclassData] = None
    if class_data and state.subclass:
        subclass_data = class_data.subclasses.get(state.subclass)
    background = viewmodel.srd.backgrounds.get(state.background) if state.background else None

    actor = {
        "name": state.name,
        "type": "character",
        "img": "icons/svg/mystery-man.svg",
        "system": _build_system(viewmodel, class_data, race_data, subclass_data, background),
        "items": _build_items(viewmodel, class_data, race_data, subclass_data, background),
        "effects": [],
        "flags": {
            "dnd5e": {
                "exportSource": {
                    "world": "",
                    "system": "dnd5e",
                    "type": "character",
                }
            }
        },
        "folder": None,
        "ownership": {"default": 0},
        "prototypeToken": _build_prototype_token(state),
        "_stats": {
            "systemId": "dnd5e",
            "systemVersion": "5.1.9",
            "coreVersion": "11",
            "createdTime": _timestamp_ms(),
            "modifiedTime": _timestamp_ms(),
            "lastModifiedBy": None,
        },
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(actor, handle, indent=2, ensure_ascii=False)


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_system(
    viewmodel: CharacterViewModel,
    class_data: Optional[ClassData],
    race_data: Optional[RaceData],
    subclass_data: Optional[SubclassData],
    background,
) -> Dict[str, object]:
    state = viewmodel.state

    abilities = _build_abilities(viewmodel)
    skills = _build_skills(viewmodel)
    spells = _build_spells(viewmodel)
    attributes = _build_attributes(viewmodel, class_data, race_data)
    details = _build_details(viewmodel, class_data, race_data, background)
    traits = _build_traits(viewmodel, race_data)
    currency = state.currency or {}
    system_currency = {
        "pp": _ensure_positive_int(currency.get("pp", 0)),
        "gp": _ensure_positive_int(currency.get("gp", 0)),
        "ep": _ensure_positive_int(currency.get("ep", 0)),
        "sp": _ensure_positive_int(currency.get("sp", 0)),
        "cp": _ensure_positive_int(currency.get("cp", 0)),
    }

    system: Dict[str, object] = {
        "currency": system_currency,
        "abilities": abilities,
        "bonuses": {
            "mwak": {"attack": "", "damage": ""},
            "rwak": {"attack": "", "damage": ""},
            "msak": {"attack": "", "damage": ""},
            "rsak": {"attack": "", "damage": ""},
            "abilities": {"check": "", "save": "", "skill": ""},
            "spell": {"dc": ""},
        },
        "skills": skills,
        "tools": _build_tools_dict(viewmodel),
        "spells": spells,
        "attributes": attributes,
        "bastion": {},
        "details": details,
        "traits": traits,
        "resources": {
            "primary": {"value": 0, "max": 0, "sr": False, "lr": False, "label": ""},
            "secondary": {"value": 0, "max": 0, "sr": False, "lr": False, "label": ""},
            "tertiary": {"value": 0, "max": 0, "sr": False, "lr": False, "label": ""},
        },
        "favorites": [],
    }
    return system


def _build_abilities(viewmodel: CharacterViewModel) -> Dict[str, object]:
    state = viewmodel.state
    saving_throws = viewmodel.saving_throw_proficiencies()
    abilities: Dict[str, object] = {}
    for ability in ABILITY_SCORES:
        score = state.total_ability_score(ability)
        abilities[ability] = {
            "value": score,
            "proficient": 1 if ability in saving_throws else 0,
            "max": 20,
            "bonuses": {"check": "", "save": ""},
            "check": {"roll": {"min": None, "max": None, "mode": 0}},
            "save": {"roll": {"min": None, "max": None, "mode": 0}},
        }
    return abilities


def _build_skills(viewmodel: CharacterViewModel) -> Dict[str, object]:
    state = viewmodel.state
    all_skills = viewmodel.selected_skills()
    expertise = state.selected_skill_expertise
    skills: Dict[str, object] = {}
    for skill_idx, foundry_key in FOUNDRY_SKILL_MAP.items():
        ability = SKILL_TO_ABILITY[skill_idx]
        prof_level = 2 if skill_idx in expertise else (1 if skill_idx in all_skills else 0)
        skills[foundry_key] = {
            "ability": ability,
            "value": prof_level,
            "bonuses": {"check": "", "passive": ""},
            "roll": {"min": None, "max": None, "mode": 0},
        }
    return skills


def _build_spells(viewmodel: CharacterViewModel) -> Dict[str, object]:
    state = viewmodel.state
    spells: Dict[str, object] = {}

    known_cantrips = 0
    for spell_index in state.selected_spells.get("known", set()):
        spell = viewmodel.srd.spells.get(spell_index)
        if spell and spell.get("level", 0) == 0:
            known_cantrips += 1
    spells["spell0"] = {"value": known_cantrips, "max": known_cantrips, "override": 0, "used": 0}

    for level in range(1, 10):
        max_slots = state.derived.spell_slots.get(level, 0)
        spells[f"spell{level}"] = {"value": max_slots, "max": max_slots, "override": 0, "used": 0}

    spells["pact"] = {"value": 0, "max": 0, "override": 0, "used": 0}
    return spells


def _build_attributes(
    viewmodel: CharacterViewModel,
    class_data: Optional[ClassData],
    race_data: Optional[RaceData],
) -> Dict[str, object]:
    state = viewmodel.state
    spell_ability = rules.spellcasting_ability_index(class_data) if class_data else None

    attributes: Dict[str, object] = {
        "ac": {"calc": "flat", "flat": state.derived.armor_class, "formula": ""},
        "init": {"ability": "dex", "bonus": "", "roll": {"min": None, "max": None, "mode": 0}},
        "movement": {
            "burrow": 0,
            "climb": 0,
            "fly": 0,
            "swim": 0,
            "walk": state.derived.speed,
            "units": "ft",
            "hover": False,
            "ignoredDifficultTerrain": [],
        },
        "attunement": {"max": 3},
        "senses": {"blindsight": 0, "darkvision": 0, "tremorsense": 0, "truesight": 0, "units": "ft", "special": ""},
        "spellcasting": spell_ability or "",
        "exhaustion": 0,
        "concentration": {"ability": "", "bonuses": {"save": ""}, "limit": 1, "roll": {"min": None, "max": None, "mode": 1}},
        "loyalty": {},
        "hp": {
            "value": max(state.derived.max_hit_points, 1),
            "max": max(state.derived.max_hit_points, 1),
            "temp": 0,
            "tempmax": 0,
            "bonuses": {"level": "", "overall": ""},
        },
        "death": {"success": 0, "failure": 0, "bonuses": {"save": ""}, "roll": {"min": None, "max": None, "mode": 0}},
        "inspiration": False,
    }

    if race_data and any(trait.get("name", "").lower() == "darkvision" for trait in race_data.traits):
        attributes["senses"]["darkvision"] = 60

    return attributes


def _build_details(
    viewmodel: CharacterViewModel,
    class_data: Optional[ClassData],
    race_data: Optional[RaceData],
    background,
) -> Dict[str, object]:
    state = viewmodel.state
    alignment_label = _alignment_label(viewmodel, state.alignment)
    race_name = race_data.name if race_data else ""
    class_name = class_data.name if class_data else ""
    background_name = background.name if background else ""

    biography_value = _format_html(state.notes) if state.notes else ""

    return {
        "biography": {"value": biography_value, "public": biography_value},
        "alignment": alignment_label,
        "ideal": "",
        "bond": "",
        "flaw": "",
        "race": race_name,
        "background": background_name,
        "originalClass": class_name,
        "xp": {"value": 0},
        "appearance": "",
        "trait": "",
        "gender": "",
        "eyes": "",
        "height": "",
        "faith": "",
        "hair": "",
        "skin": "",
        "age": "",
        "weight": "",
    }


def _alignment_label(viewmodel: CharacterViewModel, alignment_index: Optional[str]) -> str:
    if not alignment_index:
        return ""
    for entry in viewmodel.srd.alignments:
        if entry.get("index") == alignment_index:
            return entry.get("name", alignment_index).title()
    return alignment_index.title()


def _build_traits(viewmodel: CharacterViewModel, race_data: Optional[RaceData]) -> Dict[str, object]:
    state = viewmodel.state
    weapon_profs, armor_profs, tool_profs = _categorize_proficiencies(viewmodel)
    languages = sorted(viewmodel.selected_languages())

    return {
        "size": _foundry_size(race_data.size) if race_data and race_data.size else "med",
        "di": {"value": [], "custom": ""},
        "dr": {"value": [], "custom": ""},
        "dv": {"value": [], "custom": ""},
        "dm": {"value": [], "custom": ""},
        "ci": {"value": [], "custom": ""},
        "languages": {"value": languages, "custom": "", "communication": {}},
        "weaponProf": {"value": sorted(weapon_profs), "custom": "", "mastery": {"value": [], "bonus": []}},
        "armorProf": {"value": sorted(armor_profs), "custom": ""},
        "toolProf": {"value": sorted(tool_profs), "custom": ""},
    }


def _categorize_proficiencies(viewmodel: CharacterViewModel) -> Tuple[Set[str], Set[str], Set[str]]:
    state = viewmodel.state
    prof_indices = set(state.automatic_tool_proficiencies) | set(state.selected_tool_proficiencies)
    weapon: Set[str] = set()
    armor: Set[str] = set()
    tools: Set[str] = set()
    for index in prof_indices:
        entry = viewmodel.srd.proficiencies.get(index)
        if not entry:
            continue
        prof_type = (entry.get("type") or "").lower()
        if prof_type == "weapons":
            weapon.add(entry.get("index", index))
        elif prof_type == "armor":
            armor.add(entry.get("index", index))
        elif prof_type in {"artisan's tools", "musical instruments", "gaming sets", "vehicles", "other"}:
            tools.add(entry.get("index", index))
    return weapon, armor, tools


def _build_tools_dict(viewmodel: CharacterViewModel) -> Dict[str, object]:
    _, _, tool_profs = _categorize_proficiencies(viewmodel)
    tools: Dict[str, object] = {}
    for index in sorted(tool_profs):
        key = _sanitize_key(index)
        tools[key] = {
            "value": 1,
            "ability": "int",
            "bonuses": {"check": ""},
            "roll": {"min": None, "max": None, "mode": 0},
        }
    return tools


def _sanitize_key(value: str) -> str:
    return value.replace("tool-", "").replace(" ", "-").replace("'", "").lower()


def _build_items(
    viewmodel: CharacterViewModel,
    class_data: Optional[ClassData],
    race_data: Optional[RaceData],
    subclass_data: Optional[SubclassData],
    background,
) -> List[Dict[str, object]]:
    state = viewmodel.state
    items: List[Dict[str, object]] = []

    if class_data:
        items.append(_class_item(state, class_data, subclass_data))

    if subclass_data:
        items.append(_subclass_item(subclass_data, class_data))

    if race_data:
        items.append(_race_item(race_data))
        if state.subrace and state.subrace in race_data.subraces:
            items.append(_subrace_item(race_data.subraces[state.subrace], race_data))
        for trait in race_data.traits:
            items.append(_trait_item(trait, source=race_data.name, trait_type="race"))
        if state.subrace and state.subrace in race_data.subraces:
            subrace = race_data.subraces[state.subrace]
            for trait in subrace.traits:
                items.append(_trait_item(trait, source=subrace.name, trait_type="race"))

    if background:
        items.append(_background_item(background))
        if background.feature:
            items.append(
                _trait_item(
                    {"name": background.feature.get("name"), "desc": background.feature.get("desc", [])},
                    source=background.name,
                    trait_type="background",
                )
            )

    # Class and subclass features
    if class_data:
        for level in sorted(class_data.levels.keys()):
            if level > state.level:
                continue
            for feature in class_data.levels[level].features:
                items.append(_trait_item(feature, source=f"{class_data.name} {level}", trait_type="class"))
        if subclass_data:
            for level, features in sorted(subclass_data.features_by_level.items()):
                if level > state.level:
                    continue
                for feature in features:
                    items.append(_trait_item(feature, source=subclass_data.name, trait_type="class"))

    # Spells
    known_spells = state.selected_spells.get("known", set())
    prepared_spells = state.selected_spells.get("prepared", set())
    for spell_index in sorted(known_spells):
        spell = viewmodel.srd.spells.get(spell_index)
        if not spell:
            continue
        items.append(_spell_item(spell, spell_index in prepared_spells))

    # Simple equipment as loot entries
    items.extend(_equipment_items(viewmodel, state.equipment))

    return items


def _base_item(name: str, item_type: str, system: Dict[str, object], img: str = "icons/svg/book.svg") -> Dict[str, object]:
    return {
        "_id": _random_id(),
        "name": name,
        "type": item_type,
        "img": img,
        "system": system,
        "effects": [],
        "flags": {},
    }


def _class_item(state: CharacterState, class_data: ClassData, subclass_data: Optional[SubclassData]) -> Dict[str, object]:
    hit_die = f"d{class_data.hit_die}" if class_data.hit_die else ""
    spellcasting_ability = rules.spellcasting_ability_index(class_data)
    progression = _spell_progression(class_data)
    system = {
        "description": {"value": ""},
        "identifier": class_data.index,
        "levels": state.level,
        "hd": {"denomination": hit_die, "additional": "", "spent": 0},
        "source": {"book": "SRD 5.1", "page": "", "custom": ""},
        "spellcasting": {
            "ability": spellcasting_ability or "",
            "progression": progression,
            "preparation": {"formula": ""},
        },
    }
    if subclass_data:
        system["subclass"] = subclass_data.index
    return _base_item(class_data.name, "class", system)


def _subclass_item(subclass_data: SubclassData, class_data: Optional[ClassData]) -> Dict[str, object]:
    system = {
        "description": {"value": _format_html(subclass_data.description)},
        "identifier": subclass_data.index,
        "classIdentifier": class_data.index if class_data else "",
        "source": {"book": "SRD 5.1", "page": "", "custom": ""},
    }
    return _base_item(subclass_data.name, "subclass", system)


def _race_item(race: RaceData) -> Dict[str, object]:
    system = {
        "description": {"value": _format_html(_collect_text(race.traits))},
        "source": {"book": "SRD 5.1", "page": "", "custom": ""},
    }
    return _base_item(race.name, "race", system)


def _subrace_item(subrace: SubraceData, race: RaceData) -> Dict[str, object]:
    system = {
        "description": {"value": _format_html(subrace.description)},
        "source": {"book": "SRD 5.1", "page": "", "custom": race.name},
    }
    return _base_item(subrace.name, "race", system)


def _background_item(background) -> Dict[str, object]:
    description = background.feature.get("desc", []) if background and background.feature else []
    system = {
        "description": {"value": _format_html(description)},
        "source": {"book": "SRD 5.1", "page": "", "custom": ""},
    }
    return _base_item(background.name, "feat", system)


def _trait_item(trait: dict, source: str, trait_type: str) -> Dict[str, object]:
    system = {
        "description": {"value": _format_html(trait.get("desc", []))},
        "type": {"value": trait_type},
        "source": {"book": source, "page": "", "custom": ""},
    }
    return _base_item(trait.get("name", "Feature"), "feat", system)


def _spell_item(spell: dict, prepared: bool) -> Dict[str, object]:
    components = {component.lower(): True for component in spell.get("components", [])}
    properties = _spell_properties(spell, components)
    materials = {
        "value": spell.get("material", ""),
        "consumed": False,
        "cost": 0,
        "supply": 0,
    }
    source_classes = [ref.get("index") for ref in spell.get("classes", []) if ref.get("index")]
    components = {
        "v": components.get("v", False),
        "s": components.get("s", False),
        "m": components.get("m", False),
        "ritual": spell.get("ritual", False),
        "concentration": spell.get("concentration", False),
        "material": spell.get("material", ""),
    }

    system = {
        "description": {"value": _format_html(spell.get("desc", []))},
        "level": spell.get("level", 0),
        "school": spell.get("school", {}).get("index", ""),
        "activation": _parse_activation(spell.get("casting_time", "")),
        "range": _parse_range(spell.get("range", "")),
        "duration": _parse_duration(spell.get("duration", "")),
        "source": {"book": "SRD 5.1", "page": "", "custom": ""},
        "target": _default_target(),
        "identifier": spell.get("index", ""),
        "activities": {},
        "components": components,
        "materials": materials,
        "properties": properties,
        "method": "spell",
        "prepared": bool(prepared),
        "uses": {"spent": 0, "max": "", "recovery": []},
        "sourceClass": source_classes,
    }
    system["preparation"] = {"mode": "prepared" if prepared else "known", "prepared": bool(prepared)}
    activity = _build_spell_activity(spell, system)
    system["activities"][activity["_id"]] = activity
    return _base_item(spell.get("name", "Spell"), "spell", system, img="icons/magic/arcane/bolt-spiral-blue.webp")


def _collect_text(entries: Iterable[dict]) -> List[str]:
    output: List[str] = []
    for entry in entries or []:
        output.extend(entry.get("desc", []))
    return output


def _default_target() -> Dict[str, object]:
    return {
        "affects": {"count": "", "type": "", "choice": False, "special": ""},
        "template": {"count": "", "contiguous": False, "type": "", "size": "", "width": "", "height": "", "units": "ft"},
    }


def _parse_activation(text: str) -> Dict[str, object]:
    if not text:
        return {"type": "action", "value": 1, "condition": "", "override": False}
    raw = text.strip()
    condition = ""
    if "," in raw:
        main, condition = raw.split(",", 1)
        condition = condition.strip()
    else:
        main = raw
    main_lower = main.lower()
    match = re.match(r"(\d+)\s*(.*)", main_lower)
    if match:
        cost = int(match.group(1))
        unit = match.group(2).strip()
    else:
        cost = 1
        unit = main_lower

    mapping = {
        "action": "action",
        "bonus action": "bonus",
        "reaction": "reaction",
        "bonus": "bonus",
        "minute": "minute",
        "minutes": "minute",
        "hour": "hour",
        "hours": "hour",
        "round": "round",
        "rounds": "round",
        "turn": "turn",
        "turns": "turn",
        "day": "day",
        "days": "day",
    }
    mapped = "special"
    for key, value in mapping.items():
        if unit.startswith(key):
            mapped = value
            break
    return {"type": mapped, "value": cost, "condition": condition, "override": False}


def _parse_range(text: str) -> Dict[str, object]:
    if not text:
        return {"units": "self", "value": "", "override": False}
    cleaned = text.strip()
    lower = cleaned.lower()
    if lower.startswith("self"):
        return {"units": "self", "value": "", "override": False}
    if lower.startswith("touch"):
        return {"units": "touch", "value": "", "override": False}
    if "unlimited" in lower:
        return {"units": "any", "value": "", "override": False}
    if "sight" in lower:
        return {"units": "spec", "value": "sight", "override": False}
    value = _extract_number(lower)
    if "mile" in lower:
        return {"units": "mi", "value": value or "1", "override": False}
    if "foot" in lower or "feet" in lower:
        return {"units": "ft", "value": value or "0", "override": False}
    if "yard" in lower:
        number = value or "0"
        try:
            converted = str(int(number) * 3)
        except ValueError:
            converted = number
        return {"units": "ft", "value": converted, "override": False}
    if lower == "special":
        return {"units": "spec", "value": "", "override": False}
    return {"units": "spec", "value": cleaned, "override": False}


def _parse_duration(text: str) -> Dict[str, object]:
    if not text:
        return {"value": "0", "units": "inst", "override": False}
    cleaned = text.strip()
    lower = cleaned.lower()
    if "instant" in lower:
        return {"value": "0", "units": "inst", "override": False}
    if "permanent" in lower:
        return {"value": "", "units": "perm", "override": False}
    if "until dispelled" in lower or "special" in lower:
        return {"value": "", "units": "spec", "override": False}
    number = _extract_number(lower) or "1"
    if "hour" in lower:
        return {"value": number, "units": "hour", "override": False}
    if "minute" in lower:
        return {"value": number, "units": "minute", "override": False}
    if "round" in lower:
        return {"value": number, "units": "round", "override": False}
    if "turn" in lower:
        return {"value": number, "units": "turn", "override": False}
    if "day" in lower:
        return {"value": number, "units": "day", "override": False}
    return {"value": cleaned, "units": "spec", "override": False}


def _extract_number(text: str) -> Optional[str]:
    match = re.search(r"(\d+)", text)
    return match.group(1) if match else None


def _equipment_items(viewmodel: CharacterViewModel, equipment_list: List[str]) -> List[Dict[str, object]]:
    if not equipment_list:
        return []

    counter = Counter(equipment_list)
    equipment_catalog = viewmodel.srd.equipment
    output: List[Dict[str, object]] = []

    for index, quantity in counter.items():
        base_index, magic_bonus = _split_magic_index(index)
        entry = equipment_catalog.get(base_index)
        if not entry:
            display_name = base_index.replace("-", " ").title()
            if magic_bonus:
                display_name = f"{display_name} +{magic_bonus}"
            output.append(_loot_entry(display_name, base_index, quantity))
            continue

        category = (entry.get("equipment_category", {}).get("index") or "").lower()
        if category == "weapon":
            item = _weapon_entry(entry, quantity, magic_bonus)
        elif category == "armor":
            item = _armor_entry(entry, quantity, magic_bonus)
        else:
            name = entry.get("name")
            if magic_bonus:
                name = f"{name} +{magic_bonus}"
            item = _loot_entry(name, entry.get("index"), quantity, entry)
        output.append(item)

    return output


def _weapon_entry(entry: dict, quantity: int, magic_bonus: int = 0) -> Dict[str, object]:
    damage = entry.get("damage", {})
    damage_dice = damage.get("damage_dice", "")
    damage_type = damage.get("damage_type", {}).get("index", "")
    versatile = entry.get("two_handed_damage", {}).get("damage_dice", "")
    weapon_type = _weapon_type(entry)
    ability = _weapon_ability(entry)
    weapon_range = entry.get("range", {})
    properties = [prop.get("index", "") for prop in entry.get("properties", [])]

    system = {
        "description": {"value": ""},
        "identifier": entry.get("index", ""),
        "quantity": quantity,
        "weight": {"value": entry.get("weight", 0) or 0, "units": "lb"},
        "price": {
            "value": entry.get("cost", {}).get("quantity", 0),
            "denomination": entry.get("cost", {}).get("unit", "gp"),
        },
        "equipped": False,
        "attunement": "none",
        "attuned": False,
        "container": None,
        "activation": {"type": "action", "value": 1, "condition": ""},
        "range": {
            "value": str(weapon_range.get("normal") or 5),
            "long": str(weapon_range.get("long") or ""),
            "units": "ft",
        },
        "damage": {
            "parts": [[damage_dice, damage_type]] if damage_dice and damage_type else [],
            "versatile": versatile,
        },
        "properties": properties,
        "proficient": None,
        "ability": ability,
        "attackType": "mwak" if entry.get("weapon_range", "").lower() == "melee" else "rwak",
        "type": {
            "value": weapon_type,
            "baseItem": entry.get("index", ""),
        },
    }
    system["properties"] = list(dict.fromkeys(system["properties"]))
    if magic_bonus:
        system.setdefault("bonuses", {"attack": "", "damage": ""})
        system["bonuses"]["attack"] = str(magic_bonus)
        system["bonuses"]["damage"] = str(magic_bonus)
        if "mgc" not in system["properties"]:
            system["properties"].append("mgc")

    name = entry.get("name", "Weapon")
    if magic_bonus:
        name = f"{name} +{magic_bonus}"
    return _base_item(name, "weapon", system, img="systems/dnd5e/icons/svg/items/sword.svg")


def _armor_entry(entry: dict, quantity: int, magic_bonus: int = 0) -> Dict[str, object]:
    armor_class = entry.get("armor_class", {})
    armor_type = (entry.get("armor_category") or "").lower()

    system = {
        "description": {"value": ""},
        "identifier": entry.get("index", ""),
        "quantity": quantity,
        "weight": {"value": entry.get("weight", 0) or 0, "units": "lb"},
        "price": {
            "value": entry.get("cost", {}).get("quantity", 0),
            "denomination": entry.get("cost", {}).get("unit", "gp"),
        },
        "equipped": False,
        "attunement": "none",
        "attuned": False,
        "container": None,
        "armor": {
            "value": armor_class.get("base", 10) + magic_bonus,
            "dex": armor_class.get("max_bonus", 0) if armor_class.get("dex_bonus") else 0,
        },
        "type": {"value": armor_type, "baseItem": entry.get("index", "")},
        "strength": entry.get("str_minimum", 0),
        "stealth": "disadvantage" if entry.get("stealth_disadvantage") else "",
    }
    if magic_bonus:
        system.setdefault("bonuses", {})
        system["bonuses"]["ac"] = str(magic_bonus)
    name = entry.get("name", "Armor")
    if magic_bonus:
        name = f"{name} +{magic_bonus}"
    return _base_item(name, "equipment", system, img="systems/dnd5e/icons/svg/items/armor.svg")


def _loot_entry(name: str, identifier: str, quantity: int, entry: Optional[dict] = None) -> Dict[str, object]:
    cost = entry.get("cost", {}) if entry else {}
    weight = entry.get("weight") if entry else None
    system = {
        "description": {"value": ""},
        "identifier": identifier,
        "quantity": quantity,
        "weight": {"value": weight or 0, "units": "lb" if weight else ""},
        "price": {"value": cost.get("quantity", 0), "denomination": cost.get("unit", "gp")},
        "type": {"value": entry.get("equipment_category", {}).get("name", "") if entry else "", "subtype": ""},
        "identified": True,
        "unidentified": {"description": ""},
        "container": None,
        "properties": [],
    }
    return _base_item(name, "loot", system, img="systems/dnd5e/icons/svg/items/loot.svg")


def _build_spell_activity(spell: dict, system: Dict[str, object]) -> Dict[str, object]:
    activation = system.get("activation", {})
    duration = system.get("duration", {})
    spell_range = system.get("range", {})
    concentration = bool(spell.get("concentration"))
    activity_id = f"cast{spell.get('index', 'spell')[:10]}"

    return {
        "_id": activity_id,
        "type": _spell_activity_type(spell),
        "sort": 0,
        "activation": {
            "type": activation.get("type", "action"),
            "value": activation.get("value", 1),
            "condition": activation.get("condition", ""),
            "override": False,
        },
        "consumption": {
            "targets": [],
            "spellSlot": True,
            "scaling": {"allowed": False, "max": ""},
        },
        "description": {},
        "duration": {
            "units": duration.get("units", "inst"),
            "value": duration.get("value", "0"),
            "concentration": concentration,
            "override": False,
        },
        "effects": [],
        "ignoreTraits": {"idi": False, "idr": False, "idv": False, "ida": False, "idm": False},
        "isOverTimeFlag": False,
        "macroData": {"name": "", "command": ""},
        "midiProperties": {},
        "otherActivityAsParentType": True,
        "otherActivityId": "none",
        "range": {
            "value": str(spell_range.get("value", "")),
            "units": spell_range.get("units", "self"),
            "override": False,
        },
        "roll": {"prompt": False, "visible": False},
        "target": {
            "prompt": True,
            "override": False,
            "affects": {"choice": False},
            "template": {
                "contiguous": False,
                "type": "",
                "size": "",
                "width": "",
                "height": "",
                "units": "ft",
            },
        },
        "useConditionText": "",
        "useConditionReason": "",
        "uses": {"spent": 0, "recovery": []},
    }


def _spell_activity_type(spell: dict) -> str:
    if spell.get("attack_type"):
        return "attack"
    if spell.get("damage"):
        return "damage"
    return "utility"


def _spell_properties(spell: dict, components: Dict[str, bool]) -> List[str]:
    props: List[str] = []
    if components.get("v"):
        props.append("verbal")
    if components.get("s"):
        props.append("somatic")
    if components.get("m"):
        props.append("material")
    if spell.get("concentration"):
        props.append("concentration")
    if spell.get("ritual"):
        props.append("ritual")
    return props


def _spell_progression(class_data: ClassData) -> str:
    spellcasting = class_data.spellcasting or {}
    level = spellcasting.get("level")
    if level is None:
        return "none" if not spellcasting else "full"
    if level <= 1:
        return "full"
    if level == 2:
        return "half"
    if level == 3:
        return "third"
    return "full"


def _format_html(lines: Iterable[str] | str) -> str:
    if isinstance(lines, str):
        text = lines.strip()
        if not text:
            return ""
        return f"<p>{text}</p>"
    paragraphs = [line.strip() for line in lines if line and isinstance(line, str) and line.strip()]
    if not paragraphs:
        return ""
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)


def _build_prototype_token(state: CharacterState) -> Dict[str, object]:
    return {
        "name": state.name,
        "actorLink": True,
        "texture": {"src": "icons/svg/mystery-man.svg", "alphaThreshold": 0.75},
        "width": 1,
        "height": 1,
        "displayName": 0,
        "displayBars": 0,
        "disposition": 1,
        "bar1": {"attribute": "attributes.hp"},
        "bar2": {"attribute": None},
        "flags": {},
        "sight": {"enabled": True, "range": 60, "angle": 360, "visionMode": "basic", "attenuation": 0, "brightness": 0, "color": None, "contrast": 0, "saturation": 0},
        "light": {"alpha": 0.5, "angle": 360, "bright": 0, "color": None, "coloration": 1, "dim": 0, "luminosity": 0.5, "saturation": 0, "shadows": 0, "animation": {"type": None, "speed": 5, "intensity": 5}},
    }


def _random_id() -> str:
    return secrets.token_hex(8)


def _foundry_size(size: str) -> str:
    mapping = {
        "tiny": "tiny",
        "small": "sm",
        "medium": "med",
        "large": "lg",
        "huge": "huge",
        "gargantuan": "grg",
    }
    return mapping.get(size.lower(), "med")


def _ensure_positive_int(value) -> int:
    try:
        return max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return 0


def _weapon_type(entry: dict) -> str:
    category = (entry.get("weapon_category") or "").lower()
    weapon_range = (entry.get("weapon_range") or "").lower()
    prefix = "martial" if category == "martial" else "simple"
    suffix = "M" if weapon_range == "melee" else "R"
    return f"{prefix}{suffix}"


def _weapon_ability(entry: dict) -> str:
    properties = [prop.get("index", "") for prop in entry.get("properties", [])]
    if "finesse" in properties or entry.get("weapon_range", "").lower() == "ranged":
        return "dex"
    return "str"


def _split_magic_index(index: str) -> Tuple[str, int]:
    if "+" in index:
        base, bonus = index.split("+", 1)
        try:
            return base, int(bonus)
        except ValueError:
            return base, 0
    return index, 0
