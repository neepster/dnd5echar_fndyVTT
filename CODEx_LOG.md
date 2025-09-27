# Codex Session Log

## Status @ 2025-09-20T16:57:29-07:00
- PySide6 desktop application scaffolded (`main.py`) with modular architecture under `src/character_builder/`
- SRD dataset downloaded to `data/5e-database/src/2014`
- Data normalization pipeline (`character_builder.data`) ready
- View-model (`state.py`) with reactive signals, randomization locks, and a rich random-character generator (respects user selections, adds ability scores, race-aware names, gender, starter gear, level-scaled currency, and now auto-magical weapons)
- Qt UI (`ui/main_window.py`) implements the full workflow (basics, abilities, skills, spells, summary/export) with Random + Clear controls, gender picker, and summary sections for gear/finances
- NPC statblock export (`export/statblock.py`) generates 5e-formatted text blocks that summarize abilities, features, weapons, spellcasting, class details, and append descriptive bios for the 5e Statblock Importer (with quick clipboard copy support)
- Narrative generator (`flavor.py`) crafts short biographies, physical descriptors, and hooks whenever the randomizer assembles a new NPC
- Dark-themed UI refresh with header banner, iconography, and polished controls
- Requirements + README authored

## Next Steps
1. Manual QA: run `python main.py`, use Clear + Random to verify locked selections persist, gender/name generation looks right, and high-level characters receive the expected +X weapon
2. Foundry validation: export a generated JSON, import into a Foundry dnd5e world, and confirm magical weapons arrive with attack/damage bonuses while other gear shows up as loot
3. Expand equipment export (e.g., attack activities, pack contents) if deeper fidelity is desired
4. Extend tests (e.g., unit tests for `rules.update_derived_stats`, export helpers, and random generation heuristics) once behaviour stabilizes

## Notes
- Activate the virtualenv before launching: `source .venv/bin/activate`
- Dataset updates: replace files under `data/5e-database` and re-run if Wizards publishes new SRD versions
