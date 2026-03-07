from pathlib import Path

import pytest

from amigainfo import (
    IconType,
    load,
)

TEST_ICONS = Path(__file__).resolve().parent / "test-icons"


def all_info_files():
    return sorted(TEST_ICONS.rglob("*.info"))


def icon_id(path):
    return str(path.relative_to(TEST_ICONS))


@pytest.fixture(params=all_info_files(), ids=lambda p: icon_id(p))
def loaded_icon(request):
    data = request.param.read_bytes()
    return load(data), request.param


def test_loads_without_error(loaded_icon):
    obj, path = loaded_icon
    assert obj.magic == 0xE310
    assert obj.version == 1


def test_has_classic_images(loaded_icon):
    obj, _ = loaded_icon
    assert obj.classic is not None
    assert obj.classic.normal is not None
    assert len(obj.classic.normal.planes) == obj.classic.normal.header.depth


# --- Specific file tests ---


def load_file(name):
    return load((TEST_ICONS / name).read_bytes())


def test_os13_disk_type():
    obj = load_file("OS1.3/Disk.info")
    assert obj.type == IconType.DISK


def test_os13_disk_dimensions():
    obj = load_file("OS1.3/Disk.info")
    assert obj.gadget.width == 35
    assert obj.gadget.height == 16
    assert obj.classic.normal.header.depth == 2


def test_os13_disk_no_extras():
    obj = load_file("OS1.3/Disk.info")
    assert obj.newicon is None
    assert obj.coloricon is None
    assert obj.argb is None


def test_os13_prefs_is_drawer():
    obj = load_file("OS1.3/Prefs.info")
    assert obj.type == IconType.DRAWER
    assert obj.drawer_data is not None


def test_os3_disk_is_disk():
    obj = load_file("OS3/Disk.info")
    assert obj.type == IconType.DISK
    assert obj.gadget.width == 36


def test_mui_disk_3_bitplanes():
    obj = load_file("MUI/Disk.info")
    assert obj.classic.normal.header.depth == 3
    assert len(obj.classic.normal.planes) == 3


def test_newicons_detected():
    obj = load_file("Newicons/0016.info")
    assert obj.newicon is not None
    assert obj.newicon.normal.width == 42
    assert obj.newicon.normal.height == 42


def test_newicons_palette():
    obj = load_file("Newicons/0016.info")
    assert len(obj.newicon.normal.palette) == 32
    # All palette entries should be (r, g, b) tuples
    for color in obj.newicon.normal.palette:
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)


def test_newicons_pixel_count():
    obj = load_file("Newicons/0016.info")
    expected = obj.newicon.normal.width * obj.newicon.normal.height
    assert len(obj.newicon.normal.pixel_data) == expected


def test_newicons_apps_has_selected():
    obj = load_file("Newicons/Apps.info")
    assert obj.newicon is not None
    assert obj.newicon.selected is not None


def test_coloricon_face_dimensions():
    obj = load_file("ColorIcons/AmigaMail.info")
    assert obj.coloricon is not None
    assert obj.coloricon.face.width == 48
    assert obj.coloricon.face.height == 48


def test_coloricon_has_palette():
    obj = load_file("ColorIcons/AmigaMail.info")
    assert len(obj.coloricon.normal.palette) > 0


def test_coloricon_pixel_count():
    obj = load_file("ColorIcons/AmigaMail.info")
    expected = obj.coloricon.face.width * obj.coloricon.face.height
    assert len(obj.coloricon.normal.pixel_data) >= expected


def test_alpha_has_coloricon():
    obj = load_file("alpha/Games.info")
    assert obj.coloricon is not None
    assert obj.coloricon.face.width == 64
    assert obj.coloricon.face.height == 64


def test_os4_has_argb():
    obj = load_file("OS4/drawer.info")
    assert obj.argb is not None
    assert obj.argb.normal.width == 64
    assert obj.argb.normal.height == 64
    # ARGB = 4 bytes per pixel
    assert len(obj.argb.normal.data) == 64 * 64 * 4


def test_os4_aladdin_argb():
    obj = load_file("OS4/Aladdin4D.info")
    assert obj.argb is not None
    assert len(obj.argb.normal.data) == 64 * 65 * 4


def test_os4_install_is_project():
    obj = load_file("OS4/install.info")
    assert obj.type == IconType.PROJECT


def test_tooltypes_parsed():
    obj = load_file("Newicons/0016.info")
    assert len(obj.tooltypes) == 18
    assert any("IM1=" in tt for tt in obj.tooltypes)


def test_drawer_data_present():
    obj = load_file("MUI/drawer.info")
    assert obj.type == IconType.DRAWER
    assert obj.drawer_data is not None


def test_classic_image_plane_sizes():
    obj = load_file("OS1.3/Disk.info")
    header = obj.classic.normal.header
    words_per_row = (header.width + 15) // 16
    bytes_per_row = words_per_row * 2
    expected_plane_size = bytes_per_row * header.height
    for plane in obj.classic.normal.planes:
        assert len(plane) == expected_plane_size


def test_no_selected_image_when_absent():
    obj = load_file("OS1.3/Disk.info")
    # OS1.3 Disk has select_render=0, so no second image
    assert obj.gadget.select_render == 0
    assert obj.classic.selected is None


def test_selected_image_when_present():
    obj = load_file("OS1.3/Prefs.info")
    assert obj.gadget.select_render != 0
    assert obj.classic.selected is not None
    assert obj.classic.selected.header.depth == obj.classic.normal.header.depth


def test_invalid_magic():
    with pytest.raises(ValueError, match="Not an Amiga .info file"):
        load(b"\x00\x00\x00\x00" * 20)
