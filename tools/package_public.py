"""
Public Distribution Packager & Deep Content/Schema Auditor for Hades-TW-Localization.
Builds a clean, self-contained public release directory using an explicit allowlist
via a temporary staging directory, auditing file extensions, filenames, and schemas.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "tools"))

from translation_pack import verify_translation_pack


ALLOWLIST_ROOT_FILES = [
    "hades_mod_cli.py",
    "Install_TW_Mod.bat",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "requirements.txt",
    ".gitattributes",
]

ALLOWLIST_DIRS = [
    "tools",
    "translations",
    "glossary",
    "docs",
    "tests",
    ".github",
    "assets",
]

PUBLIC_GITIGNORE_CONTENT = """# Python
__pycache__/
*.py[cod]
*$py.class
*.log
.pytest_cache/

# Local player/developer workspaces, configs, backups, and build outputs
workspace/
config/
dist/
work/
extracted/
backup/
output/
scratch/
_Backup_TW_Mod/

# Copyrighted game binaries & text assets
*.exe
*.xnb
*.sjson
*.csv
*.pkg
*.bank
*.bak

# Credentials & local environment
.env
.env.*
*.key
*.pem
"""

FORBIDDEN_EXTENSIONS = {".exe", ".xnb", ".sjson", ".csv", ".bank", ".pkg", ".dll"}
FORBIDDEN_FILENAMES = {"game_paths.json", "extraction_stats.json"}


class PublicAuditError(RuntimeError):
    """Raised when a public release directory contains excluded or unsafe content."""


def _validate_safe_out_dir(out_dir: Path, source_root: Path, overwrite: bool = False) -> Path:
    out_res = out_dir.resolve()
    src_res = source_root.resolve()
    if out_res == out_res.parent:
        raise PublicAuditError(f"Refusing filesystem root as output path: {out_res}")
    if out_res == src_res or src_res.is_relative_to(out_res) or out_res.is_relative_to(src_res):
        raise PublicAuditError(f"Refusing unsafe output path relative to source_root: {out_res}")
    if out_res.exists():
        if not out_res.is_dir():
            raise PublicAuditError(f"Output path exists and is not a directory: {out_res}")
        if any(out_res.iterdir()) and not overwrite:
            raise PublicAuditError(f"Output directory is not empty: {out_res}. Pass --overwrite.")
    return out_res


def audit_public_tree(pub_dir: Path) -> Dict[str, Any]:
    """Audit staged public tree for forbidden extensions/filenames and valid translation pack."""
    file_count = 0
    for fp in pub_dir.rglob("*"):
        if fp.is_symlink():
            raise PublicAuditError(f"Symlink forbidden in public release: {fp}")
        if fp.is_dir():
            continue
        file_count += 1
        if fp.suffix.lower() in FORBIDDEN_EXTENSIONS:
            raise PublicAuditError(f"Forbidden binary/game extension {fp.suffix}: {fp}")
        if fp.name in FORBIDDEN_FILENAMES:
            raise PublicAuditError(f"Forbidden internal filename {fp.name}: {fp}")

    pack_manifest = verify_translation_pack(pub_dir / "translations" / "hades1")
    return {
        "file_count": file_count,
        "sjson_entries": pack_manifest["sjson_entry_count"],
        "subtitle_entries": pack_manifest["subtitle_entry_count"],
    }


def build_public_release(
    out_dir: Path,
    source_root: Path = ROOT_DIR,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Copy ONLY allowlisted public files into staging directory, audit, and publish to out_dir."""
    out_res = _validate_safe_out_dir(out_dir, source_root, overwrite=overwrite)

    with tempfile.TemporaryDirectory(prefix="hades_pub_stage_") as tmp:
        stage_dir = Path(tmp) / "public_stage"
        stage_dir.mkdir(parents=True, exist_ok=True)
        copied: List[str] = []

        for fname in ALLOWLIST_ROOT_FILES:
            src = source_root / fname
            if not src.is_file():
                raise PublicAuditError(f"Missing required root file: {src}")
            shutil.copy2(src, stage_dir / fname)
            copied.append(fname)

        (stage_dir / ".gitignore").write_text(PUBLIC_GITIGNORE_CONTENT, encoding="utf-8")
        copied.append(".gitignore")

        for dname in ALLOWLIST_DIRS:
            src_d = source_root / dname
            if not src_d.is_dir():
                raise PublicAuditError(f"Missing required directory: {src_d}")
            shutil.copytree(
                src_d,
                stage_dir / dname,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )
            copied.append(dname + "/")

        audit_res = audit_public_tree(stage_dir)

        if out_res.exists():
            shutil.rmtree(out_res)
        shutil.copytree(stage_dir, out_res)

    return {
        "out_dir": str(out_res),
        "copied": copied,
        "audit": audit_res,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build & audit clean public Hades-TW-Localization directory")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    res = build_public_release(Path(args.out_dir), overwrite=args.overwrite)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
