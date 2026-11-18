"""M2 Batch Preparer & M3 Translator Import for AI/Human Translation Workflows."""

import json
from pathlib import Path
from typing import Any, Dict, List


PROMPT_HEADER = """請將以下 Hades（黑帝斯）英文條目直接翻譯為台灣繁體中文（zh-TW），嚴格遵守下方術語與排版規範：

1. 輸出格式：保持 JSON 陣列（或每行一筆 JSONL），每筆需包含對應識別欄：
   - SJSON 條目：`{"file": "...", "id": "...", "field": "...", "zh": "繁體中文譯文"}`
   - Subtitles 條目：`{"file": "...", "row_id": "...", "zh": "繁體中文譯文"}`
2. 嚴格保留所有引擎控制碼（`{$Keywords...}`、`{#...}`、`{!Icons...}`、`\\n`、`\\Column ...`），數量與種類必須與原文一致。
3. 使用台灣標準標點：`「」`、`『』`、`〈〉`、`《》`、`⋯⋯`（禁用簡體 `“”` 與 `……`）。
4. 嚴格對齊以下《黑帝斯 II》官方繁中術語表：

"""


def prepare_batches(
    work_dir: Path,
    glossary_dir: Path,
    batch_size: int = 200,
) -> Dict[str, int]:
    """Split extracted JSON files into batch_XXX.input.json and prepared/batch_XXX.prompt.txt."""
    ext_dir = work_dir / "extracted"
    batches_dir = work_dir / "batches"
    prepared_dir = work_dir / "prepared"
    batches_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    glossary_md = glossary_dir / "glossary_v1.md"
    glossary_text = glossary_md.read_text(encoding="utf-8") if glossary_md.is_file() else ""

    batch_idx = 0
    total_items = 0

    for kind in ("sjson", "subtitles"):
        kind_dir = ext_dir / kind
        if not kind_dir.is_dir():
            continue
        for json_file in sorted(kind_dir.glob("*.json")):
            items = json.loads(json_file.read_text(encoding="utf-8"))
            orig_filename = json_file.stem + (".sjson" if kind == "sjson" else ".csv")
            for i in range(0, len(items), batch_size):
                chunk = items[i : i + batch_size]
                batch_idx += 1
                b_name = f"batch_{batch_idx:04d}_{kind}"
                tagged_chunk = []
                for entry in chunk:
                    obj = {"file": orig_filename}
                    obj.update(entry)
                    tagged_chunk.append(obj)
                total_items += len(tagged_chunk)
                (batches_dir / f"{b_name}.input.json").write_text(
                    json.dumps(tagged_chunk, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                prompt_text = (
                    f"{PROMPT_HEADER}\n{glossary_text}\n\n"
                    f"---\n來源批次檔案：`{b_name}.input.json`（共 {len(tagged_chunk)} 筆）\n"
                )
                (prepared_dir / f"{b_name}.prompt.txt").write_text(prompt_text, encoding="utf-8")

    return {"batch_count": batch_idx, "total_items": total_items}


def _load_records_from_file(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix.lower() == ".jsonl" or not raw.startswith("["):
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def _norm_tw(text: str) -> str:
    return text.replace("\u2026\u2026", "\u22ef\u22ef").replace("\u201c", "\u300c").replace("\u201d", "\u300d")


def import_translated_dir(from_dir: Path, pack_dir: Path) -> Dict[str, int]:
    """Import *.json / *.jsonl translation files from from_dir and merge into pack_dir."""
    if not from_dir.is_dir():
        raise FileNotFoundError(f"Import directory not found: {from_dir}")

    sjson_updates = {}
    sub_updates = {}
    files_read = 0

    for f in sorted(list(from_dir.rglob("*.json")) + list(from_dir.rglob("*.jsonl"))):
        if f.name.endswith(".input.json") or f.name == "manifest.json":
            continue
        recs = _load_records_from_file(f)
        if not recs:
            continue
        files_read += 1
        for obj in recs:
            zh = obj.get("zh") or obj.get("TW") or obj.get("tw")
            if zh is None:
                continue
            zh = _norm_tw(zh)
            fname = obj.get("file") or obj.get("File")
            if "row_id" in obj or "RowId" in obj:
                rid = obj.get("row_id") or obj.get("RowId")
                if fname and rid:
                    sub_updates[(fname, rid)] = zh
            elif "id" in obj or "Id" in obj:
                eid = obj.get("id") or obj.get("Id")
                field = obj.get("field") or obj.get("Field")
                if fname and eid and field:
                    sjson_updates[(fname, eid, field)] = zh
                elif fname and eid:
                    for fk, tk in (("DisplayName", "TW_DisplayName"), ("Description", "TW_Description")):
                        if tk in obj and obj[tk] is not None:
                            sjson_updates[(fname, eid, fk)] = _norm_tw(obj[tk])

    sjson_applied = 0
    sjson_pack = pack_dir / "sjson_zh_tw.jsonl"
    if sjson_pack.is_file() and sjson_updates:
        cur = [json.loads(l) for l in sjson_pack.read_text(encoding="utf-8").splitlines() if l.strip()]
        existing_keys = set()
        for r in cur:
            k = (r["file"], r["id"], r["field"])
            existing_keys.add(k)
            if k in sjson_updates:
                r["zh"] = sjson_updates[k]
                sjson_applied += 1
        for (fn, eid, fld), val in sorted(sjson_updates.items()):
            if (fn, eid, fld) not in existing_keys:
                cur.append({"file": fn, "id": eid, "field": fld, "zh": val})
                sjson_applied += 1
        sjson_pack.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in cur) + "\n", encoding="utf-8")

    sub_applied = 0
    sub_pack = pack_dir / "subtitles_zh_tw.jsonl"
    if sub_pack.is_file() and sub_updates:
        cur = [json.loads(l) for l in sub_pack.read_text(encoding="utf-8").splitlines() if l.strip()]
        existing_keys = set()
        for r in cur:
            k = (r["file"], r["row_id"])
            existing_keys.add(k)
            if k in sub_updates:
                r["zh"] = sub_updates[k]
                sub_applied += 1
        for (fn, rid), val in sorted(sub_updates.items()):
            if (fn, rid) not in existing_keys:
                cur.append({"file": fn, "row_id": rid, "zh": val})
                sub_applied += 1
        sub_pack.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in cur) + "\n", encoding="utf-8")

    # Refresh manifest checksums/counts
    from translation_pack import sha256_file
    m_path = pack_dir / "manifest.json"
    if m_path.is_file():
        manifest = json.loads(m_path.read_text(encoding="utf-8"))
        for fn in ("languages_zh_tw.json", "sjson_zh_tw.jsonl", "subtitles_zh_tw.jsonl"):
            if (pack_dir / fn).is_file():
                manifest["files"][fn] = sha256_file(pack_dir / fn)
        manifest["sjson_entry_count"] = sum(
            1 for l in sjson_pack.read_text(encoding="utf-8").splitlines() if l.strip()
        )
        manifest["subtitle_entry_count"] = sum(
            1 for l in sub_pack.read_text(encoding="utf-8").splitlines() if l.strip()
        )
        m_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"files_read": files_read, "sjson_updated": sjson_applied, "subtitles_updated": sub_applied}
