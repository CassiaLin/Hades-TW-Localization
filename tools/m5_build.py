"""M5 Builder: Apply pure zh-TW translation pack onto original game files and rebuild XNB fonts."""

import csv
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from m1_extract import resolve_clean_content_dir
from sjson_core import apply_field_map
import xnb_font


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_mod(
    game_dir: Path,
    pack_dir: Path,
    dist_dir: Path,
    otf_path: Path,
) -> Dict[str, Any]:
    """Build complete Hades_TW_Mod Content tree in dist_dir from original game files + translation pack."""
    if not otf_path.is_file():
        raise FileNotFoundError(f"Bundled font not found: {otf_path}")

    ref_content = resolve_clean_content_dir(game_dir)
    out_content = dist_dir / "Content"
    if out_content.exists():
        shutil.rmtree(out_content)
    out_content.mkdir(parents=True, exist_ok=True)

    chars = set()

    # 1. Build Languages.sjson
    lang_overrides = json.loads((pack_dir / "languages_zh_tw.json").read_text(encoding="utf-8"))
    orig_lang_txt = (ref_content / "Game" / "Text" / "Languages.sjson").read_text(encoding="utf-8")
    new_lang_txt = orig_lang_txt.replace('"简体中文"', f'"{lang_overrides["zh-CN"]}"')
    new_lang_txt = re.sub(
        r'(Id\s*=\s*"SettingsMenuScreen_Language"\s+DisplayName\s*=\s*)"语言"',
        rf'\1"{lang_overrides["SettingsMenuScreen_Language"]}"',
        new_lang_txt,
        count=1,
    )
    dst_lang = out_content / "Game" / "Text" / "Languages.sjson"
    dst_lang.parent.mkdir(parents=True, exist_ok=True)
    dst_lang.write_text(new_lang_txt, encoding="utf-8", newline="")
    chars.update(c for c in new_lang_txt if ord(c) >= 0x20)

    # 2. Load SJSON translations grouped by filename -> {(id, field): zh}
    by_sjson_file: Dict[str, Dict[tuple, str]] = {}
    for line in (pack_dir / "sjson_zh_tw.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        by_sjson_file.setdefault(obj["file"], {})[(obj["id"], obj["field"])] = obj["zh"]

    ref_sjson_dir = ref_content / "Game" / "Text" / "zh-CN"
    dst_sjson_dir = out_content / "Game" / "Text" / "zh-CN"
    sjson_applied_count = 0
    for ref_p in sorted(ref_sjson_dir.glob("*.sjson")):
        fmap = by_sjson_file.get(ref_p.name, {})
        dst_p = dst_sjson_dir / ref_p.name
        sjson_applied_count += apply_field_map(ref_p, dst_p, fmap)
        chars.update(c for c in dst_p.read_text(encoding="utf-8") if ord(c) >= 0x20)

    # 3. Load Subtitle translations grouped by (file, row_id) -> zh
    sub_map: Dict[tuple, str] = {}
    for line in (pack_dir / "subtitles_zh_tw.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        sub_map[(obj["file"], obj["row_id"])] = obj["zh"]

    ref_sub_dir = ref_content / "Subtitles" / "zh-CN"
    dst_sub_dir = out_content / "Subtitles" / "zh-CN"
    dst_sub_dir.mkdir(parents=True, exist_ok=True)
    csv_applied_count = 0
    for ref_p in sorted(ref_sub_dir.glob("*.csv")):
        with ref_p.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        out_rows = [rows[0]]
        for r in rows[1:]:
            if len(r) > 7 and r[3].strip() and (ref_p.name, r[3]) in sub_map:
                r = list(r)
                r[7] = sub_map[(ref_p.name, r[3])]
                csv_applied_count += 1
            if len(r) > 7:
                chars.update(c for c in r[7] if ord(c) >= 0x20)
            out_rows.append(r)
        with (dst_sub_dir / ref_p.name).open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerows(out_rows)

    # 4. Build Default.xnb and zh-CN.xnb using bundled NotoSansTC-Medium.otf
    ref_font_dir = ref_content / "Win" / "Fonts" / "zh-CN"
    dst_font_dir = out_content / "Win" / "Fonts" / "zh-CN"
    dst_font_dir.mkdir(parents=True, exist_ok=True)

    added_def, total_def = xnb_font.render_missing_chars(
        src_xnb=str(ref_font_dir / "Default.xnb"),
        dst_xnb=str(dst_font_dir / "Default.xnb"),
        otf_path=str(otf_path),
        required_chars=chars,
        font_size=27,
        baseline_y=29,
        em_box=26,
    )

    added_zh, total_zh = xnb_font.render_missing_chars(
        src_xnb=str(ref_font_dir / "zh-CN.xnb"),
        dst_xnb=str(dst_font_dir / "zh-CN.xnb"),
        otf_path=str(otf_path),
        required_chars=set("語言繁體中文"),
        font_size=43,
        baseline_y=48,
        em_box=42,
    )

    for extra_fn in ("Lang.xnb", "Fonts.remap"):
        if (ref_font_dir / extra_fn).is_file():
            shutil.copy2(ref_font_dir / extra_fn, dst_font_dir / extra_fn)

    # Copy menu zh-CN.xnb to all other language folders so language menu shows 語言/繁體中文 everywhere
    for lang in ("en", "ja", "ko", "pl", "ru"):
        dst_lang_font_dir = out_content / "Win" / "Fonts" / lang
        dst_lang_font_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst_font_dir / "zh-CN.xnb", dst_lang_font_dir / "zh-CN.xnb")

    # 5. Record build_manifest.json + helper batch scripts
    built_files = {}
    for fp in sorted(out_content.rglob("*")):
        if fp.is_file():
            rel = fp.relative_to(dist_dir).as_posix()
            built_files[rel] = _sha256(fp)

    build_manifest = {
        "version": "1.0",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "sjson_applied": sjson_applied_count,
        "csv_applied": csv_applied_count,
        "unique_chars": len(chars),
        "default_xnb_added": added_def,
        "default_xnb_total": total_def,
        "zh_cn_xnb_added": added_zh,
        "zh_cn_xnb_total": total_zh,
        "files": built_files,
    }
    (dist_dir / "build_manifest.json").write_text(
        json.dumps(build_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dist_dir / "install_mod.bat").write_text(
        "@echo off\nchcp 65001 >nul\necho 請使用專案根目錄的 Install_TW_Mod.bat 或執行 python hades_mod_cli.py player install 進行交易式備份安裝。\npause\n",
        encoding="utf-8",
    )
    (dist_dir / "uninstall_mod.bat").write_text(
        "@echo off\nchcp 65001 >nul\necho 請使用專案根目錄的 Install_TW_Mod.bat 或執行 python hades_mod_cli.py player uninstall 還原原版檔案。\npause\n",
        encoding="utf-8",
    )
    return build_manifest
