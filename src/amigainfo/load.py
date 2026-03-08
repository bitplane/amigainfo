"""Load Amiga .info files into DiskObject dataclasses."""

from __future__ import annotations

import logging
import struct
import zlib

from .enums import IconType
from .models import (
    ARGBImage,
    ARGBImages,
    ClassicImage,
    ClassicImages,
    ColorIconImage,
    ColorIconImages,
    DiskObject,
    DrawerData,
    FaceChunk,
    Gadget,
    ImageHeader,
    NewIconImage,
    NewIconImages,
    PNGImages,
)

logger = logging.getLogger(__name__)

MAGIC = 0xE310


def load(data: bytes | bytearray) -> DiskObject:
    """Parse an Amiga .info file and return a DiskObject.

    Args:
        data: Raw bytes of the .info file.

    Returns:
        A DiskObject populated with all parsed data.

    Raises:
        ValueError: If the file doesn't start with the expected magic number.
    """
    if len(data) >= 4 and data[:4] == b"\x89PNG":
        return _load_png_icon(data)

    data = memoryview(data) if not isinstance(data, memoryview) else data
    pos = 0

    # DiskObject header (78 bytes)
    magic, version = struct.unpack_from(">HH", data, pos)
    if magic != MAGIC:
        raise ValueError(f"Not an Amiga .info file: magic 0x{magic:04X}, expected 0x{MAGIC:04X}")
    pos += 4

    gadget, pos = _read_gadget(data, pos)
    icon_type_raw = data[pos]
    pos += 2  # type + padding

    has_default_tool, has_tooltypes = struct.unpack_from(">II", data, pos)
    pos += 8
    current_x, current_y = struct.unpack_from(">ii", data, pos)
    pos += 8
    has_drawer_data, has_tool_window = struct.unpack_from(">II", data, pos)
    pos += 8
    (stack_size,) = struct.unpack_from(">i", data, pos)
    pos += 4

    # DrawerData
    drawer_data = None
    if has_drawer_data:
        drawer_data, pos = _read_drawer_data(data, pos, gadget.user_data)

    # Classic images
    classic = None
    normal_image = None
    if gadget.gadget_render:
        normal_image, pos = _read_classic_image(data, pos)

    selected_image = None
    if gadget.select_render:
        selected_image, pos = _read_classic_image(data, pos)

    if normal_image:
        classic = ClassicImages(normal=normal_image, selected=selected_image)

    # DefaultTool
    default_tool = None
    if has_default_tool and pos < len(data):
        default_tool, pos = _read_text(data, pos)

    # ToolTypes
    tooltypes: list[str] = []
    if has_tooltypes and pos < len(data):
        tooltypes, pos = _read_tooltypes(data, pos)

    # ToolWindow
    tool_window = None
    if has_tool_window and pos < len(data):
        tool_window, pos = _read_text(data, pos)

    # DrawerData2 (OS 2.x+)
    if has_drawer_data and (gadget.user_data & 0xFF):
        if drawer_data and pos + 6 <= len(data):
            drawer_data.flags = struct.unpack_from(">I", data, pos)[0]
            pos += 4
            drawer_data.view_modes = struct.unpack_from(">H", data, pos)[0]
            pos += 2

    # NewIcons (from ToolTypes)
    newicon = _read_newicons(tooltypes)

    # FORM ICON (GlowIcons / ARGB)
    coloricon = None
    argb = None
    form_pos = _find_form_icon(data, pos)
    if form_pos is not None:
        face_width = gadget.width if classic is None else classic.normal.header.width
        face_height = gadget.height if classic is None else classic.normal.header.height
        coloricon, argb = _read_form_icon(data, form_pos, face_width, face_height)

    return DiskObject(
        magic=magic,
        version=version,
        type=IconType(icon_type_raw) if icon_type_raw in IconType.__members__.values() else icon_type_raw,
        gadget=gadget,
        default_tool=default_tool,
        tool_window=tool_window,
        tooltypes=tooltypes,
        current_x=current_x,
        current_y=current_y,
        stack_size=stack_size,
        drawer_data=drawer_data,
        classic=classic,
        newicon=newicon,
        coloricon=coloricon,
        argb=argb,
    )


def _read_gadget(data: memoryview, pos: int) -> tuple[Gadget, int]:
    """Read the 44-byte embedded Gadget structure."""
    (
        _next,
        left_edge,
        top_edge,
        width,
        height,
        flags,
        activation,
        gadget_type,
        gadget_render,
        select_render,
        _gadget_text,
        _mutual_exclude,
        _special_info,
        gadget_id,
        user_data,
    ) = struct.unpack_from(">IhhhhHHHIIIiIHI", data, pos)

    return Gadget(
        left_edge=left_edge,
        top_edge=top_edge,
        width=width,
        height=height,
        flags=flags,
        activation=activation,
        gadget_type=gadget_type,
        gadget_render=gadget_render,
        select_render=select_render,
        user_data=user_data,
    ), pos + 44


def _read_drawer_data(data: memoryview, pos: int, user_data: int) -> tuple[DrawerData, int]:
    """Read DrawerData (56 bytes: NewWindow + scroll offsets)."""
    (
        left_edge,
        top_edge,
        width,
        height,
        detail_pen,
        block_pen,
    ) = struct.unpack_from(">hhhhBB", data, pos)

    # Skip the rest of NewWindow (42 bytes from offset 10 to 48)
    # then read scroll offsets
    current_x, current_y = struct.unpack_from(">ii", data, pos + 48)

    return DrawerData(
        left_edge=left_edge,
        top_edge=top_edge,
        width=width,
        height=height,
        detail_pen=detail_pen,
        block_pen=block_pen,
        current_x=current_x,
        current_y=current_y,
    ), pos + 56


def _read_classic_image(data: memoryview, pos: int) -> tuple[ClassicImage | None, int]:
    """Read an Image header (20 bytes) and its planar bitmap data."""
    if pos + 20 > len(data):
        logger.warning("truncated image header at offset %d", pos)
        return None, len(data)

    (
        left_edge,
        top_edge,
        width,
        height,
        depth,
        _image_data_ptr,
        plane_pick,
        plane_on_off,
        _next,
    ) = struct.unpack_from(">hhhhhIBBI", data, pos)
    pos += 20

    if width <= 0 or height <= 0 or depth <= 0 or depth > 8:
        logger.warning("invalid image dimensions %dx%d depth=%d", width, height, depth)
        return None, pos

    header = ImageHeader(
        left_edge=left_edge,
        top_edge=top_edge,
        width=width,
        height=height,
        depth=depth,
        plane_pick=plane_pick,
        plane_on_off=plane_on_off,
    )

    # Planar data: each row padded to 16-bit word boundary
    words_per_row = (width + 15) // 16
    bytes_per_row = words_per_row * 2
    plane_size = bytes_per_row * height

    if pos + plane_size * depth > len(data):
        logger.warning(
            "truncated image plane data at offset %d (need %d bytes, have %d)", pos, plane_size * depth, len(data) - pos
        )
        return None, len(data)

    planes = []
    for _ in range(depth):
        plane_bytes = bytes(data[pos : pos + plane_size])
        planes.append(plane_bytes)
        pos += plane_size

    return ClassicImage(header=header, planes=planes), pos


def _read_text(data: memoryview, pos: int) -> tuple[str | None, int]:
    """Read a length-prefixed string (ULONG size + text + zero byte)."""
    if pos + 4 > len(data):
        logger.warning("truncated string length at offset %d", pos)
        return None, len(data)

    (length,) = struct.unpack_from(">I", data, pos)
    pos += 4

    if length > len(data) - pos:
        logger.warning("truncated string data at offset %d (need %d bytes, have %d)", pos, length, len(data) - pos)
        return None, len(data)

    text = bytes(data[pos : pos + length]).rstrip(b"\x00").decode("latin-1")
    pos += length
    return text, pos


def _read_tooltypes(data: memoryview, pos: int) -> tuple[list[str], int]:
    """Read the ToolTypes array.

    Format: ULONG count_field (where entries = count_field/4 - 1),
    followed by that many length-prefixed strings.
    """
    if pos + 4 > len(data):
        logger.warning("truncated tooltypes count at offset %d", pos)
        return [], len(data)

    (count_field,) = struct.unpack_from(">I", data, pos)
    pos += 4

    tooltypes: list[str] = []
    if count_field:
        num_entries = count_field // 4 - 1
        for _ in range(num_entries):
            text, pos = _read_text(data, pos)
            if text is None:
                break
            tooltypes.append(text)

    return tooltypes, pos


# --- NewIcons decoding ---


def _read_newicons(tooltypes: list[str]) -> NewIconImages | None:
    """Extract and decode NewIcon images from ToolTypes strings."""
    im1_lines: list[str] = []
    im2_lines: list[str] = []

    for tt in tooltypes:
        if tt.startswith("IM1="):
            im1_lines.append(tt[4:])
        elif tt.startswith("IM2="):
            im2_lines.append(tt[4:])

    if not im1_lines:
        return None

    normal = _decode_newicon_image(im1_lines)
    selected = _decode_newicon_image(im2_lines) if im2_lines else None
    return NewIconImages(normal=normal, selected=selected)


def _newicon_decode_bits(line: str) -> list[int]:
    """Decode a NewIcons ASCII line into a list of 7-bit values.

    Returns a flat list of bits (as 0/1 integers).
    """
    bits: list[int] = []
    for ch in line:
        byte = ord(ch)
        if byte < 0x20:
            continue
        if byte <= 0x6F:
            val = byte - 0x20
            for i in range(6, -1, -1):
                bits.append((val >> i) & 1)
        elif 0xA1 <= byte <= 0xD0:
            val = byte - 0x51
            for i in range(6, -1, -1):
                bits.append((val >> i) & 1)
        elif byte >= 0xD1:
            # RLE: (byte - 0xD0) * 7 zero bits
            bits.extend([0] * ((byte - 0xD0) * 7))
    return bits


def _bits_to_int(bits: list[int], offset: int, count: int) -> int:
    """Extract an integer from a bit list."""
    val = 0
    for i in range(count):
        if offset + i < len(bits):
            val = (val << 1) | bits[offset + i]
        else:
            val <<= 1
    return val


def _decode_newicon_image(lines: list[str]) -> NewIconImage:
    """Decode a single NewIcon image from its IM1=/IM2= lines."""
    first_line = lines[0]

    transparent = ord(first_line[0]) == 0x42  # 'B'
    width = ord(first_line[1]) - 0x21
    height = ord(first_line[2]) - 0x21
    num_colors = ((ord(first_line[3]) - 0x21) << 6) + (ord(first_line[4]) - 0x21)

    # Bit depth for pixel data
    bit_depth = 1
    while (1 << bit_depth) < num_colors:
        bit_depth += 1

    # Decode all lines into one continuous bitstream (palette then pixels)
    all_bits: list[int] = []
    all_bits.extend(_newicon_decode_bits(first_line[5:]))
    for line in lines[1:]:
        all_bits.extend(_newicon_decode_bits(line))

    bit_pos = 0

    # Read palette (num_colors * 24 bits)
    palette: list[tuple[int, int, int]] = []
    for _ in range(num_colors):
        if bit_pos + 24 > len(all_bits):
            break
        r = _bits_to_int(all_bits, bit_pos, 8)
        g = _bits_to_int(all_bits, bit_pos + 8, 8)
        b = _bits_to_int(all_bits, bit_pos + 16, 8)
        palette.append((r, g, b))
        bit_pos += 24

    # Read pixel data from remaining bits
    total_pixels = width * height
    pixels: list[int] = []
    while (bit_pos + bit_depth <= len(all_bits)) and (len(pixels) < total_pixels):
        pixels.append(_bits_to_int(all_bits, bit_pos, bit_depth))
        bit_pos += bit_depth

    return NewIconImage(
        width=width,
        height=height,
        transparent=transparent,
        palette=palette,
        pixel_data=pixels,
    )


# --- FORM ICON (GlowIcons / OS 3.5+) ---


def _find_form_icon(data: memoryview, start: int) -> int | None:
    """Search for FORM ICON in the data from the given start position."""
    raw = bytes(data) if isinstance(data, memoryview) else data
    pos = start
    while True:
        idx = raw.find(b"FORM", pos)
        if idx < 0 or idx + 12 > len(raw):
            return None
        if raw[idx + 8 : idx + 12] == b"ICON":
            return idx
        pos = idx + 4


def _read_form_icon(
    data: memoryview, pos: int, default_width: int, default_height: int
) -> tuple[ColorIconImages | None, ARGBImages | None]:
    """Parse IFF FORM ICON chunks (FACE, IMAG, ARGB)."""
    # Skip FORM header
    form_size = struct.unpack_from(">I", data, pos + 4)[0]
    end = pos + 8 + form_size
    pos += 12  # past "FORM" + size + "ICON"

    face = None
    imag_images: list[ColorIconImage] = []
    argb_images: list[ARGBImage] = []
    icon_width = default_width
    icon_height = default_height

    while pos + 8 <= end:
        chunk_name = bytes(data[pos : pos + 4]).decode("ascii", errors="replace")
        chunk_size = struct.unpack_from(">I", data, pos + 4)[0]
        chunk_data_start = pos + 8
        pos = chunk_data_start + chunk_size
        # IFF chunks are padded to even size
        if chunk_size % 2:
            pos += 1

        if chunk_name == "FACE":
            fc_width = data[chunk_data_start] + 1
            fc_height = data[chunk_data_start + 1] + 1
            fc_flags = data[chunk_data_start + 2]
            fc_aspect = data[chunk_data_start + 3]
            fc_max_pal = struct.unpack_from(">H", data, chunk_data_start + 4)[0] + 1
            face = FaceChunk(
                width=fc_width,
                height=fc_height,
                flags=fc_flags,
                aspect_x=(fc_aspect >> 4) & 0x0F,
                aspect_y=fc_aspect & 0x0F,
                max_palette_bytes=fc_max_pal,
            )
            icon_width = fc_width
            icon_height = fc_height

        elif chunk_name == "IMAG":
            img = _read_imag_chunk(data, chunk_data_start, icon_width, icon_height)
            # If no palette, reuse previous image's palette
            if not img.palette and imag_images:
                img.palette = list(imag_images[0].palette)
            imag_images.append(img)

        elif chunk_name == "ARGB":
            argb_img = _read_argb_chunk(data, chunk_data_start, chunk_size, icon_width, icon_height)
            if argb_img:
                argb_images.append(argb_img)

    coloricon = None
    if face and imag_images:
        coloricon = ColorIconImages(
            face=face,
            normal=imag_images[0],
            selected=imag_images[1] if len(imag_images) > 1 else None,
        )

    argb = None
    if argb_images:
        argb = ARGBImages(
            normal=argb_images[0],
            selected=argb_images[1] if len(argb_images) > 1 else None,
        )

    return coloricon, argb


def _read_imag_chunk(data: memoryview, pos: int, width: int, height: int) -> ColorIconImage:
    """Parse a single IMAG chunk."""
    transparent_color = data[pos]
    num_colors = data[pos + 1] + 1
    flags = data[pos + 2]
    image_format = data[pos + 3]
    palette_format = data[pos + 4]
    depth = data[pos + 5]
    image_size = (data[pos + 6] << 8 | data[pos + 7]) + 1
    palette_size = (data[pos + 8] << 8 | data[pos + 9]) + 1
    pos += 10

    has_transparent = bool(flags & 1)
    has_palette = bool(flags & 2)

    # Decode image data
    image_data_raw = bytes(data[pos : pos + image_size])
    if image_format == 1:  # RLE compressed
        pixels = _decode_rle(image_data_raw, depth, width * height)
    else:  # Uncompressed (one byte per pixel)
        pixels = image_data_raw

    # Decode palette
    palette: list[tuple[int, int, int]] = []
    if has_palette:
        palette_data_raw = bytes(data[pos + image_size : pos + image_size + palette_size])
        if palette_format == 1:  # RLE compressed
            rgb_bytes = _decode_rle(palette_data_raw, 8, num_colors * 3)
        else:
            rgb_bytes = palette_data_raw

        for i in range(0, len(rgb_bytes) - 2, 3):
            palette.append((rgb_bytes[i], rgb_bytes[i + 1], rgb_bytes[i + 2]))

    return ColorIconImage(
        width=width,
        height=height,
        transparent_color=transparent_color,
        has_transparent=has_transparent,
        depth=depth,
        palette=palette,
        pixel_data=pixels,
    )


def _decode_rle(data: bytes, depth: int, expected_count: int) -> bytes:
    """Decode OS 3.5 RLE-compressed bit stream.

    The RLE operates on a bit stream where entries are `depth` bits wide,
    but RLE control bytes are always 8 bits.
    """
    total_bits = len(data) * 8
    bit_pos = 0
    result: list[int] = []

    def read_bits(nbits: int) -> int:
        nonlocal bit_pos
        val = 0
        for _ in range(nbits):
            if bit_pos >= total_bits:
                break
            byte_idx = bit_pos >> 3
            bit_idx = 7 - (bit_pos & 7)
            val = (val << 1) | ((data[byte_idx] >> bit_idx) & 1)
            bit_pos += 1
        return val

    while bit_pos + 8 <= total_bits and len(result) < expected_count:
        control = read_bits(8)

        if control == 0x80:
            continue
        elif control <= 0x7F:
            # Literal: copy next (control + 1) entries
            for _ in range(control + 1):
                if len(result) >= expected_count:
                    break
                result.append(read_bits(depth))
        else:
            # Run: repeat next entry (257 - control) times
            val = read_bits(depth)
            count = 257 - control
            for _ in range(count):
                if len(result) >= expected_count:
                    break
                result.append(val)

    return bytes(result)


def _read_argb_chunk(data: memoryview, pos: int, chunk_size: int, width: int, height: int) -> ARGBImage | None:
    """Parse an ARGB chunk (zlib-compressed 32-bit image data)."""
    # Header: ULONG ztype(1), ULONG zsize, UWORD reserved
    # The JS reference just skips 10 bytes
    header_size = 10
    if chunk_size <= header_size:
        return None

    compressed = bytes(data[pos + header_size : pos + chunk_size])

    try:
        raw = zlib.decompress(compressed)
    except zlib.error:
        return None

    return ARGBImage(width=width, height=height, data=raw)


# --- OS4 PNG icon ---

# icOn chunk attribute tags
_ICON_ATTR = {
    0x80001001: "current_x",
    0x80001002: "current_y",
    0x80001003: "dd_left_edge",
    0x80001004: "dd_top_edge",
    0x80001005: "dd_width",
    0x80001006: "dd_height",
    0x80001007: "dd_flags",
    0x80001008: "tool_window",
    0x80001009: "stack_size",
    0x8000100A: "default_tool",
    0x8000100B: "tooltypes",
    0x8000100C: "dd_view_modes",
    0x8000100D: "dd_current_x",
    0x8000100E: "dd_current_y",
    0x8000100F: "type",
}

_ICON_STRING_ATTRS = {"tool_window", "default_tool", "tooltypes"}


def _parse_icon_chunk(chunk_data: bytes) -> dict:
    """Parse attribute tags from an icOn PNG chunk."""
    attrs: dict = {}
    pos = 0
    while pos + 8 <= len(chunk_data):
        tag = struct.unpack_from(">I", chunk_data, pos)[0]
        pos += 4
        name = _ICON_ATTR.get(tag)
        if name is None:
            break
        if name in _ICON_STRING_ATTRS:
            end = chunk_data.index(b"\x00", pos)
            value = chunk_data[pos:end].decode("latin-1")
            pos = end + 1
            if name == "tooltypes":
                attrs.setdefault("tooltypes", []).append(value)
            else:
                attrs[name] = value
        else:
            value = struct.unpack_from(">I", chunk_data, pos)[0]
            pos += 4
            attrs[name] = value
    return attrs


def _strip_png_chunk(png_data: bytes, chunk_type: bytes) -> bytes:
    """Remove all instances of a chunk type from PNG data."""
    parts = [png_data[:8]]
    pos = 8
    while pos + 8 <= len(png_data):
        chunk_len = struct.unpack_from(">I", png_data, pos)[0]
        ct = png_data[pos + 4 : pos + 8]
        chunk_end = pos + 8 + chunk_len + 4
        if ct != chunk_type:
            parts.append(png_data[pos:chunk_end])
        pos = chunk_end
    return b"".join(parts)


def _load_png_icon(data: bytes | bytearray) -> DiskObject:
    """Load an OS4 PNG icon (two concatenated PNGs with icOn metadata chunk)."""
    # Read width/height from IHDR (always at offset 8)
    width, height = struct.unpack_from(">II", data, 16)

    # Walk PNG chunks to find icOn and IEND
    icon_attrs: dict = {}
    iend_end = len(data)
    pos = 8  # skip PNG signature
    while pos + 8 <= len(data):
        chunk_len = struct.unpack_from(">I", data, pos)[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data_start = pos + 8
        chunk_end = chunk_data_start + chunk_len + 4  # +4 for CRC

        if chunk_type == b"icOn":
            icon_attrs = _parse_icon_chunk(data[chunk_data_start : chunk_data_start + chunk_len])

        if chunk_type == b"IEND":
            iend_end = chunk_end
            break

        pos = chunk_end

    # Split into first and second PNG, stripping icOn chunk from stored data
    # (metadata is already extracted into DiskObject fields)
    first_png = _strip_png_chunk(bytes(data[:iend_end]), b"icOn")
    remainder = bytes(data[iend_end:])
    second_png = remainder if remainder and remainder[:4] == b"\x89PNG" else None

    # Build DiskObject from icOn attributes
    icon_type_raw = icon_attrs.get("type", IconType.TOOL)
    icon_type = IconType(icon_type_raw) if icon_type_raw in IconType.__members__.values() else icon_type_raw

    drawer_data = None
    dd_keys = {
        "dd_left_edge",
        "dd_top_edge",
        "dd_width",
        "dd_height",
        "dd_flags",
        "dd_view_modes",
        "dd_current_x",
        "dd_current_y",
    }
    if dd_keys & icon_attrs.keys():
        drawer_data = DrawerData(
            left_edge=icon_attrs.get("dd_left_edge", 0),
            top_edge=icon_attrs.get("dd_top_edge", 0),
            width=icon_attrs.get("dd_width", 0),
            height=icon_attrs.get("dd_height", 0),
            flags=icon_attrs.get("dd_flags", 0),
            view_modes=icon_attrs.get("dd_view_modes", 0),
            current_x=icon_attrs.get("dd_current_x", 0),
            current_y=icon_attrs.get("dd_current_y", 0),
        )

    return DiskObject(
        magic=0x89504E47,
        type=icon_type,
        gadget=Gadget(width=width, height=height),
        default_tool=icon_attrs.get("default_tool"),
        tool_window=icon_attrs.get("tool_window"),
        tooltypes=icon_attrs.get("tooltypes", []),
        current_x=icon_attrs.get("current_x", 0),
        current_y=icon_attrs.get("current_y", 0),
        stack_size=icon_attrs.get("stack_size", 0),
        drawer_data=drawer_data,
        png=PNGImages(normal=first_png, selected=second_png),
    )
