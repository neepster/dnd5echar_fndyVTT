# Packaging the D&D 5e Character Builder with PyInstaller

## Prerequisites
- Python 3.12 (matches the version used during development)
- PyInstaller 6.5+ (`pip install pyinstaller`)
- The project dependencies installed (`pip install -r requirements.txt`)

## Windows build (PowerShell or cmd)
```powershell
python -m pip install --upgrade pyinstaller
pyinstaller packaging\dnd5echar.spec --clean --noconfirm
```
The bundled application will appear under `dist\dnd5e-character-builder\`. Distribute the entire folder so the embedded SRD data is available.

## macOS / Linux build
```bash
python3 -m pip install --upgrade pyinstaller
pyinstaller packaging/dnd5echar.spec --clean --noconfirm
```
The output will be written to `dist/dnd5e-character-builder/`. On macOS you can wrap the contents in an `.app` by passing `--windowed --name "D&D 5e Character Builder"` on the command line if you prefer an application bundle.

## Notes
- The spec file copies the vendored SRD dataset into the bundle and auto-discovers the `character_builder` package modules.
- At runtime the app looks for the SRD data inside the PyInstaller `_MEIPASS` location, so the dataset is available regardless of the bundle layout (single-folder or one-file).
- Use `--onefile` if you prefer a single executable, but keep in mind first launch takes longer because PyInstaller extracts the payload to a temp directory.
