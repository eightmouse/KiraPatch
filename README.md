![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Target](https://img.shields.io/badge/Target-GBA-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

# Disclaimer
This project is for educational and archival purposes.

# Gen 3 Shiny Odds CLI Patcher
KiraPatch is a CLI utility for modifying shiny encounter rates in Generation 3 Pokemon ROMs.

Supported games:
- FireRed
- LeafGreen
- Ruby
- Sapphire
- Emerald

Works with supported USA/EU clean revisions listed below.

## Safety model
- CRC32 ROM auto-detection (only known clean revisions are accepted)
- Strict byte validation at every patch offset before writing
- Never overwrites the input ROM (always writes a new output file)

If CRC32 is unknown, patching is refused.

## Usage
```bash
python shiny_patcher.py "Pokemon Emerald.gba" --odds 4096
```

Guided mode:
```bash
python shiny_patcher.py --guided
```

If no `input_rom` is provided, guided mode starts automatically:
```bash
python shiny_patcher.py
```

### Arguments
- `input_rom`: source `.gba` ROM path
- `--odds N`: desired shiny rate as `1 in N` (required)
- `--mode {auto,canonical,reroll,native,legacy}`: patch strategy (default: `auto`)
- `--output PATH`: optional output ROM path
- `--overwrite-output`: allow replacing an existing output file
- `--guided`: interactive wizard, scans a folder for ROMs and guides patching
- `--folder PATH`: folder to scan in guided mode (default: current directory)

Default output naming:
- `<input_stem>.shiny_1inN.gba`

## Mode behavior
- `auto`: recommended. Uses canonical PID rerolls for boosted shiny odds.
- `canonical`: canonical PID rerolls (same behavior as `auto`).
- `reroll`: alias of `canonical` for backwards compatibility.
- `native`: old threshold patch mode.
  - Max representable threshold is `255`, so best native rate is about `1/257`.
  - Requests above that rate (for example `1/256`, `1/16`) return an error.
- `legacy`: alias of `native`.

Canonical reroll behavior:
- Patches the Gen 3 PID generation routine (not visual-only shiny checks).
- Uses the game's own `SetMonData` write path to avoid checksum corruption / Bad Eggs.
- Resulting shinies are canonical and PKHeX-valid when shiny in-game.
- Effective odds are approximate to the nearest reroll-attempt count.

Patch summary reports:
- requested mode
- applied mode
- effective shiny bits
- effective odds
- canonical reroll attempts (when canonical mode is applied)

## Examples
```bash
python shiny_patcher.py "Pokemon FireRed.gba" --odds 2048 --mode auto
python shiny_patcher.py "Pokemon FireRed.gba" --odds 256 --mode auto
python shiny_patcher.py "Pokemon Emerald.gba" --odds 16 --mode canonical
```

## Drag-and-drop launcher (Windows)
Use [KiraPatch.bat](KiraPatch.bat):
- Drag one or more `.gba` ROM files onto `KiraPatch.bat`
- The launcher reads settings from [patcher_config.ini](patcher_config.ini)
- It calls `shiny_patcher.py` with `--odds` and `--mode`

Config keys:
```ini
odds=256
mode=auto
```

Valid `mode` values:
- `auto`
- `canonical`
- `reroll`
- `native`
- `legacy`

Output naming from launcher:
- `<input_stem>.shiny_1inN_mode.gba`

## Launcher icon
Windows `.bat` files do not store custom icons directly.
To use your logo icon, launch via [KiraPatch.lnk](KiraPatch.lnk), which points to `KiraPatch.bat` and uses [logo.ico](logo.ico).

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

## License
Distributed under the MIT License. See `LICENSE` for more information.
