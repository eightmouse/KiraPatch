![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Target](https://img.shields.io/badge/Target-GBA-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

# KiraPatch

## Disclaimer
KiraPatch is for educational and archival use.

Use it only with ROMs you legally own and dump yourself. Patch clean ROMs only.

## What Is It?
KiraPatch is a patcher for Generation 3 Pokemon GBA games that raises shiny odds while keeping the game on its normal data-writing path.

Supported games:
- FireRed
- LeafGreen
- Ruby
- Sapphire
- Emerald

Supported clean USA/EU revisions are detected by CRC32 before patching. If the ROM is not a known clean match, patching is refused.

## Who Is It For And Why?
KiraPatch is for players who want higher shiny odds across normal gameplay without turning shinies into fake visual-only results.

It is meant for people who want things like:
- shiny starters
- shiny wild encounters
- shiny static or gift encounters
- no Bad Eggs from broken writes
- no PKHeX legality errors caused by a visual-only threshold hack

## How Does It Work?
The recommended modes are `auto`, `canonical`, and `reroll`.

In those modes, KiraPatch does not just change the shiny check threshold. Instead, it patches the Pokemon generation flow so the game keeps rerolling until it gets a real Gen 3 shiny result, then lets the game store that Pokemon through its normal path.

That means:
- it patches real shiny generation, not just visuals
- it keeps the normal `SetMonData` write path to avoid checksum corruption and Bad Eggs
- it validates the ROM before writing anything
- it always writes a new output ROM and does not overwrite the input ROM

Important note about high rates:
- `1/16` works, but it can cause noticeable pauses because canonical rerolls are expensive
- `1/128` or `1/256` are much smoother for normal play

Legacy modes:
- `native` and `legacy` are the older threshold-style patch modes
- they are not the recommended choice if legality matters

## Are The Shinies Visual Or Not?
No. In `auto` or `canonical`, the shinies are real shinies, not visual-only shinies.

If the game shows the Pokemon as shiny, save editors like PKHeX should also see it as shiny.

## Are They Legal?
Yes, that is the point of canonical mode.

In `auto`, `canonical`, or `reroll`, KiraPatch aims to keep the generated Pokemon legal by using canonical rerolls instead of a fake visual threshold patch. On supported ROMs, starters, wild encounters, and the tested static or gift paths are intended to remain PKHeX-legal.

If legality matters, use:
- `auto`
- `canonical`
- `reroll`

Do not use:
- `native`
- `legacy`

## How Do I Patch The .rom?
### Standalone Windows EXE
Download the prebuilt `KiraPatch.exe` from the Releases section on the right, or build it locally with `build_standalone.bat` if you want your own copy.

The EXE is now the main user-facing launcher. It opens a compact GUI where you can:
- drag and drop one or more `.gba` ROMs into the window
- add ROMs manually with the file picker
- choose the shiny odds you want
- patch in `auto` mode

Recommended settings:
- `odds=128` or `odds=256` for smoother gameplay
- `odds=16` if you want aggressive testing and do not mind freezes or pauses

Output naming from the EXE:
- `<input_stem>.shiny_1inN.gba`
- if that already exists, KiraPatch adds a version suffix automatically

### CLI
```bash
python shiny_patcher.py "Pokemon Emerald.gba" --odds 256 --mode auto
```

### Guided mode
```bash
python shiny_patcher.py --guided
```

If no ROM path is provided, guided mode starts automatically:
```bash
python shiny_patcher.py
```

### Main arguments
- `input_rom`: source `.gba` ROM path
- `--odds N`: desired shiny rate as `1 in N`
- `--mode {auto,canonical,reroll,native,legacy}`
- `--output PATH`: optional output ROM path
- `--overwrite-output`: allow replacing an existing output file
- `--guided`: interactive wizard
- `--folder PATH`: folder to scan in guided mode

### Supported clean ROM CRC32 values
- `0xF0815EE7` - Pokemon Ruby Version (USA, Europe) Rev 0
- `0x61641576` - Pokemon Ruby Version (USA, Europe) Rev 1
- `0xAEAC73E6` - Pokemon Ruby Version (USA, Europe) Rev 2
- `0x554DEDC4` - Pokemon Sapphire Version (USA, Europe) Rev 0
- `0xBAFEDAE5` - Pokemon Sapphire Version (Europe) Rev 1
- `0x9CC4410E` - Pokemon Sapphire Version (USA, Europe) Rev 2
- `0xDD88761C` - Pokemon FireRed Version (USA) Rev 0
- `0x84EE4776` - Pokemon FireRed Version (USA, Europe) Rev 1
- `0xD69C96CC` - Pokemon LeafGreen Version (USA) Rev 0
- `0xDAFFECEC` - Pokemon LeafGreen Version (USA, Europe) Rev 1
- `0x1F1C08FB` - Pokemon Emerald Version (USA, Europe) Rev 0

## End
KiraPatch is built around one goal: higher shiny odds in Gen 3 without fake shinies, checksum corruption, or PKHeX legality problems.

Start with `auto` mode on a clean ROM, pick a sane odds value like `1/128` or `1/256`, and patch a fresh copy.

## License
Distributed under the MIT License. See `LICENSE` for more information.
