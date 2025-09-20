# D&D 5e Character Builder Architecture

## Goals
- Desktop application with a modern Qt-based UI (PySide6)
- Comprehensive coverage of SRD 5e content via 5e-bits JSON dataset
- Character state that can be manipulated through the UI and exported to Foundry VTT (dnd5e system JSON)

## Layered Overview

| Layer | Responsibility |
| --- | --- |
| Data Access (`character_builder.data.loader`) | Load and normalize SRD JSON resources (races, classes, features, spells, equipment, etc.) |
| Domain (`character_builder.models`, `character_builder.rules`) | Immutable-ish dataclasses that represent SRD concepts, plus helper rules for derived statistics |
| Application State (`character_builder.state`) | Mutable character draft with reactive hooks for the UI |
| UI (`character_builder.ui`) | PySide6 widgets composing the character builder workflow |
| Export (`character_builder.export.foundry`) | Translate the character state into Foundry VTT dnd5e actor JSON |

## Data Flow
1. `DataRepository` loads JSON into typed registries keyed by index.
2. `CharacterTemplate` and `CharacterState` leverage registries to present options (dropdowns) and compute derived state.
3. UI binds to the state through signals (Qt signals/slots). Changes in UI propagate to state, which recomputes derived values and updates summaries.
4. Export layer maps `CharacterState` to Foundry `system` JSON structure, embedding selected features/items/spells.

## UI Flow
```
┌───────────┐    ┌──────────────┐    ┌───────────────┐
│ Selection │ -> │ Detail Panel │ -> │ Summary/Export │
└───────────┘    └──────────────┘    └───────────────┘
```
- **Selection Pane**: level slider, race/subrace dropdown, class/subclass dropdown, background dropdown, ability score editors, proficiencies, spells, equipment.
- **Detail Pane**: contextual info for highlighted choice (feature text, spell description, etc.).
- **Summary/Export Pane**: computed stats, hit points, saving throws, skill bonuses, and export controls.

## Foundry Export (dnd5e v11+)
- Output JSON with `name`, `type="character"`, `system` block containing ability scores, attributes, details, traits, resources.
- Items array includes class, race, features, equipment, and spells as item entities with their respective system data.
- Metadata includes flags: `core.sourceId` pointing to SRD index when available for traceability.

## Restart Log
Maintain `CODEx_LOG.md` with checkpoints and next steps so the session can resume seamlessly.
