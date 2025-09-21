# D&D 5e Character Builder

A desktop character creation tool for the 5th Edition SRD. It ships with a full copy of the open-source 5e-bits SRD dataset and exports characters in Foundry VTT's dnd5e actor JSON format.

## Prerequisites
- Python 3.12+
- Virtual environment recommended: `python -m venv .venv && source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

All SRD data is already vendored at `data/5e-database/src/2014`.

## Running the app
```
python main.py
```

## Key Features
- Full SRD data coverage (classes, subclasses, races, subraces, backgrounds, feats, spells, equipment categories, etc.)
- Slick PySide6 desktop UI with:
  - Basics tab for level, race/subrace, class/subclass, background, alignment
  - One-click random character generator that honors any fields you've already chosen while filling in the rest with synergistic picks, including starter gear, magical weapon upgrades, race-aware names, and pocket change scaled to level
  - Clear button to wipe the sheet instantly when you want a completely fresh roll
  - Ability editor with automatic racial bonuses and manual ASI support
  - Skill/proficiency management with class/background/race choices and expertise toggles
  - Spell management grouped by level with known/prepared tracking
  - Summary dashboard with computed ability mods, saves, skills, spell slots, and feature list
- Foundry VTT export (`File > Export to Foundry VTT…`) producing dnd5e-compatible actor JSON including abilities, proficiencies, features, and spells.

## Data Sources
- SRD JSON sourced from [5e-bits/5e-database](https://github.com/5e-bits/5e-database) (CC-BY 4.0)

## Development Notes
- Core logic lives under `src/character_builder`
  - `data/` handles SRD loading and normalization
  - `state.py` exposes a Qt-friendly view-model
  - `ui/` contains PySide6 widgets
  - `export/foundry.py` writes Foundry actors
- Launch helper: `python -m character_builder.ui.main_window`

## Testing quick checks
- `PYTHONPATH=src python -m compileall src`
- Manual smoke test: launch the app, fill in selections, export to Foundry JSON, and import into Foundry VTT (dnd5e system >= v11)
