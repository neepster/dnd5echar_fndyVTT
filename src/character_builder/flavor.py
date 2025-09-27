from __future__ import annotations

import csv
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import CharacterState
from .data import SRDData


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


CUSTOM_NAMES_PATH = _resource_root() / "data" / "custom" / "names.csv"
CUSTOM_HOMETOWNS_PATH = _resource_root() / "data" / "custom" / "hometowns.csv"

_CUSTOM_NAMES_CACHE: Optional[Dict[str, Dict[str, List[str]]]] = None
_CUSTOM_HOMETOWNS_CACHE: Optional[Dict[str, List[str]]] = None


LEVEL_DESCRIPTORS = {
    "novice": ["fresh-faced", "aspiring", "green", "wide-eyed"],
    "journeyman": ["seasoned", "battle-tested", "resourceful", "hardened"],
    "veteran": ["renowned", "wily", "veteran", "blooded"],
    "legend": ["legendary", "mythic", "formidable", "famed"],
}

ORIGINS = [
    "the frontier village of Briar Glen",
    "the river ports of Highfall",
    "the storm-battered cliffs of Seafarer's Rest",
    "the bustling markets of Hightower",
    "the lantern-lit alleys of Duskwall",
    "a nomadic caravan crossing the Ember Expanse",
    "the mist-veiled forests of Greyfen",
    "the labyrinthine library-city of Callios",
    "the war-torn borderlands of Redridge",
    "the sun-baked dunes of Sahri Oasis",
]

BACKGROUND_SENTENCES = {
    "acolyte": "{Subject_cap} once tended the quiet halls of a remote sanctuary, offering solace to weary pilgrims.",
    "charlatan": "No stranger to masks and aliases, {Subject_cap} slipped coins from noble purses with disarming charm.",
    "criminal": "Years spent among thieves taught {object} the value of secrets, favors, and quick getaways.",
    "entertainer": "Crowded stages and raucous taverns still echo in {possessive} step; applause was {possessive} first addiction.",
    "folk-hero": "Neighbors still whisper of the day {subject} stood alone against danger to shield humble folk.",
    "guild-artisan": "Guild workshops honed {possessive} craft, and contracts still bear {possessive} meticulous seal.",
    "hermit": "Seasons of solitude in the wilds left {object} thoughtful, listening to the wind for forgotten truths.",
    "noble": "Born to titles and responsibilities, {subject_pronoun} learned courtly poise alongside sharp political instincts.",
    "outlander": "Endless trails under open skies taught {object} to read the land and trust {possessive} instincts.",
    "sage": "Libraries became second homes, and {subject_pronoun} still quotes obscure tomes from memory.",
    "sailor": "Rolling decks and salt-stung winds seasoned {object} into a sailor who still sways with phantom tides.",
    "soldier": "Discipline, drills, and the thunder of war drums hardened {object} into a stalwart fighter.",
    "urchin": "Streets and rooftops were classrooms, and survival the only test that mattered to {object}.",
}

GENERIC_BACKGROUND = [
    "Old habits from {possessive} days as a {background_name} still color every decision.",
    "Experiences far from home tempered {object}, leaving scars and stories in equal measure.",
    "Few guess how {subject} earned {possessive} lessons, but the past shadows every choice.",
]

GOAL_PHRASES = [
    "seeks to redeem {reflexive} for a costly mistake",
    "hunts for lore that could change the realms",
    "works to unite rivals before darker threats prevail",
    "aims to carve {possessive} name into the ballads of tomorrow",
    "plans to repay a life debt that still weighs on {object}",
    "strives to safeguard innocents caught between clashing powers",
]

QUIRK_PHRASES = [
    "keeping {possessive} weathered journal close at hand",
    "whittling charms whenever nerves begin to fray",
    "reciting half-remembered proverbs for confidence",
    "collecting small tokens from every new ally",
    "touching a hidden talisman before every bold move",
    "tracing protective sigils on nearby surfaces",
]

IDEALS = [
    "justice",
    "freedom",
    "knowledge",
    "loyalty",
    "ambition",
    "mercy",
]

PHYSICAL_PROFILES = {
    "human": {"height": (58, (2, 10)), "weight": (120, (2, 4), 4), "age": (18, 70)},
    "elf": {"height": (54, (2, 10)), "weight": (90, (2, 4), 3), "age": (100, 750)},
    "dwarf": {"height": (48, (2, 8)), "weight": (130, (2, 6), 4), "age": (50, 350)},
    "halfling": {"height": (31, (2, 4)), "weight": (35, (1, 1), 1), "age": (20, 150)},
    "gnome": {"height": (35, (2, 4)), "weight": (40, (1, 1), 1), "age": (40, 400)},
    "half-elf": {"height": (57, (2, 8)), "weight": (110, (2, 4), 3), "age": (20, 180)},
    "half-orc": {"height": (58, (2, 10)), "weight": (150, (2, 6), 4), "age": (14, 75)},
    "tiefling": {"height": (57, (2, 8)), "weight": (110, (2, 4), 3), "age": (18, 110)},
    "dragonborn": {"height": (66, (2, 8)), "weight": (175, (2, 6), 6), "age": (15, 80)},
}


def generate_biography(state: CharacterState, srd: SRDData) -> str:
    name = state.name
    race = srd.races.get(state.race) if state.race else None
    class_data = srd.classes.get(state.character_class) if state.character_class else None
    subclass = None
    if class_data and state.subclass:
        subclass = class_data.subclasses.get(state.subclass)
    background = srd.backgrounds.get(state.background) if state.background else None

    pronouns = _pronoun_map(state.gender)
    context: Dict[str, str] = {
        **pronouns,
        "name": name,
        "background_name": (background.name if background else "wanderer").lower(),
        "race": race.name if race else "humanoid",
        "class_name": class_data.name if class_data else "adventurer",
        "subclass_name": subclass.name if subclass else "",
        "ideal": random.choice(IDEALS),
    }

    level_descriptor = _level_descriptor(state.level)
    origin = _custom_hometown(race) or random.choice(ORIGINS)
    class_label = _class_label(class_data, subclass)
    article = _indefinite_article(level_descriptor)
    first_sentence = (
        f"{name} is {article} {level_descriptor} {context['race'].lower()} {class_label} from {origin}."
    )

    background_sentence = _background_sentence(background, context)
    goal = random.choice(GOAL_PHRASES).format_map(context)
    quirk = random.choice(QUIRK_PHRASES).format_map(context)
    hook_sentence = f"{context['Subject_cap']} {goal} while {quirk}."
    physical_sentence = _physical_sentence(race, context)

    sentences = [first_sentence]
    if background_sentence:
        sentences.append(background_sentence)
    sentences.append(hook_sentence)
    if physical_sentence:
        sentences.append(physical_sentence)
    return " ".join(sentences)


def get_custom_name(race_index: Optional[str], gender: Optional[str]) -> Optional[str]:
    data = _load_custom_names()
    if not data:
        return None
    race_candidates = _race_candidates(race_index)
    gender_candidates = [g for g in [gender.lower() if gender else None, 'any'] if g]

    for race_key in race_candidates:
        if race_key not in data:
            continue
        options: List[str] = []
        entries = data[race_key]
        for gender_key in gender_candidates:
            options.extend(entries.get(gender_key, []))
        if options:
            return random.choice(options)
    return None


def _load_custom_names() -> Dict[str, Dict[str, List[str]]]:
    global _CUSTOM_NAMES_CACHE
    if _CUSTOM_NAMES_CACHE is not None:
        return _CUSTOM_NAMES_CACHE
    mapping: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    if CUSTOM_NAMES_PATH.exists():
        with CUSTOM_NAMES_PATH.open('r', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                race = (row.get('race') or 'any').strip().lower()
                gender = (row.get('gender') or 'any').strip().lower()
                name = (row.get('name') or '').strip()
                if name:
                    mapping[race][gender].append(name)
    _CUSTOM_NAMES_CACHE = mapping
    return mapping


def _custom_hometown(race) -> Optional[str]:
    data = _load_custom_hometowns()
    if not data:
        return None
    for race_key in _race_candidates(race.index if race else None):
        options = data.get(race_key)
        if options:
            return random.choice(options)
    return None


def _load_custom_hometowns() -> Dict[str, List[str]]:
    global _CUSTOM_HOMETOWNS_CACHE
    if _CUSTOM_HOMETOWNS_CACHE is not None:
        return _CUSTOM_HOMETOWNS_CACHE
    mapping: Dict[str, List[str]] = defaultdict(list)
    if CUSTOM_HOMETOWNS_PATH.exists():
        with CUSTOM_HOMETOWNS_PATH.open('r', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                race = (row.get('race') or 'any').strip().lower()
                place = (row.get('place') or '').strip()
                if place:
                    mapping[race].append(place)
    _CUSTOM_HOMETOWNS_CACHE = mapping
    return mapping


def _race_candidates(race_index: Optional[str]) -> List[str]:
    if not race_index:
        return ['any']
    key = race_index.lower()
    parts = key.split('-')
    candidates = [key]
    if len(parts) > 1:
        candidates.extend(parts)
    candidates.append('any')
    return candidates


def _level_descriptor(level: int) -> str:
    if level >= 15:
        bucket = "legend"
    elif level >= 9:
        bucket = "veteran"
    elif level >= 5:
        bucket = "journeyman"
    else:
        bucket = "novice"
    return random.choice(LEVEL_DESCRIPTORS[bucket])


def _class_label(class_data, subclass) -> str:
    if class_data is None:
        return "adventurer"
    if subclass:
        return f"{subclass.name} {class_data.name}"
    return class_data.name


def _background_sentence(background, context: Dict[str, str]) -> str:
    if background is None:
        return random.choice(GENERIC_BACKGROUND).format_map(context)
    template = BACKGROUND_SENTENCES.get(background.index.lower())
    if template:
        return template.format_map(context)
    fallback = random.choice(GENERIC_BACKGROUND)
    return fallback.format_map(context)


def _indefinite_article(word: str) -> str:
    if not word:
        return "a"
    return "an" if word[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def _pronoun_map(gender: Optional[str]) -> Dict[str, str]:
    base = {
        "subject": "they",
        "object": "them",
        "possessive": "their",
        "reflexive": "themselves",
    }
    if gender == "male":
        base.update({
            "subject": "he",
            "object": "him",
            "possessive": "his",
            "reflexive": "himself",
        })
    elif gender == "female":
        base.update({
            "subject": "she",
            "object": "her",
            "possessive": "her",
            "reflexive": "herself",
        })
    return {
        **base,
        "Subject_cap": base["subject"].capitalize(),
        "Object_cap": base["object"].capitalize(),
        "Possessive_cap": base["possessive"].capitalize(),
    }


def _physical_sentence(race, context: Dict[str, str]) -> str:
    profile = _profile_for_race(race)
    if not profile:
        return ""
    height_inches = profile_height_inches(profile)
    weight = profile_weight(profile)
    age = profile_age(profile)
    height_text = _format_height(height_inches)
    subject = context["subject"]
    return f"Standing {height_text} and weighing about {weight} pounds, {subject} appears to be roughly {age} years old."


def _profile_for_race(race) -> Optional[dict]:
    if not race:
        return None
    index = race.index.lower()
    if index in PHYSICAL_PROFILES:
        return PHYSICAL_PROFILES[index]
    parts = index.split('-')
    for part in (parts[0], parts[-1]):
        profile = PHYSICAL_PROFILES.get(part)
        if profile:
            return profile
    return PHYSICAL_PROFILES.get("human")


def profile_height_inches(profile: dict) -> int:
    base, dice = profile["height"]
    return base + _roll(dice)


def profile_weight(profile: dict) -> int:
    base, dice, multiplier = profile["weight"]
    return base + _roll(dice) * multiplier


def profile_age(profile: dict) -> int:
    minimum, maximum = profile["age"]
    return random.randint(minimum, maximum)


def _roll(dice: tuple) -> int:
    count, sides = dice
    total = 0
    for _ in range(count):
        total += random.randint(1, sides)
    return total


def _format_height(inches: int) -> str:
    feet = inches // 12
    remainder = inches % 12
    return f"{feet}'{remainder}\""
