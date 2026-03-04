![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg) 
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Target](https://img.shields.io/badge/Target-GBA-orange)
![Stage](https://img.shields.io/badge/Stage-Archived-brown.svg)
![Support](https://img.shields.io/badge/Support-None-lightgrey.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
[![Support me on Ko-fi](https://img.shields.io/badge/Support%20Me-Ko--fi-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/eightmouse)


# Disclaimer
This project is for educational and archival purposes. 

# Gen 3 Shiny Odds CLI Patcher
It's a small script I made a while ago as practice.
Works with European and USA versions only, haven't checked JP at all, feel free to fork and add it!

Safe shiny-odds patcher for Pokemon Gen 3 GBA ROMs:
- FireRed
- LeafGreen
- Ruby
- Sapphire
- Emerald

## Safety model

- CRC32 ROM auto-detection (only known clean revisions are accepted)
- Strict byte validation at every patch offset before writing
- Never overwrites the input ROM (always writes a new output file)

If CRC32 is unknown, patching is refused.

## Usage

```bash
python shiny_patcher.py "Pokemon Emerald.gba" --odds 4096
```

Guided mode (recommended for beginners):
```bash
python shiny_patcher.py --guided
```

If no `input_rom` is provided, guided mode starts automatically:
```bash
python shiny_patcher.py
```

Arguments:
- `input_rom`: source `.gba` ROM path
- `--odds N`: desired shiny rate as `1 in N` (required)
- `--output PATH`: optional output ROM path
- `--overwrite-output`: allow replacing an existing output file
- `--guided`: interactive wizard, scans a folder for ROMs and guides patching
- `--folder PATH`: folder to scan in guided mode (default: current directory)

Default output naming:
- `<input_stem>.shiny_1inN.gba`

Example:
```bash
python shiny_patcher.py "Pokemon FireRed.gba" --odds 2048 --output "FireRed_1in2048.gba"
```

Guided scan of a specific folder:
```bash
python shiny_patcher.py --guided --folder "C:\ROMs\GBA"
```

## Notes on odds conversion

Gen 3 uses a threshold internally (base threshold is `8`, equivalent to `1/8192`).
This tool converts `1 in N` to the nearest threshold with:

- `threshold = round(65536 / N)`
- clamped to `1..255` (ROM instruction encoding limit at target offsets)

## Supported ROM CRC32 values

- `0xF0815EE7` - Pokemon Ruby Version (USA, Europe) Rev 0
- `0x61641576` - Pokemon Ruby Version (USA, Europe) Rev 1
- `0x554DEDC4` - Pokemon Sapphire Version (USA, Europe) Rev 0
- `0xBAFEDAE5` - Pokemon Sapphire Version (Europe) Rev 1
- `0xDD88761C` - Pokemon FireRed Version (USA) Rev 0
- `0x84EE4776` - Pokemon FireRed Version (USA, Europe) Rev 1
- `0xD69C96CC` - Pokemon LeafGreen Version (USA) Rev 0
- `0xDAFFECEC` - Pokemon LeafGreen Version (USA, Europe) Rev 1
- `0x1F1C08FB` - Pokemon Emerald Version (USA, Europe) Rev 0

## Verify syntax quickly

```bash
python --version
python shiny_patcher.py --help
```

<<<<<<< HEAD
## Drag-and-drop launcher (Windows)

Use [patch_drag_drop.bat](patch_drag_drop.bat) for simple usage:
- Drag one or more `.gba` ROM files onto `patch_drag_drop.bat`
- The launcher reads odds from [patcher_config.ini](patcher_config.ini)
- It calls `shiny_patcher.py` and creates patched ROM output files

Edit this line in `patcher_config.ini` to change odds:
```ini
odds=4096
```

Example values:
- `odds=8192` (vanilla)
- `odds=4096`
- `odds=2048`
=======
---

## License
Distributed under the MIT License. See `LICENSE` for more information.
>>>>>>> 7e40c940f534d4fc5881bd40314f738034d1f656
