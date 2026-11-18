import os
import struct
import sys
from PIL import Image, ImageDraw, ImageFont


def read_uleb128(data: bytes, pos: int) -> tuple[int, int]:
    val = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, pos


def write_uleb128(val: int) -> bytes:
    out = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def parse_xnb(path: str) -> dict:
    d = open(path, "rb").read()
    assert d[:6] == b"XNBw\x06\x00", f"Unsupported XNB header: {d[:6]!r}"
    total_size = struct.unpack_from("<I", d, 6)[0]
    assert total_size == len(d), f"Size mismatch: header={total_size}, actual={len(d)}"
    fmt, w, h, mips, tex_len = struct.unpack_from("<5I", d, 10)
    assert fmt == 12 and mips == 1 and tex_len == w * h, (
        f"Unexpected texture header: fmt={fmt}, w={w}, h={h}, mips={mips}, tex_len={tex_len}"
    )
    pos = 30
    pixels = d[pos : pos + tex_len]
    pos += tex_len

    n1, pos = read_uleb128(d, pos)
    glyphs = [struct.unpack_from("<4i", d, pos + i * 16) for i in range(n1)]
    pos += n1 * 16

    n2, pos = read_uleb128(d, pos)
    cropping = [struct.unpack_from("<4i", d, pos + i * 16) for i in range(n2)]
    pos += n2 * 16

    n3, pos = read_uleb128(d, pos)
    chars = []
    for _ in range(n3):
        b0 = d[pos]
        clen = 1 if b0 < 0x80 else (2 if b0 < 0xE0 else (3 if b0 < 0xF0 else 4))
        chars.append(d[pos : pos + clen].decode("utf-8"))
        pos += clen

    assert n1 == n2 == n3, f"Count mismatch: {n1}, {n2}, {n3}"

    line_spacing, spacing = struct.unpack_from("<if", d, pos)
    pos += 8
    k_hdr = struct.unpack_from("<I", d, pos)[0]
    pos += 4
    n4, pos = read_uleb128(d, pos)
    assert n4 == n3, f"Kerning count mismatch: {n4} != {n3}"
    kerning = [struct.unpack_from("<3f", d, pos + i * 12) for i in range(n4)]
    pos += n4 * 12
    tail = d[pos:]

    return {
        "w": w,
        "h": h,
        "pixels": pixels,
        "glyphs": glyphs,
        "cropping": cropping,
        "chars": chars,
        "line_spacing": line_spacing,
        "spacing": spacing,
        "k_hdr": k_hdr,
        "kerning": kerning,
        "tail": tail,
    }


def write_xnb(path: str, font_data: dict) -> None:
    w = font_data["w"]
    h = font_data["h"]
    pixels = font_data["pixels"]
    assert len(pixels) == w * h
    n = len(font_data["chars"])

    # Sort all entries by Unicode codepoint (required for binary search in XNA/MonoGame)
    items = sorted(
        zip(
            font_data["chars"],
            font_data["glyphs"],
            font_data["cropping"],
            font_data["kerning"],
        ),
        key=lambda x: ord(x[0]),
    )

    out = bytearray()
    out.extend(b"XNBw\x06\x00")
    out.extend(b"\x00\x00\x00\x00")  # placeholder for total_size
    out.extend(struct.pack("<5I", 12, w, h, 1, len(pixels)))
    out.extend(pixels)

    n_leb = write_uleb128(n)
    out.extend(n_leb)
    for _, g, _, _ in items:
        out.extend(struct.pack("<4i", *g))

    out.extend(n_leb)
    for _, _, c, _ in items:
        out.extend(struct.pack("<4i", *c))

    out.extend(n_leb)
    for ch, _, _, _ in items:
        out.extend(ch.encode("utf-8"))

    out.extend(struct.pack("<if", font_data["line_spacing"], font_data["spacing"]))
    out.extend(struct.pack("<I", font_data["k_hdr"]))
    out.extend(n_leb)
    for _, _, _, k in items:
        out.extend(struct.pack("<3f", *k))

    out.extend(font_data["tail"])
    struct.pack_into("<I", out, 6, len(out))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)


def render_missing_chars(
    src_xnb: str,
    dst_xnb: str,
    otf_path: str,
    required_chars: set[str],
    font_size: int,
    baseline_y: int,
    em_box: int,
) -> tuple[int, int]:
    data = parse_xnb(src_xnb)
    existing = set(data["chars"])
    missing = sorted(
        [c for c in required_chars if c not in existing and ord(c) >= 0x20],
        key=ord,
    )
    if not missing:
        os.makedirs(os.path.dirname(os.path.abspath(dst_xnb)), exist_ok=True)
        write_xnb(dst_xnb, data)
        return 0, len(existing)

    font = ImageFont.truetype(otf_path, font_size)
    rendered = []
    for ch in missing:
        bb = font.getbbox(ch, anchor="ls")
        adv = float(font.getlength(ch))
        if bb is None or bb[2] <= bb[0] or bb[3] <= bb[1]:
            # Whitespace / zero-width fallback
            rendered.append((ch, None, (0, 0, 0, 0), (0, 0, em_box, em_box), (0.0, 0.0, adv)))
            continue
        bx0, by0, bx1, by1 = bb
        bw = bx1 - bx0
        bh = by1 - by0
        # 1px transparent border around tight glyph bbox for clean bilinear sampling
        cw = bw + 2
        ch_px = bh + 2
        cell = Image.new("L", (cw, ch_px), 0)
        draw = ImageDraw.Draw(cell)
        draw.text((1 - bx0, 1 - by0), ch, fill=255, font=font, anchor="ls")

        crop_y = baseline_y + by0 - 1
        left_bearing = float(bx0 - 1)
        width = float(cw)
        right_bearing = adv - left_bearing - width
        rendered.append(
            (ch, cell, (cw, ch_px), (0, crop_y, em_box, em_box), (left_bearing, width, right_bearing))
        )

    # Pack new glyphs below existing texture height
    atlas_w = data["w"]
    old_h = data["h"]
    pad = 2
    cur_x = pad
    cur_y = old_h + pad
    row_h = 0

    placements = []
    for item in rendered:
        ch, cell, size_info, crop, kern = item
        if cell is None:
            placements.append((ch, None, (0, 0, 0, 0), crop, kern))
            continue
        cw, ch_px = size_info
        if cur_x + cw + pad > atlas_w:
            cur_x = pad
            cur_y += row_h + pad
            row_h = 0
        placements.append((ch, cell, (cur_x, cur_y, cw, ch_px), crop, kern))
        cur_x += cw + pad
        if ch_px > row_h:
            row_h = ch_px

    new_h = cur_y + row_h + pad
    # Round up to multiple of 4 for clean GPU texture alignment
    if new_h % 4 != 0:
        new_h += 4 - (new_h % 4)

    atlas = Image.new("L", (atlas_w, new_h), 0)
    old_img = Image.frombytes("L", (atlas_w, old_h), data["pixels"])
    atlas.paste(old_img, (0, 0))

    for ch, cell, glyph_rect, crop, kern in placements:
        if cell is not None:
            atlas.paste(cell, (glyph_rect[0], glyph_rect[1]))
        data["chars"].append(ch)
        data["glyphs"].append(glyph_rect)
        data["cropping"].append(crop)
        data["kerning"].append(kern)

    data["h"] = new_h
    data["pixels"] = atlas.tobytes()
    write_xnb(dst_xnb, data)

    # Verify round-trip
    check = parse_xnb(dst_xnb)
    assert set(required_chars & {c for c in required_chars if ord(c) >= 0x20}).issubset(set(check["chars"]))
    return len(missing), len(check["chars"])


if __name__ == "__main__":
    print("xnb_font.py loaded OK")
