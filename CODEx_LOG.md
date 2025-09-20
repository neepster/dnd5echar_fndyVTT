# Codex Session Log

## Status @ 2025-09-20T16:08:26-07:00
- PySide6 desktop application scaffolded (`main.py`) with modular architecture under `src/character_builder/`
- SRD dataset downloaded to `data/5e-database/src/2014`
- Data normalization pipeline (`character_builder.data`) ready
- View-model (`state.py`) with reactive signals, randomization locks, and a partial random-character generator (respecting user selections, adding ability scores, gear, level-scaled currency, and full resets)
- Qt UI (`ui/main_window.py`) implements the full workflow (basics, abilities, skills, spells, summary/export) with Random + Clear controls and summary sections for gear/finances
- Foundry export (`export/foundry.py`) outputs actors in the v11-style dnd5e schema, now including currency plus weapon/armor/gear items mapped from the SRD
- Requirements + README authored

## Next Steps
1. Manual QA: run `python main.py`, press Clear, ensure all dropdowns reset, then Random Character to verify locks + gear/currency populate sensibly
2. Foundry validation: export a generated JSON, import into a Foundry dnd5e world, and confirm weapons/armor arrive as typed items and coin totals match
3. Expand equipment export (e.g., populate attack activities, templates, and pack contents) if deeper fidelity is desired
4. Extend tests (e.g., unit tests for `rules.update_derived_stats`, export helpers, and random generation heuristics) once behaviour stabilizes

## Notes
- Activate the virtualenv before launching: `source .venv/bin/activate`
- Dataset updates: replace files under `data/5e-database` and re-run if Wizards publishes new SRD versions
