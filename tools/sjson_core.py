"""Hades SJSON parser, field injector, and structural/tag validator."""

import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


TRANSLATABLE_FIELDS = ("DisplayName", "Description", "OverwriteDescription")


def iter_entry_spans(text: str) -> List[Tuple[int, int]]:
    """Find (start, end) character spans of entry { ... } blocks inside Texts = [ ... ]."""
    m = re.search(r"Texts\s*=\s*\[", text)
    if not m:
        return []
    pos = m.end()
    spans: List[Tuple[int, int]] = []
    lines = text[pos:].splitlines(keepends=True)
    cur_start = -1
    offset = pos
    in_block_cmt = False
    for line in lines:
        stripped = line.strip()
        if in_block_cmt:
            if "*/" in stripped:
                in_block_cmt = False
            offset += len(line)
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block_cmt = True
            offset += len(line)
            continue
        if line.startswith("    {") or line.startswith("  {"):
            if cur_start == -1:
                cur_start = offset
        elif (line.startswith("    }") or line.startswith("  }")) and cur_start != -1:
            spans.append((cur_start, offset + len(line)))
            cur_start = -1
        elif stripped == "]" and cur_start == -1:
            break
        offset += len(line)
    return spans


def extract_field(block: str, key: str) -> Optional[str]:
    """Extract a single string field from an SJSON entry block, handling triple quotes."""
    m3 = re.search(rf"{key}\s*=\s*\"\"\"(.*?)\"\"\"", block, re.S)
    if m3:
        return m3.group(1).strip('"')
    m1 = re.search(rf'{key}\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)"', block)
    if m1:
        return m1.group(1)
    return None


def parse_entries(text: str) -> Dict[str, Dict[str, str]]:
    """Parse an SJSON file into {Id: {Field: Value}} preserving field values."""
    entries: Dict[str, Dict[str, str]] = {}
    for s, e in iter_entry_spans(text):
        block = text[s:e]
        m_id = re.search(r'Id\s*=\s*"([^"]+)"', block)
        if not m_id:
            continue
        eid = m_id.group(1)
        fields: Dict[str, str] = {}
        for key in TRANSLATABLE_FIELDS:
            val = extract_field(block, key)
            if val is not None:
                fields[key] = val
        entries[eid] = fields
    return entries


def extract_all_fields(sjson_path: Path) -> List[Dict[str, str]]:
    """Return all translatable fields from an SJSON file as [{"id", "field", "value"}]."""
    text = sjson_path.read_text(encoding="utf-8")
    records: List[Dict[str, str]] = []
    for s, e in iter_entry_spans(text):
        block = text[s:e]
        m_id = re.search(r'Id\s*=\s*"([^"]+)"', block)
        if not m_id:
            continue
        eid = m_id.group(1)
        for key in TRANSLATABLE_FIELDS:
            val = extract_field(block, key)
            if val is not None:
                records.append({"id": eid, "field": key, "value": val})
    return records


def extract_rich_entries(src_path: Path, en_path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Extract SJSON entries paired with English source / comment context and tags."""
    text = src_path.read_text(encoding="utf-8")
    en_map = parse_entries(en_path.read_text(encoding="utf-8")) if en_path and en_path.is_file() else {}
    items: List[Dict[str, str]] = []
    for s, e in iter_entry_spans(text):
        block = text[s:e]
        m_id = re.search(r'Id\s*=\s*"([^"]+)"', block)
        if not m_id:
            continue
        eid = m_id.group(1)
        speaker_m = re.search(r'Speaker\s*=\s*"([^"]+)"', block)
        comment_m = re.search(r"/\*(.*?)\*/", block, re.S)
        comment = comment_m.group(1).strip() if comment_m else ""
        for key in TRANSLATABLE_FIELDS:
            cn_val = extract_field(block, key)
            if cn_val is None:
                continue
            en_val = en_map.get(eid, {}).get(key, "")
            rec: Dict[str, str] = {
                "id": eid,
                "field": key,
                "cn": cn_val,
                "en": en_val,
            }
            if speaker_m:
                rec["speaker"] = speaker_m.group(1)
            if comment and not en_val:
                rec["en_context"] = comment
            tags = extract_tags(en_val or cn_val)
            if tags:
                rec["tags"] = tags
            items.append(rec)
    return items


def apply_field_map(src_path: Path, dst_path: Path, field_map: Dict[Tuple[str, str], str]) -> int:
    """Apply {(id, field): zh_value} onto src_path SJSON and write dst_path, preserving quotes."""
    text = src_path.read_text(encoding="utf-8")
    parts: List[str] = []
    last = 0
    replaced = 0

    for s, e in iter_entry_spans(text):
        parts.append(text[last:s])
        block = text[s:e]
        m_id = re.search(r'Id\s*=\s*"([^"]+)"', block)
        if m_id:
            eid = m_id.group(1)
            for key in TRANSLATABLE_FIELDS:
                if (eid, key) not in field_map:
                    continue
                val = field_map[(eid, key)]
                if re.search(rf"{key}\s*=\s*\"\"\"", block):
                    block = re.sub(
                        rf'({key}\s*=\s*)""""?.*?"""("?)',
                        lambda km, v=val: f'{km.group(1)}"""{v}"""',
                        block,
                        count=1,
                        flags=re.S,
                    )
                    replaced += 1
                else:
                    # If replacement contains raw unescaped quote and wasn't triple-quoted, protect with """
                    use_triple = bool(re.search(r'(?<!\\)"', val))
                    block = re.sub(
                        rf'({key}\s*=\s*)"((?:[^"\\]|\\.)*)"',
                        lambda km, v=val, t=use_triple: f'{km.group(1)}"""{v}"""' if t else f'{km.group(1)}"{v}"',
                        block,
                        count=1,
                    )
                    replaced += 1
        parts.append(block)
        last = e

    parts.append(text[last:])
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text("".join(parts), encoding="utf-8")
    return replaced


def apply_sjson(src_path: Path, items: Iterable[Dict[str, str]], dst_path: Path) -> int:
    """Compatibility wrapper accepting [{"Id": ..., "TW_DisplayName": ..., "TW_Description": ...}]."""
    field_map: Dict[Tuple[str, str], str] = {}
    for item in items:
        eid = item["Id"]
        for key in TRANSLATABLE_FIELDS:
            tk = f"TW_{key}"
            if tk in item and item[tk] is not None:
                field_map[(eid, key)] = item[tk]
    return apply_field_map(src_path, dst_path, field_map)


def extract_tags(val: str) -> List[str]:
    """Extract Hades formatting/icon/keyword tags and \\Column directives from a string."""
    return re.findall(r"\{[^}]+\}|\\Column\s+\d+|@GUI\\\\[^\s\"\\]+", val)


def validate_pair(src_path: Path, dst_path: Path, en_path: Optional[Path] = None) -> List[str]:
    """Validate IDs, fields, brace balance, tag multiset parity, and TW punctuation."""
    errors: List[str] = []
    src = parse_entries(src_path.read_text(encoding="utf-8"))
    dst = parse_entries(dst_path.read_text(encoding="utf-8"))
    en = parse_entries(en_path.read_text(encoding="utf-8")) if en_path and en_path.exists() else {}

    if set(src.keys()) != set(dst.keys()):
        missing = set(src.keys()) - set(dst.keys())
        extra = set(dst.keys()) - set(src.keys())
        if missing:
            errors.append(f"Missing IDs: {sorted(missing)[:5]}")
        if extra:
            errors.append(f"Extra IDs: {sorted(extra)[:5]}")

    for eid, s_fields in src.items():
        if eid not in dst:
            continue
        d_fields = dst[eid]
        for k, s_val in s_fields.items():
            if k not in d_fields:
                errors.append(f"{eid}.{k}: missing field")
                continue
            d_val = d_fields[k]
            d_tags = Counter(extract_tags(d_val))
            s_tags = Counter(extract_tags(s_val))
            e_tags = Counter(extract_tags(en.get(eid, {}).get(k, ""))) if eid in en and k in en[eid] else None
            if d_val.count("{") != d_val.count("}"):
                errors.append(f"{eid}.{k}: unbalanced braces")
            if e_tags is not None:
                if d_tags != s_tags and d_tags != e_tags:
                    errors.append(f"{eid}.{k}: tag mismatch: src={dict(s_tags)} dst={dict(d_tags)}")
            else:
                s_core = Counter(t for t in extract_tags(s_val) if "Italic" not in t and "Previous" not in t)
                d_core = Counter(t for t in extract_tags(d_val) if "Italic" not in t and "Previous" not in t)
                if s_core != d_core:
                    errors.append(f"{eid}.{k}: core tag mismatch: src={dict(s_core)} dst={dict(d_core)}")
            for bad_punct in ("\u201c", "\u201d", "\u2026\u2026"):
                if bad_punct in d_val:
                    errors.append(f"{eid}.{k}: non-TW punctuation {bad_punct!r}")
    return errors
