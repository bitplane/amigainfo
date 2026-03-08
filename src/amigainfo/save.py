"""Write DiskObject dataclasses back to Amiga .info file bytes."""

from __future__ import annotations

import struct
import zlib

from .models import (
    ARGBImages,
    ClassicImage,
    ColorIconImage,
    ColorIconImages,
    DiskObject,
    DrawerData,
    Gadget,
    NewIconImage,
    NewIconImages,
)

MAGIC = 0xE310


def save(obj: DiskObject) -> bytes:
    """Serialize a DiskObject to Amiga .info file bytes.

    Args:
        obj: A DiskObject to serialize.

    Returns:
        Raw bytes of the .info file.
    """
    if obj.png:
        return _save_png_icon(obj)

    parts: list[bytes] = []

    # Merge NewIcon data into tooltypes
    tooltypes = _merge_newicon_tooltypes(obj.tooltypes, obj.newicon)

    # DiskObject header (78 bytes)
    has_default_tool = 1 if obj.default_tool is not None else 0
    has_tooltypes = 1 if tooltypes else 0
    has_drawer_data = 1 if obj.drawer_data is not None else 0
    has_tool_window = 1 if obj.tool_window is not None else 0

    gadget = obj.gadget

    parts.append(struct.pack(">HH", obj.magic, obj.version))
    parts.append(_write_gadget(gadget))
    parts.append(struct.pack(">BB", int(obj.type), 0))  # type + padding
    parts.append(struct.pack(">II", has_default_tool, has_tooltypes))
    parts.append(struct.pack(">ii", obj.current_x, obj.current_y))
    parts.append(struct.pack(">II", has_drawer_data, has_tool_window))
    parts.append(struct.pack(">i", obj.stack_size))

    # DrawerData
    if obj.drawer_data:
        parts.append(_write_drawer_data(obj.drawer_data))

    # Classic images
    if obj.classic:
        parts.append(_write_classic_image(obj.classic.normal))
        if obj.classic.selected:
            parts.append(_write_classic_image(obj.classic.selected))

    # DefaultTool
    if obj.default_tool is not None:
        parts.append(_write_text(obj.default_tool))

    # ToolTypes
    if tooltypes:
        parts.append(_write_tooltypes(tooltypes))

    # ToolWindow
    if obj.tool_window is not None:
        parts.append(_write_text(obj.tool_window))

    # DrawerData2
    if obj.drawer_data and (gadget.user_data & 0xFF):
        parts.append(struct.pack(">I", obj.drawer_data.flags))
        parts.append(struct.pack(">H", obj.drawer_data.view_modes))

    # FORM ICON
    if obj.coloricon or obj.argb:
        parts.append(_write_form_icon(obj.coloricon, obj.argb))

    return b"".join(parts)


def _write_gadget(g: Gadget) -> bytes:
    """Pack the 44-byte Gadget structure. Zeros for memory-only pointer fields."""
    return struct.pack(
        ">IhhhhHHHIIIiIHI",
        0,  # ga_Next (pointer, ignored)
        g.left_edge,
        g.top_edge,
        g.width,
        g.height,
        g.flags,
        g.activation,
        g.gadget_type,
        g.gadget_render,
        g.select_render,
        0,  # ga_GadgetText (pointer, ignored)
        0,  # ga_MutualExclude
        0,  # ga_SpecialInfo (pointer, ignored)
        0,  # ga_GadgetID
        g.user_data,
    )


def _write_drawer_data(dd: DrawerData) -> bytes:
    """Pack DrawerData (56 bytes). 38 zero bytes for NewWindow internals."""
    parts = struct.pack(">hhhhBB", dd.left_edge, dd.top_edge, dd.width, dd.height, dd.detail_pen, dd.block_pen)
    parts += b"\x00" * 38  # NewWindow internals (IDCMPFlags, FirstGadget, etc.)
    parts += struct.pack(">ii", dd.current_x, dd.current_y)
    return parts


def _write_classic_image(img: ClassicImage) -> bytes:
    """Pack a classic Image header (20 bytes) + plane data."""
    h = img.header
    header = struct.pack(
        ">hhhhhIBBI",
        h.left_edge,
        h.top_edge,
        h.width,
        h.height,
        h.depth,
        0,  # ImageData pointer (ignored)
        h.plane_pick,
        h.plane_on_off,
        0,  # NextImage pointer (ignored)
    )
    return header + b"".join(img.planes)


def _write_text(s: str) -> bytes:
    """Pack a length-prefixed string (ULONG length including null + text + null)."""
    encoded = s.encode("latin-1") + b"\x00"
    return struct.pack(">I", len(encoded)) + encoded


def _write_tooltypes(tooltypes: list[str]) -> bytes:
    """Pack the ToolTypes array."""
    count_field = (len(tooltypes) + 1) * 4
    parts = [struct.pack(">I", count_field)]
    for tt in tooltypes:
        parts.append(_write_text(tt))
    return b"".join(parts)


def _merge_newicon_tooltypes(tooltypes: list[str], newicon: NewIconImages | None) -> list[str]:
    """Merge NewIcon data into tooltypes, replacing existing IM1=/IM2= entries."""
    # Strip existing NewIcon entries
    result = [tt for tt in tooltypes if not tt.startswith(("IM1=", "IM2="))]

    if not newicon:
        return result

    # Re-encode NewIcon images
    im1_lines = _encode_newicon_image(newicon.normal)
    result.extend(f"IM1={line}" for line in im1_lines)

    if newicon.selected:
        im2_lines = _encode_newicon_image(newicon.selected)
        result.extend(f"IM2={line}" for line in im2_lines)

    return result


def _encode_newicon_image(img: NewIconImage) -> list[str]:
    """Encode a NewIconImage into tooltype lines (without IM1=/IM2= prefix)."""
    num_colors = len(img.palette)

    # Header: transparency flag, width, height, color count (2 chars)
    transparent_char = chr(0x42) if img.transparent else chr(0x20)
    width_char = chr(img.width + 0x21)
    height_char = chr(img.height + 0x21)
    colors_hi = chr((num_colors >> 6) + 0x21)
    colors_lo = chr((num_colors & 0x3F) + 0x21)

    # Bit depth for pixel data
    bit_depth = 1
    while (1 << bit_depth) < num_colors:
        bit_depth += 1

    # Encode palette + pixel data as one continuous bitstream.
    # The decoder concatenates all lines into a single bitstream, so we must not
    # introduce padding bits between palette and pixels or between lines.
    all_bits: list[int] = []
    for r, g, b in img.palette:
        for val in (r, g, b):
            for i in range(7, -1, -1):
                all_bits.append((val >> i) & 1)
    for px in img.pixel_data:
        for i in range(bit_depth - 1, -1, -1):
            all_bits.append((px >> i) & 1)

    all_chars = _newicon_encode_bits(all_bits)
    header = transparent_char + width_char + height_char + colors_hi + colors_lo

    lines = []
    max_data = 128 - len(header)
    lines.append(header + all_chars[:max_data])
    remaining = all_chars[max_data:]
    for i in range(0, len(remaining), 128):
        lines.append(remaining[i : i + 128])

    return lines


def _newicon_encode_bits(bits: list[int]) -> str:
    """Encode a list of bits into NewIcon 7-bit ASCII characters."""
    chars: list[str] = []
    for i in range(0, len(bits), 7):
        val = 0
        for j in range(7):
            val <<= 1
            if i + j < len(bits):
                val |= bits[i + j]
        # Map val (0-127) to character
        if val < 0x50:
            chars.append(chr(val + 0x20))
        else:
            chars.append(chr(val + 0x51))
    return "".join(chars)


# --- FORM ICON ---


def _write_form_icon(coloricon: ColorIconImages | None, argb: ARGBImages | None) -> bytes:
    """Write the FORM ICON IFF structure."""
    body = b""

    if coloricon:
        # FACE chunk
        face = coloricon.face
        aspect = ((face.aspect_x & 0x0F) << 4) | (face.aspect_y & 0x0F)
        face_data = struct.pack(
            ">BBBBH", face.width - 1, face.height - 1, face.flags, aspect, face.max_palette_bytes - 1
        )
        body += b"FACE" + struct.pack(">I", len(face_data)) + face_data
        # Pad to even
        if len(face_data) % 2:
            body += b"\x00"

        # IMAG chunks
        body += _write_imag_chunk(coloricon.normal)
        if coloricon.selected:
            body += _write_imag_chunk(coloricon.selected)

    if argb:
        body += _write_argb_chunk(argb.normal)
        if argb.selected:
            body += _write_argb_chunk(argb.selected)

    return b"FORM" + struct.pack(">I", len(body) + 4) + b"ICON" + body


def _write_imag_chunk(img: ColorIconImage) -> bytes:
    """Write a single IMAG chunk (uncompressed format=0)."""
    pixel_data = img.pixel_data
    palette_data = b""
    flags = 0
    if img.has_transparent:
        flags |= 1
    if img.palette:
        flags |= 2
        palette_data = b"".join(bytes(color) for color in img.palette)

    num_colors = len(img.palette) if img.palette else 0

    header = struct.pack(
        ">BBBBBBHH",
        img.transparent_color,
        max(num_colors - 1, 0),
        flags,
        0,  # format = uncompressed
        0,  # palette_format = uncompressed
        img.depth,
        len(pixel_data) - 1,
        len(palette_data) - 1 if palette_data else 0,
    )

    chunk_data = header + pixel_data + palette_data
    result = b"IMAG" + struct.pack(">I", len(chunk_data)) + chunk_data
    if len(chunk_data) % 2:
        result += b"\x00"
    return result


def _write_argb_chunk(img) -> bytes:
    """Write a single ARGB chunk (zlib-compressed)."""
    compressed = zlib.compress(img.data)
    # Header: ULONG ztype=1, ULONG zsize, UWORD reserved=0
    header = struct.pack(">IIH", 1, len(compressed) - 1, 0)
    chunk_data = header + compressed
    result = b"ARGB" + struct.pack(">I", len(chunk_data)) + chunk_data
    if len(chunk_data) % 2:
        result += b"\x00"
    return result


# --- OS4 PNG icon ---

# Reverse mapping of attribute names to icOn chunk tags
_ICON_TAG = {
    "current_x": 0x80001001,
    "current_y": 0x80001002,
    "dd_left_edge": 0x80001003,
    "dd_top_edge": 0x80001004,
    "dd_width": 0x80001005,
    "dd_height": 0x80001006,
    "dd_flags": 0x80001007,
    "tool_window": 0x80001008,
    "stack_size": 0x80001009,
    "default_tool": 0x8000100A,
    "tooltypes": 0x8000100B,
    "dd_view_modes": 0x8000100C,
    "dd_current_x": 0x8000100D,
    "dd_current_y": 0x8000100E,
    "type": 0x8000100F,
}

_ICON_STRING_TAGS = {"tool_window", "default_tool", "tooltypes"}


def _build_icon_chunk(obj: DiskObject) -> bytes:
    """Build the icOn PNG chunk data from DiskObject metadata."""
    parts: list[bytes] = []

    attrs: list[tuple[str, int | str]] = [
        ("type", int(obj.type)),
        ("current_x", obj.current_x),
        ("current_y", obj.current_y),
        ("stack_size", obj.stack_size),
    ]
    if obj.default_tool is not None:
        attrs.append(("default_tool", obj.default_tool))
    if obj.tool_window is not None:
        attrs.append(("tool_window", obj.tool_window))
    for tt in obj.tooltypes:
        attrs.append(("tooltypes", tt))
    if obj.drawer_data:
        dd = obj.drawer_data
        attrs.extend(
            [
                ("dd_left_edge", dd.left_edge),
                ("dd_top_edge", dd.top_edge),
                ("dd_width", dd.width),
                ("dd_height", dd.height),
                ("dd_flags", dd.flags),
                ("dd_view_modes", dd.view_modes),
                ("dd_current_x", dd.current_x),
                ("dd_current_y", dd.current_y),
            ]
        )

    for name, value in attrs:
        tag = _ICON_TAG[name]
        parts.append(struct.pack(">I", tag))
        if name in _ICON_STRING_TAGS:
            parts.append(str(value).encode("latin-1") + b"\x00")
        else:
            parts.append(struct.pack(">I", value))

    return b"".join(parts)


def _strip_icon_chunk(png_data: bytes) -> tuple[bytes, int]:
    """Remove any existing icOn chunk from PNG data.

    Returns (cleaned_png, iend_offset) where iend_offset is the offset
    of the IEND chunk in the cleaned data.
    """
    parts: list[bytes] = []
    parts.append(png_data[:8])  # PNG signature
    pos = 8
    iend_offset = 0
    while pos + 8 <= len(png_data):
        chunk_len = struct.unpack_from(">I", png_data, pos)[0]
        chunk_end = pos + 8 + chunk_len + 4  # header(8) + data + CRC(4)
        chunk_type = png_data[pos + 4 : pos + 8]
        if chunk_type == b"icOn":
            pos = chunk_end
            continue
        if chunk_type == b"IEND":
            iend_offset = len(b"".join(parts))
            parts.append(png_data[pos:chunk_end])
            break
        parts.append(png_data[pos:chunk_end])
        pos = chunk_end
    return b"".join(parts), iend_offset


def _make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk with type, data, and CRC."""
    raw = chunk_type + data
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + raw + struct.pack(">I", crc)


def _save_png_icon(obj: DiskObject) -> bytes:
    """Save an OS4 PNG icon (two concatenated PNGs with icOn metadata)."""
    png = obj.png
    normal, iend_offset = _strip_icon_chunk(png.normal)
    icon_chunk = _make_png_chunk(b"icOn", _build_icon_chunk(obj))

    # Insert icOn chunk before IEND
    result = normal[:iend_offset] + icon_chunk + normal[iend_offset:]

    if png.selected:
        result += png.selected

    return result
