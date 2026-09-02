"""Pillow plugin for Amiga Workbench .info icon files.

Registers the WBINFO format so that ``Image.open("icon.info")`` works
after ``import amigainfo``.
"""

from __future__ import annotations

import struct

from PIL import Image, ImageFile

from .load import load
from .palettes import WB_1X, WB_2X
from .render import (
    argb_to_image,
    classic_to_image,
    coloricon_to_image,
    newicon_to_image,
    png_to_image,
)

_RENDER = {
    "png": png_to_image,
    "argb": argb_to_image,
    "coloricon": coloricon_to_image,
    "newicon": newicon_to_image,
}


def _accept(prefix):
    return prefix[:2] == b"\xe3\x10" or prefix[:4] == b"\x89PNG"


def _is_powericon(data: bytes) -> bool:
    """Return whether PNG data contains PowerIcon metadata or a second PNG."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False

    pos = 8
    while pos + 12 <= len(data):
        chunk_len = struct.unpack_from(">I", data, pos)[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_end = pos + 12 + chunk_len
        if chunk_end > len(data):
            return False
        if chunk_type == b"icOn":
            return True
        if chunk_type == b"IEND":
            return data[chunk_end : chunk_end + 8] == b"\x89PNG\r\n\x1a\n"
        pos = chunk_end

    return False


def _build_frames(obj):
    """Build ordered frame list: best-first, normal then selected per generation."""
    frames = []

    generators = []
    if obj.png:
        generators.append(("png", obj.png))
    if obj.argb:
        generators.append(("argb", obj.argb))
    if obj.coloricon:
        generators.append(("coloricon", obj.coloricon))
    if obj.newicon:
        generators.append(("newicon", obj.newicon))
    if obj.classic:
        generators.append(("classic", obj.classic))

    for kind, images in generators:
        if kind == "classic":
            palette = WB_1X if not (obj.gadget.user_data & 0xFF) else WB_2X
            frames.append(classic_to_image(images.normal, palette))
        else:
            frames.append(_RENDER[kind](images.normal))

        selected = getattr(images, "selected", None)
        if selected:
            if kind == "classic":
                frames.append(classic_to_image(selected, palette))
            else:
                frames.append(_RENDER[kind](selected))

    return frames


class WBInfoFile(ImageFile.ImageFile):
    format = "WBINFO"
    format_description = "Amiga Workbench Icon"

    def _open(self):
        data = self.fp.read()
        if not (data.startswith(b"\xe3\x10") or _is_powericon(data)):
            raise SyntaxError("Not an Amiga icon")
        obj = load(data)
        self._disk_object = obj
        self.info["disk_object"] = obj

        self._frames = _build_frames(obj)
        if not self._frames:
            raise SyntaxError("No image data in icon")

        self._frame = 0
        self._n_frames = len(self._frames)
        self.is_animated = self._n_frames > 1
        first = self._frames[0]
        self._size = first.size
        self._mode = first.mode

    @property
    def n_frames(self):
        return self._n_frames

    def seek(self, frame):
        if not self._seek_check(frame):
            return
        self._frame = frame

    def tell(self):
        return self._frame

    def load(self):
        if self._frame >= len(self._frames):
            raise EOFError("no more frames")
        im = self._frames[self._frame]
        self.im = im.im.copy()
        self._size = im.size
        self._mode = im.mode
        return self.im


Image.register_open(WBInfoFile.format, WBInfoFile, _accept)
Image.register_extension(WBInfoFile.format, ".info")
# PowerIcons share the PNG signature, so inspect them before Pillow's generic
# PNG loader. Ordinary PNG files are rejected by _open and continue to PNG.
Image.ID.remove(WBInfoFile.format)
Image.ID.insert(0, WBInfoFile.format)
