"""M1 Extractor: Extract clean SJSON and CSV texts from Hades 1 into AI-friendly JSON files."""

import csv
import json
from pathlib import Path
from typing import Dict

from sjson_core import extract_rich_entries


def resolve_clean_content_dir(game_dir: Path) -> Path:
    """Use backed-up unmodified originals if installed, otherwise live Content directory."""
    bak_content = game_dir / "_Backup_TW_Mod" / "Content"
    if (bak_content / "Game" / "Text" / "Languages.sjson").is_file():
        return bak_content
    return game_dir / "Content"


def extract_game_texts(game_dir: Path, work_dir: Path) -> Dict[str, int]:
    """Extract all 18 .sjson and 37 .csv files into work_dir/extracted/{sjson,subtitles}/."""
    clean_content = resolve_clean_content_dir(game_dir)
    live_content = game_dir / "Content"

    sjson_cn_dir = clean_content / "Game" / "Text" / "zh-CN"
    sjson_en_dir = live_content / "Game" / "Text" / "en"
    sub_cn_dir = clean_content / "Subtitles" / "zh-CN"
    sub_en_dir = live_content / "Subtitles" / "en"

    out_sjson_dir = work_dir / "extracted" / "sjson"
    out_sub_dir = work_dir / "extracted" / "subtitles"
    out_sjson_dir.mkdir(parents=True, exist_ok=True)
    out_sub_dir.mkdir(parents=True, exist_ok=True)

    sjson_files = sorted(sjson_cn_dir.glob("*.sjson"))
    sjson_items_total = 0
    for cn_file in sjson_files:
        en_file = sjson_en_dir / cn_file.name.replace(".zh-CN.", ".en.")
        items = extract_rich_entries(cn_file, en_file if en_file.is_file() else None)
        out_path = out_sjson_dir / (cn_file.stem + ".json")
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        sjson_items_total += len(items)

    csv_files = sorted(sub_cn_dir.glob("*.csv"))
    sub_items_total = 0
    for cn_csv in csv_files:
        en_csv = sub_en_dir / cn_csv.name
        en_lookup = {}
        if en_csv.is_file():
            with en_csv.open("r", encoding="utf-8", newline="") as f:
                for row in list(csv.reader(f))[1:]:
                    if len(row) > 7 and row[3].strip():
                        en_lookup[row[3]] = row[7]

        items = []
        seen_ids = set()
        with cn_csv.open("r", encoding="utf-8", newline="") as f:
            for row in list(csv.reader(f))[1:]:
                if len(row) > 7 and row[3].strip() and row[3] not in seen_ids:
                    seen_ids.add(row[3])
                    status = row[1] if len(row) > 1 else ""
                    items.append(
                        {
                            "file": cn_csv.name,
                            "row_id": row[3],
                            "status": status,
                            "en": en_lookup.get(row[3], ""),
                            "cn": row[7],
                        }
                    )
        out_path = out_sub_dir / (cn_csv.stem + ".json")
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        sub_items_total += len(items)

    stats = {
        "sjson_files": len(sjson_files),
        "sjson_items": sjson_items_total,
        "subtitle_files": len(csv_files),
        "subtitle_items": sub_items_total,
    }
    meta_dir = work_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "extraction_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return stats
