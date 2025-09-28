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
  - One-click random character generator that honors any fields you've already chosen while filling in the rest with synergistic picks, including starter gear, magical weapon/armor upgrades, race-aware names, and pocket change scaled to level
  - Automatic biography generator that scripts quick backstories, physical descriptors, and hooks for newly created NPCs
  - Clear button to wipe the sheet instantly when you want a completely fresh roll
  - Ability editor with automatic racial bonuses and manual ASI support
  - Skill/proficiency management with class/background/race choices and expertise toggles
  - Spell management grouped by level with known/prepared tracking
  - Summary dashboard with computed ability mods, saves, skills, spell slots, and feature list
- NPC statblock export (`File > Export NPC Statblock…`) that saves (or instantly copies) a ready-to-import text block (including class, trait, and biography summaries) compatible with the Foundry VTT "5e Statblock Importer" module.
- Sleek, dark-themed Qt interface with iconography and polished typography for faster workflows
- Optional custom name and hometown CSVs let you tailor race/gender-specific identities without touching code

## Data Sources
- SRD JSON sourced from [5e-bits/5e-database](https://github.com/5e-bits/5e-database) (CC-BY 4.0)

## Development Notes
- Core logic lives under `src/character_builder`
  - `data/` handles SRD loading and normalization
  - `state.py` exposes a Qt-friendly view-model
  - `ui/` contains PySide6 widgets
- `export/` houses exporters (e.g., `statblock.py` for NPC statblocks)
- Launch helper: `python -m character_builder.ui.main_window`

## Packaging
- Install dependencies: `pip install -r requirements.txt`
- Install PyInstaller: `pip install pyinstaller`
- Build (Windows PowerShell/cmd): `pyinstaller packaging\dnd5echar.spec --clean --noconfirm`
- Build (macOS/Linux): `pyinstaller packaging/dnd5echar.spec --clean --noconfirm`
- Bundles land in `dist/dnd5e-character-builder/`; ship the entire folder for the SRD dataset.

## Custom Data Files
- `data/custom/names.csv` — format: `race,gender,name`. Provide full names for specific races and genders (use `any` for wildcards). Example entries are included; edit or replace as desired.
- `data/custom/hometowns.csv` — format: `race,place`. List optional hometowns for each race; `any` acts as a fallback bucket.
- When these files exist and contain data, the randomizer and biography generator draw from them; otherwise the built-in name tables and origin list are used.
- Detailed instructions live in `data/custom/README.md`.

## Testing quick checks
- `PYTHONPATH=src python -m compileall src`
- Manual smoke test: launch the app, fill in selections, export an NPC statblock, and import it with the 5e Statblock Importer module inside Foundry VTT
