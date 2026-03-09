from pathlib import Path

import pytest
from PIL import Image

from amigainfo import load
from amigainfo.render import (
    argb_to_image,
    classic_to_image,
    coloricon_to_image,
    newicon_to_image,
    png_to_image,
    to_image,
)
from amigainfo.palettes import WB_1X, WB_2X

TEST_ICONS = Path(__file__).resolve().parent / "test-icons"


def load_file(name):
    return load((TEST_ICONS / name).read_bytes())


# --- to_image (best available) ---


def all_info_files():
    return sorted(TEST_ICONS.rglob("*.info"))


@pytest.fixture(params=all_info_files(), ids=lambda p: str(p.relative_to(TEST_ICONS)))
def icon_path(request):
    return request.param


def test_to_image_all_files(icon_path):
    obj = load(icon_path.read_bytes())
    img = to_image(obj)
    assert isinstance(img, Image.Image)
    assert img.size[0] > 0
    assert img.size[1] > 0


# --- ARGB rendering ---


def test_argb_renders_rgba():
    obj = load_file("OS4/drawer.info")
    img = argb_to_image(obj.argb.normal)
    assert img.mode == "RGBA"
    assert img.size == (64, 64)


def test_argb_pixel_not_all_zero():
    obj = load_file("OS4/drawer.info")
    img = argb_to_image(obj.argb.normal)
    assert img.tobytes() != b"\x00" * (64 * 64 * 4)


# --- ColorIcon rendering ---


def test_coloricon_renders_rgba():
    obj = load_file("ColorIcons/AmigaMail.info")
    img = coloricon_to_image(obj.coloricon.normal)
    assert img.mode == "RGBA"
    assert img.size == (48, 48)


def test_coloricon_has_nonzero_pixels():
    obj = load_file("ColorIcons/AmigaMail.info")
    img = coloricon_to_image(obj.coloricon.normal)
    assert img.tobytes() != b"\x00" * (48 * 48 * 4)


# --- NewIcon rendering ---


def test_newicon_renders_rgba():
    obj = load_file("Newicons/0016.info")
    img = newicon_to_image(obj.newicon.normal)
    assert img.mode == "RGBA"
    assert img.size == (42, 42)


def test_newicon_transparency():
    obj = load_file("Newicons/0016.info")
    assert obj.newicon.normal.transparent
    img = newicon_to_image(obj.newicon.normal)
    # Should have some transparent pixels (index 0)
    alpha = img.split()[3]
    assert 0 in list(alpha.tobytes())


# --- Classic rendering ---


def test_classic_renders_rgba():
    obj = load_file("OS1.3/Disk.info")
    img = classic_to_image(obj.classic.normal)
    assert img.mode == "RGBA"
    assert img.size == (35, 16)
    # Background color (index at 0,0) should be transparent
    alpha = img.split()[3]
    assert 0 in list(alpha.tobytes())


def test_classic_wb1x_palette():
    obj = load_file("OS1.3/Disk.info")
    img = classic_to_image(obj.classic.normal, WB_1X)
    assert img.mode == "RGBA"


def test_classic_wb2x_palette():
    obj = load_file("MUI/Disk.info")
    img = classic_to_image(obj.classic.normal, WB_2X)
    assert img.mode == "RGBA"
    assert img.size == (44, 23)


def test_classic_3_bitplane():
    obj = load_file("MUI/Disk.info")
    assert obj.classic.normal.header.depth == 3
    img = classic_to_image(obj.classic.normal, WB_2X)
    assert img.size == (44, 23)


# --- to_image priority ---


def test_to_image_prefers_argb():
    obj = load_file("OS4/drawer.info")
    assert obj.argb is not None
    img = to_image(obj)
    assert img.mode == "RGBA"
    assert img.size == (64, 64)


def test_to_image_prefers_coloricon_over_classic():
    obj = load_file("ColorIcons/AmigaMail.info")
    assert obj.coloricon is not None
    img = to_image(obj)
    # Should use coloricon dimensions, not classic
    assert img.size == (48, 48)


def test_to_image_prefers_newicon_over_classic():
    obj = load_file("Newicons/0016.info")
    assert obj.newicon is not None
    img = to_image(obj)
    assert img.size == (42, 42)


def test_to_image_falls_back_to_classic():
    obj = load_file("OS1.3/Disk.info")
    assert obj.argb is None
    assert obj.coloricon is None
    assert obj.newicon is None
    img = to_image(obj)
    assert img.mode == "RGBA"


def test_to_image_selected_fallback():
    obj = load_file("OS4/drawer.info")
    # Even if selected is requested, should work (falls back to normal if no selected)
    img = to_image(obj, selected=True)
    assert isinstance(img, Image.Image)


def test_png_renders_rgba():
    obj = load_file("PNG/def_DF0.info")
    img = png_to_image(obj.png.normal)
    assert img.mode == "RGBA"
    assert img.size == (48, 48)


def test_png_selected_renders():
    obj = load_file("PNG/def_DF0.info")
    img = png_to_image(obj.png.selected)
    assert img.mode == "RGBA"
    assert img.size == (48, 48)


def test_to_image_prefers_png():
    obj = load_file("PNG/def_DF0.info")
    assert obj.png is not None
    img = to_image(obj)
    assert img.mode == "RGBA"
    assert img.size == (48, 48)


def test_to_image_no_data_raises():
    from amigainfo import DiskObject

    with pytest.raises(ValueError, match="No image data"):
        to_image(DiskObject())
