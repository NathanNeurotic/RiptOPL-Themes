#!/usr/bin/env python3
"""
RiptOPL Themes — inventory builder.

Scans  THM/thm_<name>/  in the repository root and produces a static site:

  _site/
    index.html            (copied from site/)
    themes.json           (inventory manifest consumed by index.html)
    THM/...               (raw theme files, for previews + per-file links)
    dl/thm_<name>.zip     (one download per theme, zip root = thm_<name>/)

Design goals
  * Deterministic: sorted traversal, fixed zip timestamps/permissions, stable JSON.
    Same input tree -> byte-identical themes.json and zips.
  * Fail loud on structural problems (bad folder names, empty themes, path
    traps), warn on soft problems (no conf_theme.cfg, no preview, big files).
  * Zero third-party dependencies (stdlib only) so CI never breaks on pip.

Usage
  python3 tools/build_inventory.py                # build into _site/
  python3 tools/build_inventory.py --check        # validate only, no output
  python3 tools/build_inventory.py --out public   # custom output dir
  python3 tools/build_inventory.py --strict       # treat warnings as errors
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THM_DIR = ROOT / "THM"
SITE_SRC = ROOT / "site"

THEME_DIR_RE = re.compile(r"^thm_[A-Za-z0-9][A-Za-z0-9._-]*$")
# Filenames that are safe on FAT32/exFAT and in URLs. OPL itself is fine with
# more, but users copy these to USB sticks and memory cards — keep it boring.
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()+-]*$")

PREVIEW_CANDIDATES = (
    "preview.png", "preview.jpg", "preview.jpeg", "preview.gif", "preview.webp",
    "screenshot.png", "screenshot.jpg", "screenshot.jpeg",
    "background.png", "background.jpg", "background.jpeg",
    "bg.png", "bg.jpg", "bg.jpeg",
)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
META_FILES = ("theme.json",)          # optional, repo-only metadata
CONF_FILE = "conf_theme.cfg"          # OPL's theme config
IGNORED = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}

WARN_FILE_BYTES = 2 * 1024 * 1024     # 2 MiB single file
WARN_THEME_BYTES = 8 * 1024 * 1024    # 8 MiB whole theme (memory cards are small)

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)     # earliest DOS time -> reproducible zips


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def emit(self) -> None:
        gh = os.environ.get("GITHUB_ACTIONS") == "true"
        for w in self.warnings:
            print(f"::warning::{w}" if gh else f"WARNING: {w}")
        for e in self.errors:
            print(f"::error::{e}" if gh else f"ERROR: {e}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_conf(path: Path) -> dict[str, str]:
    """Best-effort parse of OPL conf_theme.cfg (key=value lines)."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";", "//")) or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and k not in out:
            out[k] = v
    return out


def load_meta(theme: Path, rep: Report) -> dict:
    meta_path = theme / "theme.json"
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        rep.error(f"{theme.name}/theme.json is not valid UTF-8 JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        rep.error(f"{theme.name}/theme.json must be a JSON object")
        return {}
    allowed = {"name", "author", "version", "description", "opl_version",
               "tags", "preview", "homepage", "license"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        rep.warn(f"{theme.name}/theme.json has unknown keys (ignored): {', '.join(unknown)}")
    clean = {k: data[k] for k in sorted(allowed) if k in data}
    if "tags" in clean and not (isinstance(clean["tags"], list)
                                and all(isinstance(t, str) for t in clean["tags"])):
        rep.error(f"{theme.name}/theme.json 'tags' must be a list of strings")
        clean.pop("tags")
    for key in ("name", "author", "version", "description", "opl_version",
                "preview", "homepage", "license"):
        if key in clean and not isinstance(clean[key], str):
            rep.error(f"{theme.name}/theme.json '{key}' must be a string")
            clean.pop(key)
    return clean


def walk_files(theme: Path, rep: Report) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(theme, followlinks=False):
        dirnames.sort()
        d = Path(dirpath)
        for dn in list(dirnames):
            if (d / dn).is_symlink():
                rep.error(f"{(d / dn).relative_to(THM_DIR)}: symlinked directories are not allowed")
                dirnames.remove(dn)
        for fn in sorted(filenames):
            p = d / fn
            if fn in IGNORED:
                continue
            if p.is_symlink():
                rep.error(f"{p.relative_to(THM_DIR)}: symlinks are not allowed")
                continue
            files.append(p)
    return files


def pick_preview(theme: Path, files: list[Path], meta: dict, rep: Report) -> str | None:
    rel = {f.relative_to(theme).as_posix(): f for f in files}
    lower = {k.lower(): k for k in rel}
    if meta.get("preview"):
        want = meta["preview"]
        if want in rel and Path(want).suffix.lower() in IMAGE_EXT:
            return want
        rep.error(f"{theme.name}/theme.json 'preview' points to missing/non-image file: {want}")
    for cand in PREVIEW_CANDIDATES:
        if cand in lower:
            return lower[cand]
    images = sorted(k for k in rel if Path(k).suffix.lower() in IMAGE_EXT)
    return images[0] if images else None


def build_theme(theme: Path, rep: Report) -> dict | None:
    name = theme.name
    if not THEME_DIR_RE.match(name):
        rep.error(f"THM/{name}: folder must be named thm_<name> using A-Z a-z 0-9 . _ - "
                  f"(OPL only loads folders starting with 'thm_')")
        return None

    files = walk_files(theme, rep)
    if not files:
        rep.error(f"THM/{name}: theme folder is empty")
        return None

    for f in files:
        for part in f.relative_to(theme).parts:
            if not SAFE_NAME_RE.match(part):
                rep.error(f"THM/{name}/{f.relative_to(theme).as_posix()}: "
                          f"unsafe file/folder name '{part}' (use A-Z a-z 0-9 space . _ ( ) + -)")
                break

    meta = load_meta(theme, rep)
    conf_path = theme / CONF_FILE
    conf = parse_conf(conf_path) if conf_path.is_file() else {}
    if not conf_path.is_file():
        rep.warn(f"THM/{name}: no {CONF_FILE} (OPL will use default layout for this theme)")

    entries = []
    total = 0
    for f in files:
        size = f.stat().st_size
        total += size
        relp = f.relative_to(theme).as_posix()
        if size > WARN_FILE_BYTES:
            rep.warn(f"THM/{name}/{relp}: {size/1048576:.1f} MiB — large files load slowly on PS2")
        entries.append({"path": relp, "size": size, "sha256": sha256(f)})
    if total > WARN_THEME_BYTES:
        rep.warn(f"THM/{name}: theme totals {total/1048576:.1f} MiB — consider compressing assets")

    preview = pick_preview(theme, files, meta, rep)
    if preview is None:
        rep.warn(f"THM/{name}: no preview image (add preview.png for a nicer gallery card)")

    display = meta.get("name") or name[4:].replace("_", " ").replace("-", " ").strip() or name
    return {
        "id": name,
        "name": display,
        "author": meta.get("author", ""),
        "version": meta.get("version", ""),
        "description": meta.get("description", ""),
        "opl_version": meta.get("opl_version", ""),
        "tags": meta.get("tags", []),
        "homepage": meta.get("homepage", ""),
        "license": meta.get("license", ""),
        "has_conf": conf_path.is_file(),
        "conf_keys": len(conf),
        "preview": f"THM/{name}/{preview}" if preview else None,
        "file_count": len(entries),
        "total_size": total,
        "download": f"dl/{name}.zip",
        "files": entries,
        "_paths": files,  # stripped before writing JSON
    }


def write_zip(theme_dir: Path, files: list[Path], dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            arc = f"{theme_dir.name}/{f.relative_to(theme_dir).as_posix()}"
            zi = zipfile.ZipInfo(arc, date_time=ZIP_EPOCH)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o644 & 0xFFFF) << 16
            zi.create_system = 3  # unix, so attrs are honoured consistently
            zf.writestr(zi, f.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return dest.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="_site", help="output directory (default: _site)")
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    rep = Report()
    if not THM_DIR.is_dir():
        rep.error("THM/ directory is missing at repository root")
        rep.emit()
        return 1

    themes: list[dict] = []
    for child in sorted(THM_DIR.iterdir(), key=lambda p: p.name.lower()):
        if child.name in IGNORED or child.name.startswith(".") or child.name.lower() == "readme.md":
            continue
        if child.is_symlink():
            rep.error(f"THM/{child.name}: symlinks are not allowed")
            continue
        if not child.is_dir():
            rep.error(f"THM/{child.name}: loose file in THM/ — themes must live in THM/thm_<name>/")
            continue
        t = build_theme(child, rep)
        if t:
            themes.append(t)

    lowered: dict[str, str] = {}
    for t in themes:
        key = t["id"].lower()
        if key in lowered:
            rep.error(f"THM/{t['id']} collides with THM/{lowered[key]} on case-insensitive "
                      f"filesystems (FAT32/exFAT)")
        lowered[key] = t["id"]

    if args.strict and rep.warnings:
        rep.errors.extend(f"(strict) {w}" for w in rep.warnings)
        rep.warnings = []

    rep.emit()
    print(f"Found {len(themes)} theme(s); {len(rep.warnings)} warning(s); {len(rep.errors)} error(s).")
    if rep.errors:
        return 1
    if args.check:
        return 0

    out = (ROOT / args.out).resolve()
    if out == ROOT or ROOT not in out.parents:
        print(f"ERROR: refusing to write outside the repo or into the repo root: {out}")
        return 1
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for item in sorted(SITE_SRC.iterdir()):
        dst = out / item.name
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)

    for t in themes:
        src = THM_DIR / t["id"]
        for f in t["_paths"]:
            dst = out / "THM" / t["id"] / f.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
        t["download_size"] = write_zip(src, t.pop("_paths"), out / t["download"])

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    manifest = {
        "schema": 1,
        "repository": repo,
        "commit": os.environ.get("GITHUB_SHA", ""),
        "theme_count": len(themes),
        "themes": themes,
    }
    (out / "themes.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}/ ({len(themes)} theme(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
