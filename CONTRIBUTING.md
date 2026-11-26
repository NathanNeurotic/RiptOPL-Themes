# Submitting a theme

## 1. Folder

Add **one** folder per PR:

```
THM/thm_<your_theme_name>/
```

- Must start with `thm_`. OPL only loads folders with that prefix.
- Allowed characters: `A-Z a-z 0-9 . _ -` (no spaces in the folder name).
- Must not differ only by letter case from an existing theme (FAT32/exFAT are case-insensitive).
- File names inside: `A-Z a-z 0-9 space . _ ( ) + -`. No symlinks.

## 2. Contents

| File | Required? | Purpose |
|---|---|---|
| `conf_theme.cfg` | Recommended | OPL layout/config. Without it, OPL uses the default layout with your images. |
| `preview.png` | Recommended | Gallery thumbnail, ideally a real-hardware or PCSX2 screenshot at 640×448 or 4:3. |
| `theme.json` | Optional | Gallery metadata (see below). |
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

## 4. Test it

- Load it on **real PS2 hardware** if you can, otherwise in PCSX2, and say which in the PR.
- Run `python3 tools/build_inventory.py --check` locally. CI runs the same check.

## 5. Open the PR

Fill in the PR checklist. Once it's merged, the gallery updates automatically.
