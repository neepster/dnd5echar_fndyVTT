from __future__ import annotations

import random
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PySide6 import QtCore

from .constants import ABILITY_NAMES, ABILITY_SCORES, SKILL_NAMES
from .data import SRDData
from .data.srd import ClassData, RaceData, SubraceData
from .models import CharacterState
from . import rules


@dataclass(slots=True)
class ChoiceOption:
    id: str
    label: str
    kind: str
    index: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ChoiceGroup:
    id: str
    source: str
    name: str
    choose: int
    options: List[ChoiceOption]
    description: Optional[str] = None


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

CLASS_ABILITY_PRIORITIES: Dict[str, List[str]] = {
    "barbarian": ["str", "con", "dex", "wis", "cha", "int"],
    "bard": ["cha", "dex", "con", "wis", "int", "str"],
    "cleric": ["wis", "con", "str", "dex", "int", "cha"],
    "druid": ["wis", "con", "dex", "int", "str", "cha"],
    "fighter": ["str", "con", "dex", "wis", "cha", "int"],
    "monk": ["dex", "wis", "con", "str", "int", "cha"],
    "paladin": ["str", "cha", "con", "wis", "dex", "int"],
    "ranger": ["dex", "wis", "con", "str", "int", "cha"],
    "rogue": ["dex", "int", "cha", "wis", "con", "str"],
    "sorcerer": ["cha", "con", "dex", "wis", "int", "str"],
    "warlock": ["cha", "con", "dex", "wis", "int", "str"],
    "wizard": ["int", "dex", "con", "wis", "cha", "str"],
}

PREPARED_CASTER_CLASSES = {"cleric", "druid", "paladin", "wizard"}

LEVEL_WEIGHTS = [20, 18, 16, 14, 12, 10, 9, 8, 7, 6, 5, 4, 4, 4, 3, 3, 2, 2, 2, 1]

CLASS_STARTER_LOADOUTS: Dict[str, Dict[str, object]] = {
    "barbarian": {
        "armor": ["scale-mail"],
        "weapons": ["greataxe", "handaxe", "handaxe"],
        "gear": ["explorers-pack"],
        "gp": 50,
        "gp_per_level": 25,
    },
    "bard": {
        "armor": ["leather-armor"],
        "weapons": ["rapier", "dagger"],
        "gear": ["entertainers-pack", "lute"],
        "gp": 45,
        "gp_per_level": 20,
    },
    "cleric": {
        "armor": ["scale-mail", "shield"],
        "weapons": ["mace"],
        "gear": ["priests-pack", "holy-water-flask"],
        "gp": 55,
        "gp_per_level": 25,
    },
    "druid": {
        "armor": ["leather-armor", "shield"],
        "weapons": ["scimitar", "quarterstaff"],
        "gear": ["explorers-pack"],
        "gp": 40,
        "gp_per_level": 20,
    },
    "fighter": {
        "armor": ["chain-mail", "shield"],
        "weapons": ["longsword", "longsword", "longbow", "arrow"],
        "gear": ["dungeoneers-pack"],
        "gp": 75,
        "gp_per_level": 30,
    },
    "monk": {
        "armor": [],
        "weapons": ["shortsword", "dart", "dart", "dart", "dart"],
        "gear": ["explorers-pack"],
        "gp": 20,
        "gp_per_level": 15,
    },
    "paladin": {
        "armor": ["chain-mail", "shield"],
        "weapons": ["longsword", "warhammer"],
        "gear": ["priests-pack", "holy-water-flask"],
        "gp": 70,
        "gp_per_level": 30,
    },
    "ranger": {
        "armor": ["scale-mail"],
        "weapons": ["longbow", "arrow", "shortsword", "shortsword"],
        "gear": ["explorers-pack"],
        "gp": 60,
        "gp_per_level": 25,
    },
    "rogue": {
        "armor": ["leather-armor"],
        "weapons": ["rapier", "shortbow", "arrow"],
        "gear": ["burglars-pack"],
        "gp": 45,
        "gp_per_level": 20,
    },
    "sorcerer": {
        "armor": [],
        "weapons": ["dagger", "dagger", "crossbow-light", "crossbow-bolt", "crossbow-bolt"],
        "gear": ["explorers-pack", "crystal"],
        "gp": 60,
        "gp_per_level": 25,
    },
    "warlock": {
        "armor": ["leather-armor"],
        "weapons": ["crossbow-light", "crossbow-bolt", "crossbow-bolt", "dagger", "dagger"],
        "gear": ["scholars-pack"],
        "gp": 65,
        "gp_per_level": 25,
    },
    "wizard": {
        "armor": [],
        "weapons": ["quarterstaff", "dagger"],
        "gear": ["scholars-pack", "spellbook", "crystal"],
        "gp": 50,
        "gp_per_level": 20,
    },
}

DEFAULT_LOADOUT = {
    "armor": ["leather-armor"],
    "weapons": ["quarterstaff"],
    "gear": ["explorers-pack"],
    "gp": 40,
    "gp_per_level": 20,
}

RACE_NAME_TABLES: Dict[str, Dict[str, List[str]]] = {
    "human": {
        "male": ["Alden", "Derrik", "Marcus", "Tristan", "Roland"],
        "female": ["Elena", "Lysa", "Marian", "Seren", "Talia"],
        "surname": ["Blackwood", "Cavalier", "Harrow", "Rivers", "Thorne"],
    },
    "elf": {
        "male": ["Aelar", "Theren", "Varis", "Erevan", "Syllion"],
        "female": ["Aeris", "Lia", "Naivara", "Sylwen", "Thia"],
        "surname": ["Evenwood", "Moonwhisper", "Nightbreeze", "Silvertree", "Windrunner"],
    },
    "dwarf": {
        "male": ["Baern", "Bruen", "Dorn", "Harbek", "Rurik"],
        "female": ["Amber", "Eldeth", "Finellen", "Mardred", "Torbera"],
        "surname": ["Battlehammer", "Fireforge", "Ironfist", "Rockseeker", "Stonehelm"],
    },
    "halfling": {
        "male": ["Alton", "Cade", "Eldon", "Milo", "Wellby"],
        "female": ["Bree", "Callie", "Lavinia", "Myria", "Seraphina"],
        "surname": ["Brushgather", "Goodbarrel", "Greenbottle", "Highhill", "Tealeaf"],
    },
    "dragonborn": {
        "male": ["Aryx", "Balasar", "Khagrax", "Rhogar", "Torinn"],
        "female": ["Akra", "Kaida", "Mizra", "Sora", "Thyana"],
        "surname": ["Clethtinthiallor", "Daardendrian", "Delmirev", "Kepeshkmolik", "Turnuroth"],
    },
    "gnome": {
        "male": ["Alston", "Boddynock", "Dimble", "Finnan", "Orin"],
        "female": ["Bimpnottin", "Ella", "Lilli", "Nissa", "Zanna"],
        "surname": ["Beren", "Daergel", "Folkor", "Murnig", "Nackle"],
    },
    "half-elf": {
        "male": ["Aeric", "Corin", "Laethan", "Syllas", "Theron"],
        "female": ["Ara", "Elora", "Maia", "Rinn", "Sylia"],
        "surname": ["Amastacia", "Galanodel", "Ilphelkiir", "Siannodel", "Holimion"],
    },
    "half-orc": {
        "male": ["Dorn", "Grysh", "Krusk", "Mogar", "Thokk"],
        "female": ["Arha", "Baggi", "Emen", "Sutha", "Yevelda"],
        "surname": ["Bonecrusher", "Ironhide", "Skullcleaver", "Stormcaller", "Thrash"]
    },
    "tiefling": {
        "male": ["Akmenos", "Damien", "Leucis", "Morthos", "Zephiros"],
        "female": ["Akmena", "Beleth", "Kasdeya", "Orianna", "Zephra"],
        "surname": ["Fateborn", "Hellfire", "Nightbloom", "Runeweaver", "Shadowstep"],
    },
}

DEFAULT_NAME_TABLE = {
    "male": ["Rowan", "Galen", "Tobin", "Lucan", "Merrick"],
    "female": ["Ayla", "Celia", "Daphne", "Lyra", "Mira"],
    "surname": ["Ashford", "Brightwood", "Fairwind", "Starling", "Waverly"],
}


class CharacterViewModel(QtCore.QObject):
    stateChanged = QtCore.Signal()
    derivedChanged = QtCore.Signal()
    choiceGroupsChanged = QtCore.Signal()
    messageEmitted = QtCore.Signal(str)

    def __init__(self, srd: Optional[SRDData] = None, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.srd = srd or SRDData()
        self.state = CharacterState()
        self.choice_groups: Dict[str, ChoiceGroup] = {}
        self._saving_throw_proficiencies: Set[str] = set()
        self._signal_suppression = 0
        self._refresh_everything()

    # ------------------------------------------------------------------
    # Public helpers used by the UI
    def _lock_field(self, field: str, locked: bool) -> None:
        if locked:
            self.state.randomization_locks.add(field)
        else:
            self.state.randomization_locks.discard(field)

    def _is_locked(self, field: str) -> bool:
        return field in self.state.randomization_locks

    def race_options(self) -> List[Tuple[str, str]]:
        return sorted(
            ((race.index, race.name) for race in self.srd.races.values()),
            key=lambda item: item[1],
        )

    def subrace_options(self) -> List[Tuple[str, str]]:
        if not self.state.race:
            return []
        race = self.srd.races.get(self.state.race)
        if not race:
            return []
        return sorted(((sub.index, sub.name) for sub in race.subraces.values()), key=lambda item: item[1])

    def class_options(self) -> List[Tuple[str, str]]:
        return sorted(((cls.index, cls.name) for cls in self.srd.classes.values()), key=lambda item: item[1])

    def subclass_options(self) -> List[Tuple[str, str]]:
        if not self.state.character_class:
            return []
        class_data = self.srd.classes.get(self.state.character_class)
        if not class_data:
            return []
        return sorted(((sub.index, sub.name) for sub in class_data.subclasses.values()), key=lambda item: item[1])

    def background_options(self) -> List[Tuple[str, str]]:
        return sorted(((bg.index, bg.name) for bg in self.srd.backgrounds.values()), key=lambda item: item[1])

    def ability_score_breakdown(self) -> Dict[str, Dict[str, int]]:
        data: Dict[str, Dict[str, int]] = {}
        for ability in ABILITY_SCORES:
            data[ability] = {
                "base": self.state.base_ability_scores[ability],
                "racial": self.state.racial_ability_bonuses[ability],
                "subrace": self.state.subrace_ability_bonuses[ability],
                "manual": self.state.manual_ability_bonuses[ability],
                "total": self.state.total_ability_score(ability),
            }
        return data

    def choice_groups_for_display(self) -> List[ChoiceGroup]:
        return list(self.choice_groups.values())

    # ------------------------------------------------------------------
    # State mutators
    def set_name(self, name: str) -> None:
        self.state.name = name.strip() or "New Adventurer"
        self._lock_field("name", bool(name.strip()))
        self._emit_state_changed()

    def set_level(self, level: int) -> None:
        level = max(1, min(20, int(level)))
        if level == self.state.level:
            return
        self.state.level = level
        self._lock_field("level", True)
        self._refresh_everything()

    def set_race(self, race_index: Optional[str]) -> None:
        self.state.race = race_index.lower() if race_index else None
        self._lock_field("race", bool(race_index))
        # Reset subrace if not compatible
        if self.state.subrace:
            race_obj = self.srd.races.get(self.state.race) if self.state.race else None
            if not race_obj or self.state.subrace not in race_obj.subraces:
                self.state.subrace = None
                self._lock_field("subrace", False)
        self._refresh_everything()

    def set_subrace(self, subrace_index: Optional[str]) -> None:
        self.state.subrace = subrace_index.lower() if subrace_index else None
        self._lock_field("subrace", bool(subrace_index))
        self._refresh_everything()

    def set_class(self, class_index: Optional[str]) -> None:
        self.state.character_class = class_index.lower() if class_index else None
        self._lock_field("class", bool(class_index))
        # Reset subclass if incompatible
        if self.state.subclass:
            class_obj = self.srd.classes.get(self.state.character_class) if self.state.character_class else None
            if not class_obj or self.state.subclass not in class_obj.subclasses:
                self.state.subclass = None
                self._lock_field("subclass", False)
        self._refresh_everything()

    def set_subclass(self, subclass_index: Optional[str]) -> None:
        self.state.subclass = subclass_index.lower() if subclass_index else None
        self._lock_field("subclass", bool(subclass_index))
        self._refresh_everything()

    def set_background(self, background_index: Optional[str]) -> None:
        self.state.background = background_index.lower() if background_index else None
        self._lock_field("background", bool(background_index))
        self._refresh_everything()

    def set_alignment(self, alignment: Optional[str]) -> None:
        self.state.alignment = alignment
        self._lock_field("alignment", bool(alignment))
        self._emit_state_changed()

    def set_gender(self, gender: Optional[str]) -> None:
        normalized = gender.lower() if gender else None
        if normalized not in {"male", "female", None}:
            normalized = None
        self.state.gender = normalized
        self._lock_field("gender", bool(normalized))
        self._emit_state_changed()

    def set_base_ability_score(self, ability: str, value: int) -> None:
        self.state.set_base_ability_score(ability, value)
        self._lock_field("abilities", True)
        self._refresh_derived()

    def set_manual_ability_bonus(self, ability: str, value: int) -> None:
        self.state.set_manual_bonus(ability, value)
        self._lock_field("abilities", True)
        self._refresh_derived()

    def toggle_skill_proficiency(self, skill_index: str, enabled: bool) -> None:
        normalized = _normalize_skill_index(skill_index)
        if enabled:
            self.state.selected_skill_proficiencies.add(normalized)
        else:
            self.state.selected_skill_proficiencies.discard(normalized)
        self._lock_field("skills", True)
        if not self.state.selected_skill_proficiencies and not self.state.selected_skill_expertise:
            self._lock_field("skills", False)
        self._refresh_derived()

    def toggle_expertise(self, skill_index: str, enabled: bool) -> None:
        normalized = _normalize_skill_index(skill_index)
        if enabled:
            self.state.selected_skill_expertise.add(normalized)
        else:
            self.state.selected_skill_expertise.discard(normalized)
        self._lock_field("skills", True)
        if not self.state.selected_skill_proficiencies and not self.state.selected_skill_expertise:
            self._lock_field("skills", False)
        self._refresh_derived()

    def set_choice_selection(self, group_id: str, selected_ids: Iterable[str]) -> None:
        group = self.choice_groups.get(group_id)
        if not group:
            return
        selected = {sid for sid in selected_ids if any(opt.id == sid for opt in group.options)}
        if len(selected) > group.choose:
            # Trim extras deterministically
            selected = set(sorted(selected)[: group.choose])
        self.state.choice_selections[group_id] = selected
        if selected:
            self._lock_field("choices", True)
        elif all(not choices for choices in self.state.choice_selections.values()):
            self._lock_field("choices", False)
        self._refresh_everything()


    def spells_by_level(self) -> Dict[int, List[dict]]:
        class_idx = self.state.character_class
        if not class_idx:
            return {}
        spells = list(self.srd.spells_for_class(class_idx))
        if self.state.subclass:
            spells.extend(self.srd.spells_for_subclass(self.state.subclass))
        grouped: Dict[int, List[dict]] = {}
        for spell in spells:
            level = spell.get('level', 0)
            grouped.setdefault(level, []).append(spell)
        for level, items in grouped.items():
            items.sort(key=lambda entry: entry.get('name', ''))
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    def is_spell_selected(self, spell_index: str, kind: str = 'known') -> bool:
        return spell_index.lower() in {s.lower() for s in self.state.selected_spells.get(kind, set())}

    def toggle_spell(self, spell_index: str, kind: str = 'known', enabled: bool = True) -> None:
        spell_index = spell_index.lower()
        selection = self.state.selected_spells.setdefault(kind, set())
        if enabled:
            selection.add(spell_index)
            if kind == 'prepared':
                self.state.selected_spells.setdefault('known', set()).add(spell_index)
        else:
            selection.discard(spell_index)
            if kind == 'known':
                self.state.selected_spells.get('prepared', set()).discard(spell_index)
        self._emit_state_changed()

    def randomize_character(self) -> None:
        """Generate a random but sensible character."""

        available_classes = list(self.srd.classes.values())
        if not available_classes:
            return

        state = self.state

        # Determine class
        if self._is_locked("class") and state.character_class:
            class_data = self.srd.classes.get(state.character_class)
        else:
            class_data = random.choice(available_classes)
            state.character_class = class_data.index
            self._lock_field("class", False)

        if not class_data:
            class_data = random.choice(available_classes)
            state.character_class = class_data.index

        # Determine level
        if not self._is_locked("level") or state.level <= 0:
            state.level = random.choices(range(1, 21), weights=LEVEL_WEIGHTS, k=1)[0]

        # Determine race
        if self._is_locked("race") and state.race:
            race = self.srd.races.get(state.race)
        else:
            race = self._pick_weighted_race(class_data)
            state.race = race.index
            self._lock_field("race", False)

        if not race:
            race = random.choice(list(self.srd.races.values()))
            state.race = race.index

        # Determine subrace
        if race.subraces:
            if self._is_locked("subrace") and state.subrace in race.subraces:
                subrace_choice = race.subraces[state.subrace]
            else:
                subrace_choice = self._pick_weighted_subrace(race, class_data)
                state.subrace = subrace_choice.index if subrace_choice else None
                self._lock_field("subrace", False)
        else:
            subrace_choice = None
            state.subrace = None

        # Determine subclass if applicable
        if class_data.subclasses:
            if self._is_locked("subclass") and state.subclass in class_data.subclasses:
                subclass_choice = class_data.subclasses[state.subclass]
            else:
                eligible = []
                for subclass in class_data.subclasses.values():
                    levels = subclass.features_by_level.keys()
                    min_level = min(levels) if levels else 3
                    if state.level >= min_level:
                        eligible.append(subclass)
                subclass_choice = random.choice(eligible) if eligible else None
                state.subclass = subclass_choice.index if subclass_choice else None
                self._lock_field("subclass", False)
        else:
            subclass_choice = None
            state.subclass = None

        # Background and alignment
        if self._is_locked("background") and state.background:
            background = self.srd.backgrounds.get(state.background)
        else:
            background = random.choice(list(self.srd.backgrounds.values())) if self.srd.backgrounds else None
            state.background = background.index if background else None
            if background is not None:
                self._lock_field("background", False)

        if self._is_locked("alignment") and state.alignment:
            alignment_entry = next((entry for entry in self.srd.alignments if entry.get("index") == state.alignment), None)
        else:
            alignment_entry = random.choice(self.srd.alignments) if self.srd.alignments else None
            state.alignment = alignment_entry.get("index") if alignment_entry else None
            self._lock_field("alignment", False)

        if self._is_locked("gender") and state.gender:
            gender = state.gender
        else:
            gender = random.choice(["male", "female"])
            state.gender = gender
            self._lock_field("gender", False)

        if not self._is_locked("name"):
            generated_name = _generate_character_name(race, gender)
            state.name = generated_name
            self._lock_field("name", False)

        if not self._is_locked("skills"):
            state.selected_skill_proficiencies.clear()
            state.selected_skill_expertise.clear()

        if not self._is_locked("spells"):
            state.selected_spells.clear()
            state.prepared_spells.clear()

        if not self._is_locked("abilities"):
            state.manual_hit_points = None
            state.base_ability_scores = {ability: 10 for ability in ABILITY_SCORES}
            state.manual_ability_bonuses = {ability: 0 for ability in ABILITY_SCORES}

        if not self._is_locked("notes"):
            state.notes = ""

        equipment_list, generated_currency = self._generate_equipment_and_currency(class_data)

        if not self._is_locked("equipment"):
            state.equipment = equipment_list
            self._lock_field("equipment", False)

        if not self._is_locked("currency"):
            state.currency = generated_currency
            self._lock_field("currency", False)

        class_data = self.srd.classes.get(state.character_class) if state.character_class else None
        race = self.srd.races.get(state.race) if state.race else None

        with self._suspend_signals():
            if not self._is_locked("abilities"):
                self._apply_standard_array(class_data)
            self._recalculate_racial_bonuses()
            self._rebuild_choice_groups()
            self._auto_populate_choice_selections(overwrite=not self._is_locked("choices"))
            if not self._is_locked("spells"):
                self._auto_assign_spells(class_data)
            self._refresh_derived()

        self._emit_state_changed()
        self.choiceGroupsChanged.emit()
        self.derivedChanged.emit()

    # ------------------------------------------------------------------
    def choice_skill_selections(self) -> Set[str]:
        return self._skills_from_choice_selections()

    def choice_language_selections(self) -> Set[str]:
        return self._languages_from_choice_selections()

    def saving_throw_proficiencies(self) -> Set[str]:
        return set(self._saving_throw_proficiencies)

    def _refresh_everything(self) -> None:
        self._recalculate_racial_bonuses()
        self._rebuild_choice_groups()
        self._refresh_derived()
        self._emit_state_changed()

    def _refresh_derived(self) -> None:
        class_data = self.srd.classes.get(self.state.character_class) if self.state.character_class else None
        race_data = self.srd.races.get(self.state.race) if self.state.race else None
        auto_skills, auto_tools, auto_langs = self._gather_automatic_resources(class_data, race_data)
        choice_skills = self._skills_from_choice_selections()
        choice_languages = self._languages_from_choice_selections()
        choice_tools = self._tools_from_choice_selections()
        combined_skills = auto_skills | self.state.selected_skill_proficiencies | choice_skills
        self.state.automatic_skill_proficiencies = auto_skills
        self.state.automatic_tool_proficiencies = auto_tools | choice_tools
        self.state.automatic_languages = auto_langs | choice_languages
        expertise = self.state.selected_skill_expertise
        saving_throws = self._saving_throw_proficiencies
        rules.update_derived_stats(self.state, class_data, race_data, combined_skills, expertise, saving_throws)
        if self._signal_suppression == 0:
            self.derivedChanged.emit()

    def _emit_state_changed(self) -> None:
        if self._signal_suppression == 0:
            self.stateChanged.emit()

    # ------------------------------------------------------------------
    def _recalculate_racial_bonuses(self) -> None:
        # Reset bonuses
        for ability in ABILITY_SCORES:
            self.state.racial_ability_bonuses[ability] = 0
            self.state.subrace_ability_bonuses[ability] = 0
        race = self.srd.races.get(self.state.race) if self.state.race else None
        if race:
            for bonus in race.ability_bonuses:
                ability = bonus.get("ability_score", {}).get("index", "").lower()
                if ability:
                    self.state.racial_ability_bonuses[ability] += bonus.get("bonus", 0)
        if race and self.state.subrace:
            subrace = race.subraces.get(self.state.subrace)
            if subrace:
                for bonus in subrace.ability_bonuses:
                    ability = bonus.get("ability_score", {}).get("index", "").lower()
                    if ability:
                        self.state.subrace_ability_bonuses[ability] += bonus.get("bonus", 0)

    def _gather_automatic_resources(
        self, class_data: Optional[ClassData], race_data: Optional[RaceData]
    ) -> Tuple[Set[str], Set[str], Set[str]]:
        skills: Set[str] = set()
        tools: Set[str] = set()
        languages: Set[str] = set()

        # Race contributions
        if race_data:
            skills |= _skills_from_proficiencies(race_data.starting_proficiencies)
            tools |= _tools_from_proficiencies(race_data.starting_proficiencies)
            languages |= {lang["index"] for lang in race_data.languages}
            if self.state.subrace:
                subrace = race_data.subraces.get(self.state.subrace)
                if subrace:
                    skills |= _skills_from_proficiencies(subrace.proficiencies)
                    tools |= _tools_from_proficiencies(subrace.proficiencies)
                    languages |= {lang["index"] for lang in subrace.languages}

        # Background contributions
        if self.state.background:
            background = self.srd.backgrounds.get(self.state.background)
            if background:
                skills |= _skills_from_proficiencies(background.starting_proficiencies)
                tools |= _tools_from_proficiencies(background.starting_proficiencies)
                if background.language_options is None:
                    # Some backgrounds provide fixed languages, but SRD background does not
                    pass

        # Class contributions
        if class_data:
            tools |= _tools_from_proficiencies(class_data.proficiencies)
            self._saving_throw_proficiencies = _saving_throws_from_proficiencies(class_data.saving_throws)
        else:
            self._saving_throw_proficiencies = set()

        return skills, tools, languages

    def _rebuild_choice_groups(self) -> None:
        new_groups: Dict[str, ChoiceGroup] = {}

        # Race options
        race = self.srd.races.get(self.state.race) if self.state.race else None
        if race:
            if race.language_options:
                group = _choice_group_from_option_block(
                    group_id=f"race:{race.index}:languages",
                    source="race",
                    name=f"{race.name} Bonus Languages",
                    block=race.language_options,
                    option_kind_hint="language",
                )
                if group:
                    new_groups[group.id] = group
            if race.starting_proficiency_options:
                group = _choice_group_from_option_block(
                    group_id=f"race:{race.index}:proficiencies",
                    source="race",
                    name=f"{race.name} Bonus Proficiencies",
                    block=race.starting_proficiency_options,
                )
                if group:
                    new_groups[group.id] = group

        # Subrace options
        if race and self.state.subrace:
            subrace = race.subraces.get(self.state.subrace)
            if subrace and subrace.language_options:
                group = _choice_group_from_option_block(
                    group_id=f"subrace:{subrace.index}:languages",
                    source="subrace",
                    name=f"{subrace.name} Languages",
                    block=subrace.language_options,
                    option_kind_hint="language",
                )
                if group:
                    new_groups[group.id] = group

        # Class proficiency choices
        class_data = self.srd.classes.get(self.state.character_class) if self.state.character_class else None
        if class_data:
            for idx, block in enumerate(class_data.proficiency_choices):
                group = _choice_group_from_option_block(
                    group_id=f"class:{class_data.index}:prof-{idx}",
                    source="class",
                    name=block.get("desc") or f"{class_data.name} Choice {idx + 1}",
                    block=block,
                )
                if group:
                    new_groups[group.id] = group

        # Background language options
        if self.state.background:
            background = self.srd.backgrounds.get(self.state.background)
            if background and background.language_options:
                group = _choice_group_from_option_block(
                    group_id=f"background:{background.index}:languages",
                    source="background",
                    name=f"{background.name} Languages",
                    block=background.language_options,
                    option_kind_hint="language",
                )
                if group:
                    new_groups[group.id] = group

        # Filter stale selections
        for group_id in list(self.state.choice_selections.keys()):
            if group_id not in new_groups:
                self.state.choice_selections.pop(group_id)
            else:
                options = {opt.id for opt in new_groups[group_id].options}
                self.state.choice_selections[group_id] = {
                    opt_id
                    for opt_id in self.state.choice_selections[group_id]
                    if opt_id in options
                }

        self.choice_groups = new_groups
        if self._signal_suppression == 0:
            self.choiceGroupsChanged.emit()

    # ------------------------------------------------------------------
    def selected_skills(self) -> Set[str]:
        skills = set(self.state.automatic_skill_proficiencies)
        skills |= self.state.selected_skill_proficiencies
        skills |= self._skills_from_choice_selections()
        return skills

    def selected_languages(self) -> Set[str]:
        languages = set(self.state.automatic_languages)
        languages |= self.state.selected_languages
        languages |= self._languages_from_choice_selections()
        return languages

    def _skills_from_choice_selections(self) -> Set[str]:
        skills: Set[str] = set()
        for group_id, selected in self.state.choice_selections.items():
            group = self.choice_groups.get(group_id)
            if not group:
                continue
            for opt in group.options:
                if opt.id in selected and opt.kind == "skill":
                    value = opt.index or opt.id
                    skills.add(_normalize_skill_index(value))
        return skills

    def _languages_from_choice_selections(self) -> Set[str]:
        langs: Set[str] = set()
        for group_id, selected in self.state.choice_selections.items():
            group = self.choice_groups.get(group_id)
            if not group:
                continue
            for opt in group.options:
                if opt.id in selected and opt.kind == "language":
                    langs.add(opt.index or opt.id)
        return langs

    def _tools_from_choice_selections(self) -> Set[str]:
        tools: Set[str] = set()
        for group_id, selected in self.state.choice_selections.items():
            group = self.choice_groups.get(group_id)
            if not group:
                continue
            for opt in group.options:
                if opt.id in selected and opt.kind == "tool":
                    value = opt.index or opt.id
                    if isinstance(value, str):
                        entry = self.srd.proficiencies.get(value)
                        if entry:
                            prof_type = entry.get("type", "")
                            if prof_type in {"Artisan's Tools", "Musical Instruments", "Gaming Sets", "Vehicles", "Other"}:
                                tools.add(value)
                            elif opt.kind == "tool":
                                tools.add(value)
                        else:
                            tools.add(value)
                elif opt.id in selected:
                    value = opt.index or opt.id
                    entry = self.srd.proficiencies.get(value) if isinstance(value, str) else None
                    if entry and entry.get("type", "") in {"Artisan's Tools", "Musical Instruments", "Gaming Sets", "Vehicles", "Other"}:
                        tools.add(value)
        return tools

    def _generate_equipment_and_currency(self, class_data: Optional[ClassData]) -> Tuple[List[str], Dict[str, int]]:
        loadout = _loadout_for_class(class_data.index if class_data else None)
        equipment: List[str] = []
        for category in ("armor", "weapons", "gear"):
            items = loadout.get(category, [])
            if isinstance(items, list):
                equipment.extend(items)

        magic_bonus = 0
        if self.state.level >= 16:
            magic_bonus = 3
        elif self.state.level >= 11:
            magic_bonus = 2
        elif self.state.level >= 5:
            magic_bonus = 1

        if magic_bonus > 0:
            for idx, item_index in enumerate(equipment):
                entry = self.srd.equipment.get(item_index)
                if entry and (entry.get("equipment_category", {}).get("index", "").lower() == "weapon"):
                    equipment[idx] = f"{item_index}+{magic_bonus}"
                    break

        base_gp = loadout.get("gp", 40)
        gp_per_level = loadout.get("gp_per_level", 20)
        level = max(1, self.state.level)
        total_gp = base_gp + max(0, level - 1) * gp_per_level

        currency = {
            "pp": _ensure_positive_int(loadout.get("pp", 0)),
            "gp": _ensure_positive_int(total_gp),
            "ep": _ensure_positive_int(loadout.get("ep", 0)),
            "sp": _ensure_positive_int(loadout.get("sp", 0)),
            "cp": _ensure_positive_int(loadout.get("cp", 0)),
        }
        return equipment, currency

    @contextmanager
    def _suspend_signals(self):
        self._signal_suppression += 1
        try:
            yield
        finally:
            self._signal_suppression = max(0, self._signal_suppression - 1)

    def _apply_standard_array(self, class_data: Optional[ClassData]) -> None:
        priorities = list(CLASS_ABILITY_PRIORITIES.get(class_data.index if class_data else "", ABILITY_SCORES))
        ordered: List[str] = []
        for ability in priorities:
            if ability not in ordered:
                ordered.append(ability)
        for ability in ABILITY_SCORES:
            if ability not in ordered:
                ordered.append(ability)

        scores = list(STANDARD_ARRAY)
        assignments: Dict[str, int] = {}
        for ability, score in zip(ordered, scores):
            assignments[ability] = score
        fallback = scores[-1]
        for ability in ABILITY_SCORES:
            self.state.base_ability_scores[ability] = assignments.get(ability, fallback)

    def _auto_populate_choice_selections(self, overwrite: bool = True) -> None:
        if not self.choice_groups:
            return
        for group in self.choice_groups.values():
            options = [opt.id for opt in group.options]
            if not options or group.choose <= 0:
                continue
            existing = set(self.state.choice_selections.get(group.id, set()))
            available = [opt for opt in options if opt not in existing]
            if overwrite:
                pool = options
                pick_count = min(group.choose, len(pool))
                if pick_count <= 0:
                    continue
                selection = set(random.sample(pool, pick_count))
                self.state.choice_selections[group.id] = selection
            else:
                needed = group.choose - len(existing)
                if needed <= 0:
                    continue
                pick_count = min(needed, len(available))
                if pick_count <= 0:
                    continue
                selection = existing | set(random.sample(available, pick_count))
                self.state.choice_selections[group.id] = selection

    def _auto_assign_spells(self, class_data: Optional[ClassData]) -> None:
        if not class_data:
            self.state.selected_spells.clear()
            return
        level_info = class_data.levels.get(self.state.level) if class_data.levels else None
        if not level_info or not level_info.spellcasting:
            self.state.selected_spells.clear()
            return

        spells_by_level = self.spells_by_level()
        selected_known: Set[str] = set()
        selected_prepared: Set[str] = set()

        spellcasting = level_info.spellcasting
        cantrips_known = spellcasting.get("cantrips_known", 0)
        if cantrips_known:
            cantrips = spells_by_level.get(0, [])
            if cantrips:
                for spell in random.sample(cantrips, min(cantrips_known, len(cantrips))):
                    selected_known.add(spell["index"].lower())

        leveled_spells: List[dict] = []
        for lvl in range(1, 10):
            if spellcasting.get(f"spell_slots_level_{lvl}", 0) > 0:
                leveled_spells.extend(spells_by_level.get(lvl, []))
        if leveled_spells:
            leveled_spells = list({spell["index"]: spell for spell in leveled_spells}.values())

        spells_known = spellcasting.get("spells_known")
        if spells_known and leveled_spells:
            for spell in random.sample(leveled_spells, min(spells_known, len(leveled_spells))):
                selected_known.add(spell["index"].lower())

        if class_data.index in PREPARED_CASTER_CLASSES and leveled_spells:
            ability_idx = rules.spellcasting_ability_index(class_data)
            ability_mod = self.state.ability_modifier(ability_idx) if ability_idx else 0
            prepared_count = max(1, ability_mod + self.state.level)
            for spell in random.sample(leveled_spells, min(prepared_count, len(leveled_spells))):
                selected_prepared.add(spell["index"].lower())
                selected_known.add(spell["index"].lower())

        self.state.selected_spells = {}
        if selected_known:
            self.state.selected_spells["known"] = selected_known
        if selected_prepared:
            self.state.selected_spells["prepared"] = selected_prepared
        self.state.prepared_spells = set(selected_prepared)

    def _pick_weighted_race(self, class_data: ClassData) -> RaceData:
        races = list(self.srd.races.values())
        weights = [
            _score_race_for_class(race, class_data)
            for race in races
        ]
        return random.choices(races, weights=weights, k=1)[0]

    def _pick_weighted_subrace(self, race: RaceData, class_data: ClassData) -> Optional[SubraceData]:
        if not race.subraces:
            return None
        subraces = list(race.subraces.values())
        weights = [
            _score_subrace_for_class(subrace, class_data)
            for subrace in subraces
        ]
        return random.choices(subraces, weights=weights, k=1)[0]


# ----------------------------------------------------------------------
def _normalize_skill_index(value: str) -> str:
    if value.startswith("skill-"):
        return value.split("skill-")[-1]
    return value


def _skills_from_proficiencies(proficiencies: Iterable[dict]) -> Set[str]:
    skills: Set[str] = set()
    for prof in proficiencies or []:
        index = prof.get("index", "")
        if index.startswith("skill-"):
            skills.add(_normalize_skill_index(index))
        elif prof.get("type") == "Skill":
            skills.add(_normalize_skill_index(index))
    return skills


def _tools_from_proficiencies(proficiencies: Iterable[dict]) -> Set[str]:
    tools: Set[str] = set()
    for prof in proficiencies or []:
        if prof.get("type") in {"Tool", "Artisans Tools", "Instrument", "Gaming Set", "Other"}:
            tools.add(prof.get("index", ""))
        elif prof.get("type") in {"Weapon", "Armor"}:
            tools.add(prof.get("index", ""))
    return tools


def _saving_throws_from_proficiencies(proficiencies: Iterable[dict]) -> Set[str]:
    saves: Set[str] = set()
    for prof in proficiencies or []:
        index = prof.get("index", "")
        if index.startswith("saving-throw-"):
            saves.add(index.split("saving-throw-")[-1])
    return saves


def _choice_group_from_option_block(
    group_id: str,
    source: str,
    name: str,
    block: dict,
    option_kind_hint: Optional[str] = None,
) -> Optional[ChoiceGroup]:
    if not isinstance(block, dict):
        return None
    try:
        choose = int(block.get("choose") or 0)
    except (TypeError, ValueError):
        return None
    options_block = block.get("from") or block.get("options")
    desc = block.get("desc")

    if isinstance(options_block, dict) and options_block.get("option_set_type") == "options_array":
        options_raw = options_block.get("options", [])
    elif isinstance(options_block, dict) and "options" in options_block:
        options_raw = options_block.get("options", [])
    elif isinstance(options_block, list):
        options_raw = options_block
    else:
        return None

    options: List[ChoiceOption] = []
    for opt in options_raw:
        item = opt.get("item") if isinstance(opt, dict) else opt
        if not item:
            if isinstance(opt, dict) and opt.get("option_type") == "choice":
                nested_block = opt.get("choice")
                nested_group = _choice_group_from_option_block(
                    group_id=f"{group_id}:nested",
                    source=source,
                    name=name,
                    block=nested_block,
                    option_kind_hint=option_kind_hint,
                )
                if nested_group:
                    options.extend(nested_group.options)
            continue
        index = item.get("index")
        if isinstance(index, str):
            index = index.lower()
        label = item.get("name") or (index or "Option")
        kind = option_kind_hint or _infer_option_kind(index)
        option_id = index or label.lower()
        options.append(ChoiceOption(id=option_id, label=label, kind=kind, index=index))

    if not options or not choose:
        return None
    return ChoiceGroup(id=group_id, source=source, name=name, choose=choose, options=options, description=desc)


def _infer_option_kind(index: Optional[str]) -> str:
    if not index:
        return "misc"
    if index.startswith("skill-"):
        return "skill"
    if index.startswith("language-"):
        return "language"
    if index.startswith("tool-"):
        return "tool"
    if index.startswith("instrument-"):
        return "tool"
    if index.startswith("armor-") or index.startswith("weapon-"):
        return "equipment"
    if index.startswith("saving-throw-"):
        return "saving-throw"
    if index.startswith("ability-score-"):
        return "ability"
    return "misc"


def _score_race_for_class(race: RaceData, class_data: ClassData) -> float:
    priorities = CLASS_ABILITY_PRIORITIES.get(class_data.index, ABILITY_SCORES)
    primary = priorities[0]
    secondary = priorities[1] if len(priorities) > 1 else None

    score = 0.0
    for bonus in race.ability_bonuses:
        ability = bonus.get("ability_score", {}).get("index", "").lower()
        value = bonus.get("bonus", 0)
        if ability == primary:
            score += value * 2
        elif ability == secondary:
            score += value * 1.5
        else:
            score += value * 0.75
    return score or 1.0


def _score_subrace_for_class(subrace: SubraceData, class_data: ClassData) -> float:
    priorities = CLASS_ABILITY_PRIORITIES.get(class_data.index, ABILITY_SCORES)
    primary = priorities[0]
    secondary = priorities[1] if len(priorities) > 1 else None

    score = 0.0
    for bonus in subrace.ability_bonuses:
        ability = bonus.get("ability_score", {}).get("index", "").lower()
        value = bonus.get("bonus", 0)
        if ability == primary:
            score += value * 2
        elif ability == secondary:
            score += value * 1.5
        else:
            score += value * 0.75
    return score or 1.0


def _loadout_for_class(class_index: Optional[str]) -> Dict[str, object]:
    if class_index and class_index in CLASS_STARTER_LOADOUTS:
        return CLASS_STARTER_LOADOUTS[class_index]
    return DEFAULT_LOADOUT


def _ensure_positive_int(value) -> int:
    try:
        return max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return 0


def _split_magic_index(index: str) -> Tuple[str, int]:
    if "+" in index:
        base, bonus = index.split("+", 1)
        try:
            value = int(bonus)
        except ValueError:
            value = 0
        return base, value
    return index, 0


def _generate_character_name(race: Optional[RaceData], gender: Optional[str]) -> str:
    gender = (gender or random.choice(["male", "female"])).lower()
    race_key = race.index if race else "human"
    if race_key not in RACE_NAME_TABLES and race:
        parts = race.index.split("-")
        for candidate in (race.index, parts[0], parts[-1]):
            if candidate in RACE_NAME_TABLES:
                race_key = candidate
                break
    name_table = RACE_NAME_TABLES.get(race_key, DEFAULT_NAME_TABLE)

    given_options = name_table.get(gender, DEFAULT_NAME_TABLE.get(gender, DEFAULT_NAME_TABLE["male"]))
    surname_options = name_table.get("surname", DEFAULT_NAME_TABLE["surname"])
    given_name = random.choice(given_options) if given_options else "Arin"
    surname = random.choice(surname_options) if surname_options else "Brightwood"
    return f"{given_name} {surname}"
