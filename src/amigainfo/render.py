"""Render Amiga .info image data to Pillow Images."""

from __future__ import annotations

from PIL import Image

from .models import (
    ARGBImage,
    ClassicImage,
    ColorIconImage,
    DiskObject,
    NewIconImage,
)
from .palettes import DEFAULT, WB_1X, WB_2X


def to_image(obj: DiskObject, selected: bool = False) -> Image.Image:
    """Render the best available image from a DiskObject.

    Priority: ARGB > ColorIcon > NewIcon > Classic.
    Falls back to normal state if selected is not available.

    Args:
        obj: A loaded DiskObject.
        selected: If True, render the selected (highlighted) state.

    Returns:
        A Pillow Image in RGBA or RGB mode.

    Raises:
        ValueError: If no image data is available.
    """
    if obj.argb:
        img = obj.argb.selected if selected and obj.argb.selected else obj.argb.normal
        return argb_to_image(img)

    if obj.coloricon:
        img = obj.coloricon.selected if selected and obj.coloricon.selected else obj.coloricon.normal
        return coloricon_to_image(img)

    if obj.newicon:
        img = obj.newicon.selected if selected and obj.newicon.selected else obj.newicon.normal
        return newicon_to_image(img)

    if obj.classic:
        img = obj.classic.selected if selected and obj.classic.selected else obj.classic.normal
        palette = WB_1X if not (obj.gadget.user_data & 0xFF) else WB_2X
        return classic_to_image(img, palette)

    raise ValueError("No image data available in DiskObject")


def argb_to_image(img: ARGBImage) -> Image.Image:
    """Render an ARGB image to a Pillow RGBA Image.

    The raw data is in ARGB byte order; we swap to RGBA for Pillow.
    """
    # Swap ARGB → RGBA
    argb = img.data
    rgba = bytearray(len(argb))
    for i in range(0, len(argb), 4):
        rgba[i] = argb[i + 1]  # R
        rgba[i + 1] = argb[i + 2]  # G
        rgba[i + 2] = argb[i + 3]  # B
        rgba[i + 3] = argb[i]  # A
    return Image.frombytes("RGBA", (img.width, img.height), bytes(rgba))


def coloricon_to_image(img: ColorIconImage) -> Image.Image:
    """Render a ColorIcon/GlowIcon image to a Pillow RGBA Image."""
    pixels = bytearray(img.width * img.height * 4)
    for i, idx in enumerate(img.pixel_data):
        offset = i * 4
        if img.has_transparent and idx == img.transparent_color:
            pixels[offset : offset + 4] = b"\x00\x00\x00\x00"
        elif idx < len(img.palette):
            r, g, b = img.palette[idx]
            pixels[offset] = r
            pixels[offset + 1] = g
            pixels[offset + 2] = b
            pixels[offset + 3] = 255
        else:
            pixels[offset : offset + 4] = b"\x00\x00\x00\xff"
    return Image.frombytes("RGBA", (img.width, img.height), bytes(pixels))


def newicon_to_image(img: NewIconImage) -> Image.Image:
    """Render a NewIcon image to a Pillow RGBA Image."""
    pixels = bytearray(img.width * img.height * 4)
    for i, idx in enumerate(img.pixel_data):
        offset = i * 4
        if img.transparent and idx == 0:
            pixels[offset : offset + 4] = b"\x00\x00\x00\x00"
        elif idx < len(img.palette):
            r, g, b = img.palette[idx]
            pixels[offset] = r
            pixels[offset + 1] = g
            pixels[offset + 2] = b
            pixels[offset + 3] = 255
        else:
            pixels[offset : offset + 4] = b"\x00\x00\x00\xff"
    return Image.frombytes("RGBA", (img.width, img.height), bytes(pixels))


def classic_to_image(
    img: ClassicImage,
    palette: tuple[tuple[int, int, int], ...] | None = None,
) -> Image.Image:
    """Render a classic planar image to a Pillow RGB Image.

    Args:
        img: A ClassicImage with planar bitmap data.
        palette: Color palette to use. Defaults to the WB 2.x palette.
    """
    if palette is None:
        palette = DEFAULT

    header = img.header
    width = header.width
    height = header.height
    words_per_row = (width + 15) // 16
    bytes_per_row = words_per_row * 2

    pixels = bytearray(width * height * 3)

    for y in range(height):
        for x in range(width):
            byte_idx = y * bytes_per_row + (x >> 3)
            bit_idx = 7 - (x & 7)

            color_index = 0
            for plane_num in range(header.depth):
                if header.plane_pick & (1 << plane_num):
                    # This plane has data
                    plane_idx = bin(header.plane_pick & ((1 << (plane_num + 1)) - 1)).count("1") - 1
                    if plane_idx < len(img.planes):
                        bit = (img.planes[plane_idx][byte_idx] >> bit_idx) & 1
                        color_index |= bit << plane_num
                elif header.plane_on_off & (1 << plane_num):
                    color_index |= 1 << plane_num

            if color_index < len(palette):
                r, g, b = palette[color_index]
            else:
                r, g, b = 0, 0, 0

            offset = (y * width + x) * 3
            pixels[offset] = r
            pixels[offset + 1] = g
            pixels[offset + 2] = b

    return Image.frombytes("RGB", (width, height), bytes(pixels))
