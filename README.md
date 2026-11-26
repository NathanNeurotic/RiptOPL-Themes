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
tools/port_builtin_theme.py # regenerates THM/thm_incebtion + THM/thm_korium from RiptOPL history
tests/engine/               # runs the ports through RiptOPL's real parser, view resolver and tar reader
.github/workflows/pages.yml # validate on PR, build + deploy Pages on main
```

## Installing a theme

1. Download the theme's `thm_<name>.tar` from the [gallery](https://nathanneurotic.github.io/RiptOPL-Themes/).
2. **RiptOPL:** copy the `.tar` into `THM/` on your device (USB / MX4SIO / HDD / SMB / MMCE) **as is**. RiptOPL reads one-file themes straight from the archive.
   **Stock OPL or other forks:** extract it instead (`tar -xf thm_<name>.tar`, 7-Zip, or Windows' built-in tar) so you have `THM/thm_<name>/`.
3. In RiptOPL: **Settings → Theme Settings → Theme**, select it, then save settings.

## Make your own

Use the **[RiptOPL Theme Creator](https://nathanneurotic.github.io/RiptOPL/theme-creator.html)**: a browser editor with a live preview of every screen that exports a ready-to-use `thm_<Name>.tar`. Then submit it here (below).

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

## Ported built-in themes

`thm_incebtion` and `thm_korium` are disk-theme ports of RiptOPL's two former built-in editions (IncebtIon and Korium), with all four views: List, Coverflow, PSBBN Flow and Grid. They are **generated, not hand-edited**:

```bash
python3 tools/port_builtin_theme.py --riptopl /path/to/RiptOPL --theme incebtion   # or korium
tests/engine/run.sh /path/to/RiptOPL                                               # verify
```

See the porter's docstring for exactly what differs between an embedded and a disk theme and how each difference is handled.

## Credits

Each theme belongs to its author. Credits and licensing live in that theme's `theme.json` and/or a `README`/`LICENSE` inside its folder.
