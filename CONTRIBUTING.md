# Submitting a theme

> **New theme?** The easiest start is the [RiptOPL Theme Creator](https://nathanneurotic.github.io/RiptOPL/theme-creator.html). It exports a `thm_<Name>.tar`; extract it into `THM/` here for the PR (CI rebuilds the `.tar` for the gallery).

## 1. Folder

Add **one** folder per PR:

```
THM/thm_<your_theme_name>/
```

- Must start with `thm_`. OPL only loads folders with that prefix.
- Allowed characters: `A-Z a-z 0-9 . _ -` (no spaces in the folder name).
- Must not differ only by letter case from an existing theme (FAT32/exFAT are case-insensitive).
- File names inside: `A-Z a-z 0-9 space . _ ( ) + - #` (`#` is needed for badge files such as `ISO_#Format.png`). No symlinks.

## 2. Contents

| File | Required? | Purpose |
|---|---|---|
| `conf_theme.cfg` | Recommended | OPL layout/config. Without it, OPL uses the default layout with your images. |
| `preview.png` | Recommended | Gallery thumbnail, ideally a real-hardware or PCSX2 screenshot. Shown in the gallery, not packed into the download. |
| `theme.json` | Optional | Gallery metadata (see below). Not packed into the download. |
| everything else | — | Images, fonts, and so on, exactly as they should sit on the device. |

Keep the total size reasonable (CI warns above 8 MiB per theme or 2 MiB per file). Big assets load slowly on PS2 hardware and eat memory-card space.

## 3. `theme.json` (optional)

```json
{
  "name": "Midnight Crystal",
  "author": "YourName",
  "version": "1.0",
  "description": "Dark blue glass theme with animated-look icons.",
  "opl_version": "RiptOPL 1.x",
  "tags": ["dark", "minimal"],
  "preview": "preview.png",
  "homepage": "https://example.com",
  "license": "CC-BY-4.0"
}
```

Every key is optional, and unknown keys are ignored (CI warns about them).

## 4. Badges and file names

A disk theme never uses RiptOPL's embedded badges. An `AttributeImage` loads **`<value>_<attribute>.png`** from your folder, for example `ISO_#Format.png`, `Vmode_ntsc_Vmode.png` or `Rating_3_Rating.png` (see RiptOPL's `docs/THEME_ENGINE.md` section 6). Ship one for every value you want drawn.

Never ship two names that differ only by case (for example `app.png` and `APP.png`). FAT32 and exFAT, and RiptOPL's `.tar` reader, treat them as one file. CI rejects this.

## 5. Test it

- Load it on **real PS2 hardware** if you can, otherwise in PCSX2, and say which in the PR.
- Run `python3 tools/build_inventory.py --check` locally. CI runs the same check.

## 6. Open the PR

Fill in the PR checklist. Once it's merged, the gallery updates automatically.
