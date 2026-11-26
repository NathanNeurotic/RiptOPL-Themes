#!/usr/bin/env python3
"""
Port a retired RiptOPL *built-in* theme (inceBtion or Korium) to an *external* disk theme.

The embedded and disk paths of the theme engine differ, so a built-in cfg cannot simply be
copied into THM/. This tool reproduces exactly what the edition build embedded
(tools/assets.py + src/gfx/textures.cpp at the pinned RiptOPL commit) and rewrites it into the
shape a disk theme needs:

  1. Textures     Every texture the edition embedded is written under the name the engine
                  probes in a theme folder (src/gfx/textures.cpp's name column), with the same
                  bytes the ELF carried, including the edition aliases (no_Rating -> Rating_0,
                  logo4..6 -> logo3..1, Korium's incebtion/ip -> background/background_info,
                  Korium's coverapp -> cover, its 2-4 dot BdmIndex -> Index_<p>, the
                  CUE/EXE/BIN stand-in badges).
  2. Badges       Disk themes never draw the embedded badges (themeelems.cpp, #213). An
                  AttributeImage loads <value>_<attribute>.png from the theme, so every badge the
                  cfg can show is written under that name as well.
  3. Views        The built-in loaded each view from its own cfg file. A disk theme carries them
                  all in one conf_theme.cfg: the List file is the base and each other view file
                  is prefixed (coverflow. / grid. / psbbn.) with <view>.inherit=0, so each view
                  is the edition's own file block for block.
  4. Globals      Keys only the base can carry (fonts) are hoisted and must agree across views;
                  keys a view may override (use_real_height, list_cfg_text, ...) are prefixed.
  5. Case         FAT32/exFAT (USB, MX4SIO) and the theme-tar reader match names case-insensitively, so app.png
                  (Apps device icon) and APP.png (APP media badge) cannot both exist. APP.png is not written;
                  the cfg's default=APP fallbacks point at APP_#Media.png, the same picture. This is the only
                  change made to the edition's blocks.
  6. Only what is read  A disk theme's folder is read for a fixed set of textures (thmLoad in src/gfx/themes.cpp:
                  loading frames, device and hint icons, BdmIndex dots, UDPFS, L1/R1/L3/R3, fav) plus whatever the
                  cfg names (default=/overlay=/overlay2=) and the badges. Boot logos and the techwritescode credit
                  always come from the ELF, and plain-named badges (Scan_480p.png) are never opened, so neither is
                  shipped: that is about 9 MB of pictures nothing would load.
  7. Colours      Built-ins take the Colours picker; a disk theme must set its own. The edition's
                  out-of-box palette (src/app/opl.cpp at the pinned commit) is written explicitly.

Usage
  python3 tools/port_builtin_theme.py --riptopl /path/to/RiptOPL --theme incebtion
  python3 tools/port_builtin_theme.py --riptopl /path/to/RiptOPL --theme korium

The RiptOPL checkout needs the pinned commit's objects (a blobless clone is enough). Output goes
to THM/thm_<theme>/ and is deterministic: same commit in, byte-identical theme out.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Last RiptOPL commit before the inceBtion/Korium built-ins were retired by 01f079f8 (#483).
PIN = "ae61fcc5fc8987d84b684349fcfb0bbe98c00c74"

# The edition's out-of-box palette (src/app/opl.cpp + include/opl.h at PIN). Same for both editions.
PALETTE = {
    "bg_color": "#0C3AA8",
    "text_color": "#FFFFFF",
    "sel_text_color": "#00AEFF",
    "ui_text_color": "#5868B4",
    "title_color": "#FFFFFF",
}

# Globals a view may override (thmLoad in src/gfx/themes.cpp reads them with thmViewGet*).
VIEW_GLOBALS = {"use_default", "use_real_height", "coverflow_cover_offset", "bg_color", "plasma_blend_color",
                "text_color", "ui_text_color", "title_color", "sel_text_color", "list_cfg_text", "hd_autofit"}

# Attribute values an AttributeImage can be handed (docs/THEME_ENGINE.md section 6). The value is
# also the embedded glyph's name, which is how the edition drew it.
ATTRIBUTE_VALUES = {
    "#System": ["PS1", "PS2"],
    "#Media": ["CD", "DVD", "APP"],
    "#Format": ["ISO", "ZSO", "VCD", "UL", "ELF", "HDL", "CUE", "EXE", "BIN"],
    "Vmode": ["Vmode_multi", "Vmode_ntsc", "Vmode_pal"],
    "Aspect": ["Aspect_s", "Aspect_w", "Aspect_w1", "Aspect_w2"],
    "Scan": ["Scan_240p", "Scan_240p1", "Scan_480i", "Scan_480p", "Scan_480p1", "Scan_480p2", "Scan_480p3",
             "Scan_480p4", "Scan_480p5", "Scan_576i", "Scan_576p", "Scan_720p", "Scan_1080i", "Scan_1080i2",
             "Scan_1080p"],
    "Players": ["Players_1", "Players_2", "Players_3", "Players_4"],
    "Rating": ["Rating_0", "Rating_1", "Rating_2", "Rating_3", "Rating_4", "Rating_5"],
}

THEMES = {
    "incebtion": {
        "title": "inceBtion",
        "author": "Ripto (NathanNeurotic) & Berion",
        "korium": False,
        "preview": "docs/assets/ui/incebtion/list.png",  # PCSX2 capture of the IncebtIon edition, Beta-4052
        "views": {  # view -> cfg path at PIN (list is the base)
            "list": "misc/conf_theme_OPL.cfg",
            "coverflow": "misc/theme_coverflow.cfg",
            "psbbn": "misc/theme_psbbn_flow.cfg",
            "grid": "misc/theme_grid.cfg",
        },
        "credits": [
            "inceBtion - by Ripto (NathanNeurotic) and Berion.",
            "RiptOPL's built-in theme (IncebtIon edition) before PSBBN List/Flow replaced it.",
            "PSBBN Flow view after CosmicScale's PSBBN Definitive Project, glide timing from dnunezx's LUNA.",
        ],
    },
    "korium": {
        "title": "Korium Komblete",
        "author": "KrahJohlito & Berion",
        "korium": True,
        "preview": "docs/assets/ui/list.png",  # PCSX2 capture of the Korium edition, Beta-4052
        "views": {
            "list": "<korium>/misc/conf_theme_OPL.cfg",
            "coverflow": "<korium>/misc/theme_coverflow.cfg",
            "psbbn": "misc/theme_psbbn_flow.cfg",
            "grid": "misc/theme_grid_korium.cfg",
        },
        "credits": [
            "Korium Komblete - by KrahJohlito and Berion.",
            "Ported to RiptOPL's built-in Korium edition, then back to a disk theme, by the RiptOPL project.",
            "CUE / EXE / BIN badges are RiptOPL stand-ins drawn from Korium's own badges.",
            "PSBBN Flow view after CosmicScale's PSBBN Definitive Project, glide timing from dnunezx's LUNA.",
        ],
    },
}

# Textures thmLoad reads from a DISK theme's folder (src/gfx/themes.cpp, current engine): LOAD0..LOAD7,
# BDM_ICON..START_ICON, INDEX2_0..INDEX4_3, UDPFS_ICON, L3_ICON..FAV_MARK, L1_ICON, R1_ICON.
ENGINE_READS = set("""load0 load1 load2 load3 load4 load5 load6 load7 usb usb_bd ilk_bd m4s_bd hdd_bd mmce hdd eth udp_bd app
Index_0 Index_1 Index_2 Index_3 Index_4 left right cross triangle circle square select start Index2_0 Index2_1 Index3_0
Index3_1 Index3_2 Index4_0 Index4_1 Index4_2 Index4_3 udp_fs L3 R3 fav fav_mark L1 R1""".split())

HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*):\s*$")
KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.#]*)=(.*)$")
KEY_MAX = 47  # CONFIG_KEY_NAME_LEN 48 incl. NUL


class Git:
    def __init__(self, repo: Path, commit: str) -> None:
        self.repo, self.commit = repo, commit

    def read(self, path: str) -> bytes:
        return subprocess.run(["git", "-C", str(self.repo), "show", f"{self.commit}:{path}"],
                              check=True, capture_output=True).stdout

    def exists(self, path: str) -> bool:
        return subprocess.run(["git", "-C", str(self.repo), "cat-file", "-e", f"{self.commit}:{path}"],
                              capture_output=True).returncode == 0


def die(msg: str) -> None:
    sys.exit(f"ERROR: {msg}")


# ------------------------------------------------------------------ textures

def texture_table(git: Git, korium: bool) -> list[tuple[str, str | None]]:
    """(name, png symbol stem or None) for src/gfx/textures.cpp's internalDefault[] at PIN."""
    src = git.read("src/gfx/textures.cpp").decode()
    body = src[src.index("internalDefault"):]
    body = body[:body.index("};")]
    out, stack = [], []  # stack of "active" flags for #ifdef BUILTIN_KORIUM / #ifndef
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("#ifdef BUILTIN_KORIUM"):
            stack.append(korium)
        elif line.startswith("#ifndef BUILTIN_KORIUM"):
            stack.append(not korium)
        elif line.startswith("#if"):
            stack.append(None)  # unrelated guard (e.g. RA): leave it out
        elif line.startswith("#else") and stack:
            stack[-1] = None if stack[-1] is None else not stack[-1]
        elif line.startswith("#endif") and stack:
            stack.pop()
        else:
            m = re.match(r'\{[A-Z_0-9]+,\s*"([^"]+)",\s*(?:&(\w+)_png|NULL)\}', line)
            if m and all(s is True for s in stack):
                out.append((m.group(1), m.group(2)))
    return out


class AssetSource:
    """Resolves a png symbol stem to the bytes the edition embedded (tools/assets.py at PIN)."""

    def __init__(self, git: Git, korium: bool) -> None:
        self.git, self.korium, self.files = git, korium, {}
        if korium:
            manifest = json.loads(git.read("third_party/korium/UPSTREAM.json"))
            archive = git.read("third_party/korium/assets.zip")
            if hashlib.sha256(archive).hexdigest() != manifest["archive_sha256"]:
                die("Korium asset archive digest mismatch")
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                for name, digest in manifest["files"].items():
                    data = z.read(name)
                    if hashlib.sha256(data).hexdigest() != digest:
                        die(f"Korium asset digest mismatch: {name}")
                    self.files[name] = data

    def png(self, stem: str) -> bytes:
        if not self.korium:
            return self.git.read(f"gfx/{stem}.png")
        name = {"incebtion": "background", "ip": "background_info"}.get(stem, stem)
        if f"gfx/{name}.png" in self.files:
            return self.files[f"gfx/{name}.png"]
        if name.startswith("Index") and "_" in name and name[5] != "_":
            alt = f"gfx/Index_{name.split('_')[1]}.png"  # five-dot BdmIndex only: dot p of n is Index_p
            if alt in self.files:
                return self.files[alt]
        if self.git.exists(f"third_party/korium/stand-in/gfx/{name}.png"):
            return self.git.read(f"third_party/korium/stand-in/gfx/{name}.png")
        return self.git.read(f"gfx/{stem}.png")

    def cfg(self, path: str) -> bytes:
        if path.startswith("<korium>/"):
            return self.files[path[len("<korium>/"):]]
        return self.git.read(path)


# ------------------------------------------------------------------ cfg

def parse_cfg(text: str, where: str) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]:
    """Split a legacy theme cfg into (globals, [(section, body lines)]). Comments and blanks drop."""
    globals_, sections, cur = [], [], None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        h = HEADER_RE.match(s)
        if h:
            cur = (h.group(1), [])
            sections.append(cur)
            continue
        k = KEY_RE.match(s)
        if not k:
            die(f"{where}:{n}: unparseable line {s!r}")
        if cur is None:
            globals_.append((k.group(1), k.group(2)))
        else:
            cur[1].append(f"{k.group(1)}={k.group(2)}")
    return globals_, sections


def korium_list(src: AssetSource) -> str:
    """Korium's List cfg with RiptOPL's List Title/Description overlay, merged like assets.py did."""
    overlay = src.git.read("misc/korium_list_desc.cfg")
    split = overlay.index(b"\nmain") + 1
    return (overlay[:split] + src.cfg("<korium>/misc/conf_theme_OPL.cfg") + overlay[split:]).decode()


def build_cfg(spec: dict, src: AssetSource) -> tuple[str, set[str]]:
    base_globals: dict[str, str] = {"use_default": "1", **PALETTE}
    view_globals: list[tuple[str, str]] = []
    blocks: list[tuple[str, list[str]]] = []
    referenced: set[str] = set()

    for view, path in spec["views"].items():
        text = korium_list(src) if (spec["korium"] and view == "list") else src.cfg(path).decode()
        g, secs = parse_cfg(text, f"{view}:{path}")
        prefix = "" if view == "list" else f"{view}."
        # Fonts are theme-wide (thmLoadFonts), so a view whose font slot differs from another view's gets
        # its own free slot, and its blocks are renumbered to it. A slot the view never draws with is dropped.
        slots = {}
        for key, val in g:
            m = re.match(r"^font(\d+)(_size|_weight)?$", key)
            if m:
                slots.setdefault(int(m.group(1)), {})[key[len(f"font{m.group(1)}"):] or ""] = val
        remap = {}
        for slot, props in slots.items():
            mine = {f"font{slot}{suf}": v for suf, v in props.items()}
            if all(base_globals.get(k, v) == v for k, v in mine.items()):
                base_globals.update(mine)
                continue
            if not any(f"font={slot}" in line for _, body in secs for line in body):
                print(f"note: {view} sets font{slot} differently but never draws with it - dropped")
                continue
            free = next(n for n in range(1, 16) if not any(k.startswith(f"font{n}") and
                        (len(k) == len(f"font{n}") or not k[len(f"font{n}")].isdigit()) for k in base_globals))
            base_globals.update({f"font{free}{suf}": v for suf, v in props.items()})
            remap[slot] = free
            print(f"note: {view} font{slot} -> font{free}")
        if remap:
            secs = [(n, [f"font={remap[int(l[5:])]}" if l.startswith("font=") and int(l[5:]) in remap else l
                         for l in body]) for n, body in secs]
        for key, val in g:
            if re.match(r"^font\d+(_size|_weight)?$", key):
                continue
            if key in VIEW_GLOBALS:
                view_globals.append((prefix + key, val))
            elif key in base_globals and base_globals[key] != val:
                die(f"{view}: theme-wide global {key}={val} conflicts with {base_globals[key]}")
            else:
                base_globals[key] = val
        if prefix:
            view_globals.append((f"{view}.inherit", "0"))
            # A view the edition did not hide its list text in shows it, as its own file did.
            if not any(k == "list_cfg_text" for k, _ in g):
                view_globals.append((f"{view}.list_cfg_text", "1"))
        secs = [(n, ["default=APP_#Media" if l == "default=APP" else l for l in body]) for n, body in secs]
        for name, body in secs:
            for line in body:
                k, v = line.split("=", 1)
                if k in ("default", "overlay", "overlay2"):
                    referenced.add(v.strip())
                if len(f"{prefix}{name}_{k}") > KEY_MAX:
                    die(f"key too long ({len(prefix + name + '_' + k)} > {KEY_MAX}) {prefix}{name}_{k}")
            blocks.append((prefix + name, body))

    out = [
        f"# {spec['title']} - external port of the RiptOPL built-in theme",
        f"# Generated by tools/port_builtin_theme.py from RiptOPL {PIN[:12]}",
        "# Do not hand-edit - change the porter and regenerate",
        "",
        "views=list,coverflow,psbbn,grid",
        "default_view=list",
    ]
    out += [f"{k}={v}" for k, v in base_globals.items()]
    out += [f"{k}={v}" for k, v in view_globals]
    for name, body in blocks:
        out.append("")
        out.append(f"{name}:")
        out += [f"\t{line}" for line in body]
    return "\n".join(out) + "\n", referenced


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--riptopl", required=True, type=Path, help="RiptOPL git checkout containing the pinned commit")
    ap.add_argument("--theme", required=True, choices=sorted(THEMES))
    ap.add_argument("--dump-sources", type=Path, help="also write the edition's own view cfgs here (for tests)")
    ap.add_argument("--commit", default=PIN, help=f"RiptOPL commit to port from (default {PIN[:12]})")
    args = ap.parse_args()

    spec = THEMES[args.theme]
    git = Git(args.riptopl, args.commit)
    src = AssetSource(git, spec["korium"])
    if args.dump_sources:
        args.dump_sources.mkdir(parents=True, exist_ok=True)
        for view, path in spec["views"].items():
            text = korium_list(src) if (spec["korium"] and view == "list") else src.cfg(path).decode()
            (args.dump_sources / f"{view}.cfg").write_text(text, encoding="utf-8")
        return 0
    files: dict[str, bytes] = {}

    table = texture_table(git, spec["korium"])
    by_name = {n: s for n, s in table}
    for name, stem in table:
        if stem is None:
            continue  # theme-supplied only (settings_bg, Device_*, ...) or retired in this edition
        files[f"{name}.png"] = src.png(stem)

    cfg, referenced = build_cfg(spec, src)
    files["conf_theme.cfg"] = cfg.encode()

    # Disk-theme badges: <value>_<attribute>.png for every value an AttributeImage can show.
    used_attrs = set(re.findall(r"^\tattribute=(\S+)", cfg, re.M))
    for attr in sorted(used_attrs & set(ATTRIBUTE_VALUES)):
        for value in ATTRIBUTE_VALUES[attr]:
            stem = by_name.get(value)
            if stem:  # a value the edition had no glyph for drew nothing; keep it that way
                files[f"{value}_{attr}.png"] = src.png(stem)

    # Korium's own extras the cfg names directly (not in the texture table under these names).
    for extra in sorted(referenced):
        if f"{extra}.png" not in files:
            if extra in by_name and by_name[extra] is None:
                continue
            stem = by_name.get(extra, extra)
            files[f"{extra}.png"] = src.png(stem)

    # Keep only what the engine can open (see 6. above).
    badge_names = {f"{v}_{a}.png" for a in used_attrs for v in ATTRIBUTE_VALUES.get(a, [])}
    wanted = {f"{n}.png" for n in ENGINE_READS | referenced} | badge_names | {"conf_theme.cfg"}
    for name in [n for n in files if n not in wanted]:
        del files[name]

    # Names that differ only by case collide on FAT32/exFAT and in the theme-tar index (see 5. above).
    files.pop("APP.png", None)
    folded = {}
    for name in files:
        if name.lower() in folded:
            die(f"case-insensitive collision: {folded[name.lower()]} / {name}")
        folded[name.lower()] = name

    missing = sorted(r for r in referenced if f"{r}.png" not in files)
    if missing:
        die(f"cfg references assets that do not exist: {', '.join(missing)}")

    files["preview.png"] = git.read(spec["preview"])
    files["CREDITS.txt"] = ("\n".join(spec["credits"]) + "\n").encode()
    files["theme.json"] = (json.dumps({
        "name": spec["title"] + " (external)",
        "author": spec["author"],
        "version": f"riptopl-{args.commit[:7]}",
        "description": f"Disk-theme port of RiptOPL's former built-in {spec['title']} edition, with List, "
                       f"Coverflow, PSBBN Flow and Grid views.",
        "opl_version": "RiptOPL (Beta-4000+)",
        "tags": ["port", "multi-view", args.theme],
        "preview": "preview.png",
        "license": "AFL-3.0",
    }, indent=2) + "\n").encode()

    dest = ROOT / "THM" / f"thm_{args.theme}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in sorted(files):
        (dest / name).write_bytes(files[name])
    print(f"Wrote THM/thm_{args.theme}/: {len(files)} files, {sum(map(len, files.values())) / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
