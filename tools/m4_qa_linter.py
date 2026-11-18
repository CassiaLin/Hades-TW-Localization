"""M4 QA Linter: Validate SJSON tags/structure, CSV parity, punctuation, and XNB font glyph coverage."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from sjson_core import validate_pair
import xnb_font


def run_qa(
    content_dir: Path,
    ref_content_dir: Path,
    en_sjson_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate built Content directory against clean reference Content directory."""
    errors: List[str] = []
    chars = set()

    # 1. Languages.sjson
    lang_file = content_dir / "Game" / "Text" / "Languages.sjson"
    if not lang_file.is_file():
        errors.append(f"Missing Languages.sjson: {lang_file}")
    else:
        lang_txt = lang_file.read_text(encoding="utf-8")
        if '"繁體中文"' not in lang_txt:
            errors.append("Languages.sjson does not contain 繁體中文")
        if '"语言"' in lang_txt or '"简体中文"' in lang_txt:
            errors.append("Languages.sjson still contains Simplified 中文/语言")
        chars.update(c for c in lang_txt if ord(c) >= 0x20)

    # 2. All 18 .sjson files
    dst_sjson_dir = content_dir / "Game" / "Text" / "zh-CN"
    ref_sjson_dir = ref_content_dir / "Game" / "Text" / "zh-CN"
    ref_sjsons = sorted(ref_sjson_dir.glob("*.sjson"))
    if not ref_sjsons:
        errors.append(f"No reference SJSON files in {ref_sjson_dir}")

    sjson_checked = 0
    for ref_p in ref_sjsons:
        dst_p = dst_sjson_dir / ref_p.name
        if not dst_p.is_file():
            errors.append(f"Missing translated SJSON: {ref_p.name}")
            continue
        en_p = None
        if en_sjson_dir and ref_p.name in ("CodexText.zh-CN.sjson", "HelpText.zh-CN.sjson"):
            cand = en_sjson_dir / ref_p.name.replace(".zh-CN.", ".en.")
            if cand.is_file():
                en_p = cand
        errs = validate_pair(ref_p, dst_p, en_p)
        for e in errs:
            errors.append(f"{ref_p.name}: {e}")
        chars.update(c for c in dst_p.read_text(encoding="utf-8") if ord(c) >= 0x20)
        sjson_checked += 1

    # 3. All 37 .csv files
    dst_sub_dir = content_dir / "Subtitles" / "zh-CN"
    ref_sub_dir = ref_content_dir / "Subtitles" / "zh-CN"
    ref_csvs = sorted(ref_sub_dir.glob("*.csv"))
    if not ref_csvs:
        errors.append(f"No reference CSV files in {ref_sub_dir}")

    csv_checked = 0
    csv_rows_total = 0
    for ref_p in ref_csvs:
        dst_p = dst_sub_dir / ref_p.name
        if not dst_p.is_file():
            errors.append(f"Missing translated CSV: {ref_p.name}")
            continue
        with ref_p.open("r", encoding="utf-8", newline="") as f:
            ref_rows = list(csv.reader(f))
        with dst_p.open("r", encoding="utf-8", newline="") as f:
            dst_rows = list(csv.reader(f))
        if len(ref_rows) != len(dst_rows):
            errors.append(f"{ref_p.name}: row count mismatch {len(dst_rows)} vs {len(ref_rows)}")
        for r in dst_rows[1:]:
            if len(r) > 7:
                for bp in ("\u201c", "\u201d", "\u2026\u2026"):
                    if bp in r[7]:
                        errors.append(f"{ref_p.name} {r[3]}: non-TW punctuation {bp!r}")
                chars.update(c for c in r[7] if ord(c) >= 0x20)
        csv_rows_total += len(dst_rows) - 1
        csv_checked += 1

    # 4. XNB Font coverage
    def_xnb = content_dir / "Win" / "Fonts" / "zh-CN" / "Default.xnb"
    zh_xnb = content_dir / "Win" / "Fonts" / "zh-CN" / "zh-CN.xnb"
    missing_default = []
    missing_menu = []
    if not def_xnb.is_file():
        errors.append(f"Missing rebuilt font: {def_xnb}")
    else:
        parsed_def = xnb_font.parse_xnb(str(def_xnb))
        def_set = set(parsed_def["chars"])
        missing_default = sorted(c for c in chars if c not in def_set)
        if missing_default:
            errors.append(f"Default.xnb missing {len(missing_default)} glyphs: {''.join(missing_default[:20])}")

    if not zh_xnb.is_file():
        errors.append(f"Missing rebuilt font: {zh_xnb}")
    else:
        parsed_zh = xnb_font.parse_xnb(str(zh_xnb))
        zh_set = set(parsed_zh["chars"])
        missing_menu = sorted(c for c in "語言繁體中文" if c not in zh_set)
        if missing_menu:
            errors.append(f"zh-CN.xnb missing menu glyphs: {missing_menu}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "sjson_checked": sjson_checked,
        "csv_checked": csv_checked,
        "csv_rows_total": csv_rows_total,
        "unique_chars": len(chars),
        "missing_default_count": len(missing_default),
        "missing_menu_count": len(missing_menu),
    }
