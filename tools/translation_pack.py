"""Pure Traditional Chinese Translation Pack exporter and verifier for Hades 1."""

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sjson_core import extract_all_fields


PACK_FORMAT_VERSION = "1.0"
FORBIDDEN_ENGLISH_KEYS = {"en", "EN", "EN_Context", "en_raw", "en_clean", "cn", "CN"}
FORBIDDEN_PUNCTUATION = ("\u201c", "\u201d", "\u2026\u2026")


class TranslationPackError(RuntimeError):
    """Raised when a translation pack fails integrity, schema, or purity checks."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def export_translation_pack(
    built_content_dir: Path,
    orig_content_dir: Path,
    pack_dir: Path,
) -> Dict[str, Any]:
    """Export pure zh-TW translation pack (no English text or game binaries) to pack_dir."""
    pack_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export SJSON translations
    built_sjson_dir = built_content_dir / "Game" / "Text" / "zh-CN"
    sjson_files = sorted(p for p in built_sjson_dir.glob("*.sjson"))
    if not sjson_files:
        raise TranslationPackError(f"No translated .sjson files found in {built_sjson_dir}")

    sjson_records = []
    for p in sjson_files:
        for rec in extract_all_fields(p):
            sjson_records.append(
                {
                    "file": p.name,
                    "id": rec["id"],
                    "field": rec["field"],
                    "zh": rec["value"],
                }
            )
    sjson_records.sort(key=lambda r: (r["file"], r["id"], r["field"]))
    sjson_out = pack_dir / "sjson_zh_tw.jsonl"
    sjson_out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in sjson_records) + "\n",
        encoding="utf-8",
    )

    # 2. Export Subtitle CSV translations (only rows with non-empty RowId, deduplicated deterministically)
    built_sub_dir = built_content_dir / "Subtitles" / "zh-CN"
    csv_files = sorted(p for p in built_sub_dir.glob("*.csv"))
    if not csv_files:
        raise TranslationPackError(f"No translated .csv files found in {built_sub_dir}")

    seen_sub = set()
    sub_records = []
    for p in csv_files:
        with p.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        for r in rows[1:]:
            if len(r) > 7 and r[3].strip():
                key = (p.name, r[3])
                if key in seen_sub:
                    continue
                seen_sub.add(key)
                sub_records.append(
                    {
                        "file": p.name,
                        "row_id": r[3],
                        "zh": r[7],
                    }
                )
    sub_records.sort(key=lambda r: (r["file"], r["row_id"]))
    sub_out = pack_dir / "subtitles_zh_tw.jsonl"
    sub_out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in sub_records) + "\n",
        encoding="utf-8",
    )

    # 3. Export Languages.sjson UI overrides
    lang_out = pack_dir / "languages_zh_tw.json"
    lang_data = {
        "SettingsMenuScreen_Language": "語言",
        "zh-CN": "繁體中文",
    }
    lang_out.write_text(json.dumps(lang_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 4. Write manifest.json
    file_hashes = {}
    for fn in ("languages_zh_tw.json", "sjson_zh_tw.jsonl", "subtitles_zh_tw.jsonl"):
        file_hashes[fn] = sha256_file(pack_dir / fn)

    manifest = {
        "pack_format_version": PACK_FORMAT_VERSION,
        "game": "Hades",
        "target_locale": "zh-TW",
        "target_slot": "zh-CN",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sjson_file_count": len(sjson_files),
        "sjson_entry_count": len(sjson_records),
        "subtitle_file_count": len(csv_files),
        "subtitle_entry_count": len(sub_records),
        "files": file_hashes,
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify_translation_pack(pack_dir: Path) -> Dict[str, Any]:
    """Verify manifest checksums, counts, schema, and purity of the translation pack."""
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        raise TranslationPackError(f"Missing manifest.json in {pack_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("pack_format_version") != PACK_FORMAT_VERSION:
        raise TranslationPackError(f"Unsupported pack_format_version: {manifest.get('pack_format_version')}")

    expected_files = manifest.get("files", {})
    for fn, expected_hash in expected_files.items():
        fp = pack_dir / fn
        if not fp.is_file():
            raise TranslationPackError(f"Missing pack file: {fp}")
        actual = sha256_file(fp)
        if actual != expected_hash:
            raise TranslationPackError(f"SHA-256 mismatch for {fn}: expected {expected_hash}, got {actual}")

    lang_data = json.loads((pack_dir / "languages_zh_tw.json").read_text(encoding="utf-8"))
    if lang_data.get("SettingsMenuScreen_Language") != "語言" or lang_data.get("zh-CN") != "繁體中文":
        raise TranslationPackError(f"Unexpected languages_zh_tw.json values: {lang_data}")

    sjson_lines = [l for l in (pack_dir / "sjson_zh_tw.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(sjson_lines) != manifest.get("sjson_entry_count"):
        raise TranslationPackError("sjson_entry_count mismatch")
    for idx, line in enumerate(sjson_lines):
        obj = json.loads(line)
        if not {"file", "id", "field", "zh"}.issubset(obj.keys()):
            raise TranslationPackError(f"sjson_zh_tw.jsonl:{idx+1} invalid schema")
        if FORBIDDEN_ENGLISH_KEYS.intersection(obj.keys()):
            raise TranslationPackError(f"sjson_zh_tw.jsonl:{idx+1} contains forbidden English key")
        for bp in FORBIDDEN_PUNCTUATION:
            if bp in obj["zh"]:
                raise TranslationPackError(f"sjson_zh_tw.jsonl:{idx+1} contains non-TW punctuation {bp!r}")

    sub_lines = [l for l in (pack_dir / "subtitles_zh_tw.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(sub_lines) != manifest.get("subtitle_entry_count"):
        raise TranslationPackError("subtitle_entry_count mismatch")
    for idx, line in enumerate(sub_lines):
        obj = json.loads(line)
        if not {"file", "row_id", "zh"}.issubset(obj.keys()):
            raise TranslationPackError(f"subtitles_zh_tw.jsonl:{idx+1} invalid schema")
        if FORBIDDEN_ENGLISH_KEYS.intersection(obj.keys()):
            raise TranslationPackError(f"subtitles_zh_tw.jsonl:{idx+1} contains forbidden English key")
        for bp in FORBIDDEN_PUNCTUATION:
            if bp in obj["zh"]:
                raise TranslationPackError(f"subtitles_zh_tw.jsonl:{idx+1} contains non-TW punctuation {bp!r}")

    return manifest
