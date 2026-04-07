![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Target](https://img.shields.io/badge/Target-GBA-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
[![Support me on Ko-fi](https://img.shields.io/badge/Support%20Me-Ko--fi-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/eightmouse)

# KiraPatch

> [!IMPORTANT]
> Current status: I am in the last stretch of Method 1 starter closure for the next release. Local testing is in a much better place now, and the current focus is locking the final starter path down cleanly before moving on.
>
> FireRed was the stubborn one for a while, but it is finally landing legal shiny starters again on the current local path, including the hardest current starter target. The remaining work is less about "can it happen?" and more about making sure the final path is clean and reliable enough to ship.
>
> The current public `2.0.0` build can still have rough edges depending on the game and encounter type. That can mean lag, freezes, or shinies that are not as clean or reliable as I want them to be yet.
>
> Right now I am focused on finishing the starter work at `1/64`, `1/128`, and `1/256` in a way I can fully stand behind before I move on to gifts, statics, wild encounters, and the rest. `1/32` or lower is still experimental for now.

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
- `1/64` is the current hardening target for the next stricter release
- `1/128` or `1/256` are the safer public choices while hardening continues
- `1/32` and lower are currently experimental and may freeze or fail legality checks

Legacy modes:
- `native` and `legacy` are the older threshold-style patch modes
- they are not the recommended choice if legality matters

## Are The Shinies Visual Or Not?
No. In `auto` or `canonical`, the shinies are real shinies, not visual-only shinies.

If the game shows the Pokemon as shiny, save editors like PKHeX should also see it as shiny.

## Are They Legal?
Under current standard PKHeX checks on supported vanilla ROMs, that is the point of canonical mode.

In `auto`, `canonical`, or `reroll`, KiraPatch aims to keep the generated Pokemon PKHeX-clean under current desktop checks by using canonical rerolls instead of a fake visual threshold patch. Current local hardening work has the `1/64` starter base path clean across all 5 supported games on a real `.sav` + reset-based runner; shiny-hit validation at `1/64` is still being finished before the next release. Wild, static, gift, and egg paths are being tightened separately.

That is not the same thing as proving the Pokemon are indistinguishable from untouched vanilla RNG history under deep trace analysis. KiraPatch is designed to avoid visual-only fake shinies and broken writes, while keeping results clean under current standard legality checks.

If legality matters, use:
- `auto`
- `canonical`
- `reroll`

Do not use:
- `native`
- `legacy`

## How Do I Patch The .rom?
### Standalone Windows EXE
Download `KiraPatch.exe` from the Releases section on the right.

The EXE is now the main user-facing launcher. It opens a compact GUI where you can:
- add one or more `.gba` or `.rom` files with the file picker
- patch in `auto` mode
- choose the shiny odds you want

Recommended settings:
- `odds=128` or `odds=256` for the current public build
- `odds=64` as the current hardening target for the next stricter release
- `odds=32` and lower only if you are explicitly testing experimental aggressive rates

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

Start with `auto` mode on a clean ROM. For the current public build, `1/128` or `1/256` are the safer choices while `1/64` is being finished for the next stricter release.

## License
Distributed under the MIT License. See `LICENSE` for more information.

