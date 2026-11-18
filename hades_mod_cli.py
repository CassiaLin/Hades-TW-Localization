"""Hades 1 — Taiwan Traditional Chinese Localization Toolkit CLI (Dual-Mode)."""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = ROOT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from game_detector import detect_hades_dir
from m1_extract import extract_game_texts, resolve_clean_content_dir
from m2_prepare import import_translated_dir, prepare_batches
from m4_qa_linter import run_qa
from m5_build import build_mod
from translation_pack import (
    TranslationPackError,
    export_translation_pack,
    verify_translation_pack,
)


DEFAULT_PACK_DIR = ROOT_DIR / "translations" / "hades1"
DEFAULT_WORK_DIR = ROOT_DIR / "workspace" / "hades1"
DEFAULT_DIST_DIR = ROOT_DIR / "dist" / "Hades_TW_Mod"
DEFAULT_GLOSSARY_DIR = ROOT_DIR / "glossary"
DEFAULT_OTF_PATH = ROOT_DIR / "assets" / "fonts" / "NotoSansTC-Medium.otf"
CONFIG_PATH = ROOT_DIR / "config" / "game_paths.json"


class BackupIntegrityError(RuntimeError):
    """Raised when backup manifest or hashes fail validation."""


class ExternalModificationError(RuntimeError):
    """Raised when Steam/external edits are detected in live game files."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_copy(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.tmp.{os.getpid()}")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    return sha256_file(dst)


def _target_relative_files(content_dir: Path) -> List[str]:
    rels = ["Content/Game/Text/Languages.sjson"]
    for p in sorted((content_dir / "Game" / "Text" / "zh-CN").glob("*.sjson")):
        rels.append(f"Content/Game/Text/zh-CN/{p.name}")
    for p in sorted((content_dir / "Subtitles" / "zh-CN").glob("*.csv")):
        rels.append(f"Content/Subtitles/zh-CN/{p.name}")
    for fn in ("Default.xnb", "zh-CN.xnb", "Lang.xnb", "Fonts.remap"):
        if (content_dir / "Win" / "Fonts" / "zh-CN" / fn).is_file():
            rels.append(f"Content/Win/Fonts/zh-CN/{fn}")
    for lang in ("en", "ja", "ko", "pl", "ru"):
        fp = content_dir / "Win" / "Fonts" / lang / "zh-CN.xnb"
        if fp.is_file():
            rels.append(f"Content/Win/Fonts/{lang}/zh-CN.xnb")
    return rels


def _backup_dir(game_dir: Path) -> Path:
    return game_dir / "_Backup_TW_Mod"


def _load_manifest(game_dir: Path) -> Dict[str, Any] | None:
    mp = _backup_dir(game_dir) / "manifest.json"
    if not mp.is_file():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise BackupIntegrityError(f"Failed to read backup manifest {mp}: {e}") from e


def ensure_backup_and_check_external(game_dir: Path, force: bool = False) -> Dict[str, Any]:
    """Create initial backup from clean game files or validate existing backup vs live files."""
    bak_dir = _backup_dir(game_dir)
    manifest = _load_manifest(game_dir)
    live_content = game_dir / "Content"

    if manifest is None:
        files_rec: Dict[str, Dict[str, str]] = {}
        for rel in _target_relative_files(live_content):
            src = game_dir / rel
            dst = bak_dir / rel
            orig_hash = sha256_file(src)
            copied_hash = atomic_copy(src, dst)
            assert orig_hash == copied_hash
            files_rec[rel] = {"original_sha256": orig_hash, "installed_sha256": orig_hash}
        manifest = {
            "version": "1.0",
            "state": "UNINSTALLED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "files": files_rec,
        }
        (bak_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    state = manifest.get("state")
    if state not in {"UNINSTALLED", "COMMITTED", "PREPARED", "APPLYING", "UNINSTALLING"}:
        raise BackupIntegrityError(f"Corrupt or unexpected backup state: {state}")

    # Verify backup files themselves aren't corrupted and check live game files for Steam updates
    for rel, rec in manifest.get("files", {}).items():
        bak_file = bak_dir / rel
        if not bak_file.is_file():
            raise BackupIntegrityError(f"Missing backup file: {bak_file}")
        if sha256_file(bak_file) != rec["original_sha256"]:
            raise BackupIntegrityError(f"Backup hash mismatch: {bak_file}")

        live_file = game_dir / rel
        if not live_file.is_file():
            if not force:
                raise ExternalModificationError(f"Live game file missing: {live_file}")
            continue
        live_hash = sha256_file(live_file)
        expected = rec["original_sha256"] if state == "UNINSTALLED" else rec.get("installed_sha256")
        if not force and live_hash != expected and live_hash != rec["original_sha256"]:
            raise ExternalModificationError(
                f"External modification detected (possibly Steam update) at {live_file}. "
                "Verify integrity in Steam or run uninstall first; do not blindly overwrite."
            )
    return manifest


def install_from_dist(game_dir: Path, dist_dir: Path, force: bool = False) -> Dict[str, Any]:
    manifest = ensure_backup_and_check_external(game_dir, force=force)
    bak_dir = _backup_dir(game_dir)
    built_content = dist_dir / "Content"

    manifest["state"] = "APPLYING"
    (bak_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    installed_count = 0
    for fp in sorted(built_content.rglob("*")):
        if not fp.is_file():
            continue
        rel = "Content/" + fp.relative_to(built_content).as_posix()
        dst = game_dir / rel
        new_hash = atomic_copy(fp, dst)
        if rel in manifest["files"]:
            manifest["files"][rel]["installed_sha256"] = new_hash
        installed_count += 1

    manifest["state"] = "COMMITTED"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    (bak_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"installed_files": installed_count, "state": manifest["state"]}


def uninstall_mod(game_dir: Path, force: bool = False) -> Dict[str, Any]:
    manifest = _load_manifest(game_dir)
    if manifest is None:
        raise BackupIntegrityError(f"No backup found in {_backup_dir(game_dir)}; cannot uninstall.")
    bak_dir = _backup_dir(game_dir)
    files_rec = manifest.get("files", {})

    # Verify backup files first
    for rel, rec in files_rec.items():
        bf = bak_dir / rel
        if not bf.is_file() or sha256_file(bf) != rec["original_sha256"]:
            raise BackupIntegrityError(f"Backup integrity check failed for {bf}")

    if not force:
        state = manifest.get("state")
        for rel, rec in files_rec.items():
            lf = game_dir / rel
            if not lf.is_file():
                continue
            lh = sha256_file(lf)
            if state == "COMMITTED" and lh not in (rec.get("installed_sha256"), rec["original_sha256"]):
                raise ExternalModificationError(
                    f"External modification (e.g. Steam update) detected at {lf}; aborting uninstall."
                )

    manifest["state"] = "UNINSTALLING"
    (bak_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    restored = 0
    for rel, rec in files_rec.items():
        atomic_copy(bak_dir / rel, game_dir / rel)
        rec["installed_sha256"] = rec["original_sha256"]
        restored += 1

    manifest["state"] = "UNINSTALLED"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    (bak_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"restored_files": restored, "state": manifest["state"]}


def cmd_player_status(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    print(f"[偵測] 遊戲目錄: {game_dir if game_dir else '未偵測到（請使用 --game-dir 指定）'}")
    try:
        pm = verify_translation_pack(Path(args.pack_dir))
        print(
            f"[譯文包] 驗證通過: SJSON {pm['sjson_entry_count']} 筆 ({pm['sjson_file_count']} 檔), "
            f"字幕 {pm['subtitle_entry_count']} 筆 ({pm['subtitle_file_count']} 檔)"
        )
    except TranslationPackError as e:
        print(f"[譯文包] 驗證失敗: {e}")
        return 1

    if game_dir:
        m = _load_manifest(game_dir)
        state = m.get("state", "NONE") if m else "NOT_INSTALLED"
        print(f"[安裝狀態] {state}")
    return 0


def cmd_player_install(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    if not game_dir:
        print("[錯誤] 找不到 Hades 遊戲安裝目錄，請使用 --game-dir 指定。")
        return 1
    pack_dir = Path(args.pack_dir)
    dist_dir = Path(args.dist_dir)
    otf_path = Path(args.otf_path)

    print("[1/4] 驗證繁體中文譯文包...")
    verify_translation_pack(pack_dir)

    print("[2/4] 驗證遊戲原檔與備份安全...")
    ensure_backup_and_check_external(game_dir, force=args.force)

    print("[3/4] 合成繁體中文文本與重建免缺字字型檔 (.xnb)...")
    bm = build_mod(game_dir, pack_dir, dist_dir, otf_path)
    print(
        f"      已替換 SJSON {bm['sjson_applied']} 欄、字幕 {bm['csv_applied']} 筆；"
        f"Default.xnb 補字 +{bm['default_xnb_added']} (共 {bm['default_xnb_total']} 字)"
    )

    print("[4/4] 執行安裝前品質驗證 (QA) 與交易式寫入...")
    qa = run_qa(
        dist_dir / "Content",
        resolve_clean_content_dir(game_dir),
        game_dir / "Content" / "Game" / "Text" / "en",
    )
    if not qa["passed"]:
        print("[錯誤] QA 未通過，中止安裝：")
        for err in qa["errors"][:10]:
            print("  -", err)
        return 1

    res = install_from_dist(game_dir, dist_dir, force=args.force)
    print(f"[完成] 成功安裝 {res['installed_files']} 個檔案 (狀態: {res['state']})，可啟動遊戲測試！")
    return 0


def cmd_player_uninstall(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    if not game_dir:
        print("[錯誤] 找不到 Hades 遊戲安裝目錄。")
        return 1
    res = uninstall_mod(game_dir, force=args.force)
    print(f"[完成] 已還原 {res['restored_files']} 個原版檔案 (狀態: {res['state']})。")
    return 0


def cmd_dev_extract(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    if not game_dir:
        print("[錯誤] 找不到 Hades 遊戲安裝目錄。")
        return 1
    stats = extract_game_texts(game_dir, Path(args.work_dir))
    print(f"[M1] 提取完成 -> {args.work_dir}: {stats}")
    return 0


def cmd_dev_prepare(args: argparse.Namespace) -> int:
    stats = prepare_batches(Path(args.work_dir), DEFAULT_GLOSSARY_DIR, batch_size=args.batch_size)
    print(f"[M2] 批次檔與 AI 提示生成完成: {stats}")
    return 0


def cmd_dev_import(args: argparse.Namespace) -> int:
    stats = import_translated_dir(Path(args.from_dir), Path(args.pack_dir))
    print(f"[M3] 匯入完成: {stats}")
    return 0


def cmd_dev_qa(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    if not game_dir:
        print("[錯誤] 找不到 Hades 遊戲安裝目錄。")
        return 1
    target_content = Path(args.dist_dir) / "Content"
    if not target_content.is_dir():
        target_content = game_dir / "Content"
    qa = run_qa(
        target_content,
        resolve_clean_content_dir(game_dir),
        game_dir / "Content" / "Game" / "Text" / "en",
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return 0 if qa["passed"] else 1


def cmd_dev_build(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    if not game_dir:
        print("[錯誤] 找不到 Hades 遊戲安裝目錄。")
        return 1
    bm = build_mod(game_dir, Path(args.pack_dir), Path(args.dist_dir), Path(args.otf_path))
    print(json.dumps({k: v for k, v in bm.items() if k != "files"}, ensure_ascii=False, indent=2))
    return 0


def cmd_dev_export(args: argparse.Namespace) -> int:
    game_dir = detect_hades_dir(args.game_dir, CONFIG_PATH)
    built_content = Path(args.from_content) if args.from_content else Path(args.dist_dir) / "Content"
    orig_content = resolve_clean_content_dir(game_dir) if game_dir else built_content
    manifest = export_translation_pack(built_content, orig_content, Path(args.pack_dir))
    verify_translation_pack(Path(args.pack_dir))
    print("[匯出] Translation Pack 驗證通過:", manifest["sjson_entry_count"], "SJSON +", manifest["subtitle_entry_count"], "Subtitles")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Hades 1 Taiwan Traditional Chinese Localization CLI")
    p.add_argument("--game-dir", default=None, help="Path to Steam Hades root directory")
    p.add_argument("--pack-dir", default=str(DEFAULT_PACK_DIR), help="Translation pack directory")
    p.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR), help="Developer extraction workspace")
    p.add_argument("--dist-dir", default=str(DEFAULT_DIST_DIR), help="Built mod output directory")
    p.add_argument("--otf-path", default=str(DEFAULT_OTF_PATH), help="Path to NotoSansTC-Medium.otf")

    sub = p.add_subparsers(dest="mode", required=True)

    # Player mode
    sp_player = sub.add_parser("player", help="Player mode (status/install/update-pack/uninstall)")
    p_sub = sp_player.add_subparsers(dest="action", required=True)
    p_sub.add_parser("status", help="Inspect game detection, backup status, and pack integrity")
    p_inst = p_sub.add_parser("install", help="Build and install zh-TW localization")
    p_inst.add_argument("--force", action="store_true", help="Override external modification guard")
    p_upd = p_sub.add_parser("update-pack", help="Rebuild and update installed files from pack")
    p_upd.add_argument("--force", action="store_true", help="Override external modification guard")
    p_un = p_sub.add_parser("uninstall", help="Restore original Simplified Chinese game files")
    p_un.add_argument("--force", action="store_true", help="Override external modification guard")

    # Developer mode
    sp_dev = sub.add_parser("dev", help="Developer/translator mode (extract/prepare/import/qa/build/install/export)")
    d_sub = sp_dev.add_subparsers(dest="action", required=True)
    d_sub.add_parser("extract", help="M1: Extract .sjson and .csv files into AI-friendly JSON")
    d_prep = d_sub.add_parser("prepare", help="M2: Split batches and inject glossary prompts")
    d_prep.add_argument("--batch-size", type=int, default=200)
    d_imp = d_sub.add_parser("import", help="M3: Import translated JSON/JSONL outputs into translation pack")
    d_imp.add_argument("--from-dir", required=True, help="Directory with translated JSON/JSONL outputs")
    d_sub.add_parser("qa", help="M4: Run structural, tag, punctuation, and font glyph checks")
    d_sub.add_parser("build", help="M5: Rebuild SJSON/CSV and XNB fonts into dist/")
    d_inst = d_sub.add_parser("install", help="Install built mod into Steam Hades directory")
    d_inst.add_argument("--force", action="store_true")
    d_exp = d_sub.add_parser("export", help="Export pure zh-TW pack to translations/hades1/")
    d_exp.add_argument("--from-content", default=None, help="Source Content directory to export from")

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "player":
        if args.action == "status":
            return cmd_player_status(args)
        if args.action in ("install", "update-pack"):
            return cmd_player_install(args)
        if args.action == "uninstall":
            return cmd_player_uninstall(args)

    if args.mode == "dev":
        if args.action == "extract":
            return cmd_dev_extract(args)
        if args.action == "prepare":
            return cmd_dev_prepare(args)
        if args.action == "import":
            return cmd_dev_import(args)
        if args.action == "qa":
            return cmd_dev_qa(args)
        if args.action == "build":
            return cmd_dev_build(args)
        if args.action == "install":
            return cmd_player_install(args)
        if args.action == "export":
            return cmd_dev_export(args)

    return 2


if __name__ == "__main__":
    sys.exit(main())
