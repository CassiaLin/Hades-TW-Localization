"""Automated unit and E2E tests for Hades 1 Traditional Chinese Localization toolkit."""

import csv
import json
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT_DIR / "tools"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from hades_mod_cli import install_from_dist, uninstall_mod
from m1_extract import extract_game_texts
from m2_prepare import import_translated_dir, prepare_batches
from m4_qa_linter import run_qa
from m5_build import build_mod
from package_public import build_public_release
from sjson_core import apply_field_map, extract_all_fields, validate_pair
from translation_pack import export_translation_pack, verify_translation_pack
import xnb_font


def _make_minimal_xnb(path: Path, chars: list[str] | None = None) -> None:
    """Create a valid uncompressed XNBw v6 Alpha8 SpriteFont binary for offline testing."""
    if chars is None:
        chars = [" ", "*"]
    chars = sorted(chars, key=ord)
    w, h = 64, 64
    pixels = b"\x00" * (w * h)
    n = len(chars)
    out = bytearray()
    out.extend(b"XNBw\x06\x00\x00\x00\x00\x00")
    out.extend(struct.pack("<5I", 12, w, h, 1, len(pixels)))
    out.extend(pixels)
    n_leb = xnb_font.write_uleb128(n)
    out.extend(n_leb)
    for i in range(n):
        out.extend(struct.pack("<4i", i * 8, 0, 6, 8))
    out.extend(n_leb)
    for _ in range(n):
        out.extend(struct.pack("<4i", 0, 0, 10, 10))
    out.extend(n_leb)
    for ch in chars:
        out.extend(ch.encode("utf-8"))
    out.extend(struct.pack("<if", 40, 0.0))
    out.extend(struct.pack("<I", 20))
    out.extend(n_leb)
    for _ in range(n):
        out.extend(struct.pack("<3f", 0.0, 8.0, 2.0))
    out.extend(b"\x01\x2a")
    struct.pack_into("<I", out, 6, len(out))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


def test_public_translation_pack_valid():
    pack_dir = ROOT_DIR / "translations" / "hades1"
    manifest = verify_translation_pack(pack_dir)
    assert manifest["sjson_file_count"] == 18
    assert manifest["sjson_entry_count"] == 12280
    assert manifest["subtitle_file_count"] == 37
    assert manifest["subtitle_entry_count"] == 14109


def test_sjson_core_triple_quotes_and_tag_validation(tmp_path: Path):
    sample_cn = """{
  lang = "zh-CN"
  Texts = [
    {
      Id = "Cast"
      DisplayName = "投掷"
      Description = "消耗 {#BoldFormatGraft}1 {#PreviousFormat}枚血石。"
    }
    {
      Id = "AboutScreen_Credits"
      DisplayName = ""
      Description = \"\"\"开发者 "Test" 名单\"\"\"
    }
  ]
}
"""
    src = tmp_path / "HelpText.zh-CN.sjson"
    dst = tmp_path / "HelpText.zh-TW.sjson"
    src.write_text(sample_cn, encoding="utf-8")

    recs = extract_all_fields(src)
    assert len(recs) == 4

    apply_field_map(
        src,
        dst,
        {
            ("Cast", "DisplayName"): "法陣",
            ("Cast", "Description"): "消耗 {#BoldFormatGraft}1 {#PreviousFormat}顆血石。",
            ("AboutScreen_Credits", "Description"): '開發者 "Test" 名單',
        },
    )
    assert '"""開發者 "Test" 名單"""' in dst.read_text(encoding="utf-8")
    assert validate_pair(src, dst) == []

    # Tag mismatch must be flagged
    bad_dst = tmp_path / "HelpText.bad.sjson"
    apply_field_map(src, bad_dst, {("Cast", "Description"): "缺少標籤「引號」“壞”"})
    errs = validate_pair(src, bad_dst)
    assert any("core tag mismatch" in e for e in errs)
    assert any("non-TW punctuation" in e for e in errs)


def test_xnb_font_render_and_roundtrip(tmp_path: Path):
    src_xnb = tmp_path / "Default.xnb"
    dst_xnb = tmp_path / "Default_tw.xnb"
    _make_minimal_xnb(src_xnb)

    otf = ROOT_DIR / "assets" / "fonts" / "NotoSansTC-Medium.otf"
    assert otf.is_file()

    added, total = xnb_font.render_missing_chars(
        src_xnb=str(src_xnb),
        dst_xnb=str(dst_xnb),
        otf_path=str(otf),
        required_chars=set("語言繁體中文「」⋯"),
        font_size=27,
        baseline_y=29,
        em_box=26,
    )
    assert added == 9
    assert total == 11
    parsed = xnb_font.parse_xnb(str(dst_xnb))
    assert set("語言繁體中文「」⋯").issubset(set(parsed["chars"]))
    assert all(ord(parsed["chars"][i]) < ord(parsed["chars"][i + 1]) for i in range(len(parsed["chars"]) - 1))


def test_dual_mode_e2e_extract_import_build_qa_install_uninstall(tmp_path: Path):
    game_dir = tmp_path / "Hades"
    content = game_dir / "Content"

    # Populate synthetic Hades game directory
    (content / "Game" / "Text").mkdir(parents=True)
    (content / "Game" / "Text" / "Languages.sjson").write_text(
        'Id = "SettingsMenuScreen_Language"\nDisplayName = "语言"\nId = "zh-CN"\nDisplayName = "简体中文"\n',
        encoding="utf-8",
    )
    sjson_src = (
        '{\n  lang = "zh-CN"\n  Texts = [\n    {\n      Id = "Dash"\n'
        '      DisplayName = "冲刺"\n      Description = "快速移动。"\n    }\n  ]\n}\n'
    )
    sjson_en = (
        '{\n  lang = "en"\n  Texts = [\n    {\n      Id = "Dash"\n'
        '      DisplayName = "Dash"\n      Description = "Move quickly."\n    }\n  ]\n}\n'
    )
    (content / "Game" / "Text" / "zh-CN").mkdir(parents=True)
    (content / "Game" / "Text" / "en").mkdir(parents=True)
    (content / "Game" / "Text" / "zh-CN" / "HelpText.zh-CN.sjson").write_text(sjson_src, encoding="utf-8")
    (content / "Game" / "Text" / "en" / "HelpText.en.sjson").write_text(sjson_en, encoding="utf-8")

    (content / "Subtitles" / "zh-CN").mkdir(parents=True)
    (content / "Subtitles" / "en").mkdir(parents=True)
    with (content / "Subtitles" / "zh-CN" / "ZagreusHome.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["c0", "Status", "c2", "RowId", "c4", "c5", "c6", "Line"])
        w.writerow(["", "Integrated", "", "ZagreusHome_0001", "", "", "", "我回来了……"])
    with (content / "Subtitles" / "en" / "ZagreusHome.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["c0", "Status", "c2", "RowId", "c4", "c5", "c6", "Line"])
        w.writerow(["", "Integrated", "", "ZagreusHome_0001", "", "", "", "I'm back..."])

    _make_minimal_xnb(content / "Win" / "Fonts" / "zh-CN" / "Default.xnb")
    _make_minimal_xnb(content / "Win" / "Fonts" / "zh-CN" / "zh-CN.xnb")
    (content / "Win" / "Fonts" / "zh-CN" / "Fonts.remap").write_text("remap\n", encoding="utf-8")
    for lang in ("en", "ja", "ko", "pl", "ru"):
        _make_minimal_xnb(content / "Win" / "Fonts" / lang / "zh-CN.xnb")

    # 1. Dev extract & prepare
    work_dir = tmp_path / "work"
    ext_stats = extract_game_texts(game_dir, work_dir)
    assert ext_stats["sjson_files"] == 1
    assert ext_stats["sjson_items"] == 2
    assert ext_stats["subtitle_items"] == 1

    prep_stats = prepare_batches(work_dir, ROOT_DIR / "glossary", batch_size=50)
    assert prep_stats["batch_count"] == 2

    # 2. Export initial empty/template pack, then import translator JSON overrides
    pack_dir = tmp_path / "pack"
    export_translation_pack(content, content, pack_dir)
    imp_dir = tmp_path / "imp"
    imp_dir.mkdir()
    (imp_dir / "translated.json").write_text(
        json.dumps(
            [
                {"file": "HelpText.zh-CN.sjson", "id": "Dash", "field": "DisplayName", "zh": "衝刺"},
                {"file": "HelpText.zh-CN.sjson", "id": "Dash", "field": "Description", "zh": "快速移動。"},
                {"file": "ZagreusHome.csv", "row_id": "ZagreusHome_0001", "zh": "我回來了……"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    imp_stats = import_translated_dir(imp_dir, pack_dir)
    assert imp_stats["sjson_updated"] == 2
    assert imp_stats["subtitles_updated"] == 1
    verify_translation_pack(pack_dir)

    # 3. Build, QA, install, verify, uninstall
    dist_dir = tmp_path / "dist"
    otf = ROOT_DIR / "assets" / "fonts" / "NotoSansTC-Medium.otf"
    bm = build_mod(game_dir, pack_dir, dist_dir, otf)
    assert bm["sjson_applied"] == 2
    assert bm["csv_applied"] == 1

    qa = run_qa(dist_dir / "Content", content, content / "Game" / "Text" / "en")
    assert qa["passed"], qa["errors"]

    inst_res = install_from_dist(game_dir, dist_dir)
    assert inst_res["state"] == "COMMITTED"
    assert "繁體中文" in (content / "Game" / "Text" / "Languages.sjson").read_text(encoding="utf-8")
    assert "⋯⋯" in (content / "Subtitles" / "zh-CN" / "ZagreusHome.csv").read_text(encoding="utf-8")

    un_res = uninstall_mod(game_dir)
    assert un_res["state"] == "UNINSTALLED"
    assert "简体中文" in (content / "Game" / "Text" / "Languages.sjson").read_text(encoding="utf-8")


def test_package_public_audit(tmp_path: Path):
    pub_dir = tmp_path / "pub_release"
    res = build_public_release(pub_dir, source_root=ROOT_DIR, overwrite=True)
    assert res["audit"]["sjson_entries"] == 12280
    assert res["audit"]["subtitle_entries"] == 14109
    assert (pub_dir / ".gitignore").is_file()
    assert (pub_dir / "assets" / "fonts" / "NotoSansTC-Medium.otf").is_file()
    assert not any(pub_dir.rglob("*.sjson"))
    assert not any(pub_dir.rglob("*.csv"))
    assert not any(pub_dir.rglob("*.xnb"))
