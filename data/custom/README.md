# Custom Data Files

You can override the random generator with your own names and hometowns by editing the CSV files in this directory.

## names.csv
- **Columns**: `race`, `gender`, `name`
- `race` accepts any race index (e.g., `human`, `half-elf`, `dragonborn`). Use `any` as a wildcard.
- `gender` accepts `male`, `female`, or `any`.
- `name` should contain the full name exactly as you want it to appear.
- The app first looks for an exact race+gender match, then race+`any`, then `any`+gender, and finally `any`/`any`.

Example:
```
race,gender,name
human,male,Callum Drake
human,female,Serena Vale
any,any,Arin Starfall
```

## hometowns.csv
- **Columns**: `race`, `place`
- `race` accepts any race index (use `any` for a fallback bucket).
- `place` is the hometown text that will be referenced in biographies.

Example:
```
race,place
elf,Silverglade
half-orc,Grimscar Hold
any,Dragon's Rest
```

## Workflow
1. Edit the CSVs with your preferred spreadsheet or text editor (keep headers intact).
2. Leave files empty or remove them if you want the default generator to take over.
3. Changes are picked up immediately—no restart or rebuild required.

Tip: You can add as many entries as you like. The generator selects randomly within the best matching bucket.
