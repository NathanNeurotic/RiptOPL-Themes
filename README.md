# RiptOPL Themes

Download, submit, and share themes for **RiptOPL** / Open PS2 Loader.

**Gallery:** https://nathanneurotic.github.io/RiptOPL-Themes/

---

## Repository layout

The repo root mirrors the device layout OPL expects, so any theme folder can be copied straight across:

```
THM/
├── thm_<submission_name>/
│   ├── conf_theme.cfg      # OPL theme config (recommended)
│   ├── preview.png         # gallery thumbnail (recommended, repo-only)
│   ├── theme.json          # gallery metadata (optional, repo-only)
│   └── ...                 # backgrounds, icons, fonts, etc.
└── thm_<another_theme>/
site/                       # GitHub Pages front-end (index.html)
tools/build_inventory.py    # scans THM/, validates, builds themes.json + .tar archives
.github/workflows/pages.yml # validate on PR, build + deploy Pages on main
```

## Installing a theme

1. Download the theme's `.tar` from the [gallery](https://nathanneurotic.github.io/RiptOPL-Themes/).
2. Extract it (Windows 10+: right-click → Extract All, or `tar -xf thm_<name>.tar`; 7-Zip and macOS work too) so you end up with `THM/thm_<name>/` on your OPL device (USB / MX4SIO / HDD / SMB share / memory card).
3. In RiptOPL: **Settings → Display Settings → Theme**, select it, then save settings.

## Submitting a theme

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. Short version: open a PR that adds exactly one folder, `THM/thm_<your_theme>/`. CI validates it, and once merged, the gallery rebuilds itself.

## How the inventory works

GitHub Pages can't list directories, so on every push to `main` the workflow:

1. Runs `tools/build_inventory.py`, which walks `THM/thm_*/` and validates names, files, and metadata.
2. Writes `themes.json` (files, sizes, SHA-256 hashes, preview, metadata).
3. Builds one **deterministic** `.tar` per theme (USTAR format, fixed mtime/owner/permissions, so the same input always gives byte-identical output).
4. Deploys `_site/` to Pages.

If `themes.json` is ever missing, the page falls back to a live listing from the GitHub API.

Run it locally:

```bash
python3 tools/build_inventory.py --check     # validate only
python3 tools/build_inventory.py             # build into _site/
python3 -m http.server -d _site 8000         # preview at http://localhost:8000
```

## Credits

Each theme belongs to its author. Credits and licensing live in that theme's `theme.json` and/or a `README`/`LICENSE` inside its folder.
