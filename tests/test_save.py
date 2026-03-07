from pathlib import Path

import pytest

from amigainfo import DiskObject, Gadget, IconType, load, save

TEST_ICONS = Path(__file__).resolve().parent / "test-icons"


def all_info_files():
    return sorted(TEST_ICONS.rglob("*.info"))


def icon_id(path):
    return str(path.relative_to(TEST_ICONS))


@pytest.fixture(params=all_info_files(), ids=lambda p: icon_id(p))
def icon_path(request):
    return request.param


def _strip_newicon_tooltypes(obj):
    """Return a copy with IM1=/IM2= tooltypes removed for comparison.

    NewIcon data is re-encoded with different line splitting, so the raw
    tooltype strings won't match byte-for-byte. The decoded newicon field
    is compared separately.
    """
    import dataclasses

    return dataclasses.replace(
        obj,
        tooltypes=[tt for tt in obj.tooltypes if not tt.startswith(("IM1=", "IM2="))],
    )


def test_round_trip(icon_path):
    original = load(icon_path.read_bytes())
    saved = save(original)
    reloaded = load(saved)
    assert _strip_newicon_tooltypes(reloaded) == _strip_newicon_tooltypes(original)


def test_save_minimal():
    obj = DiskObject(type=IconType.TOOL, gadget=Gadget(width=32, height=32))
    data = save(obj)
    reloaded = load(data)
    assert reloaded.type == IconType.TOOL
    assert reloaded.gadget.width == 32
    assert reloaded.gadget.height == 32


def test_save_with_newicon():
    obj = load((TEST_ICONS / "Newicons/0016.info").read_bytes())
    assert obj.newicon is not None
    saved = save(obj)
    reloaded = load(saved)
    assert reloaded.newicon is not None
    assert reloaded.newicon.normal.width == obj.newicon.normal.width
    assert reloaded.newicon.normal.height == obj.newicon.normal.height
    assert reloaded.newicon.normal.palette == obj.newicon.normal.palette
    assert reloaded.newicon.normal.pixel_data == obj.newicon.normal.pixel_data


def test_save_with_coloricon():
    obj = load((TEST_ICONS / "ColorIcons/AmigaMail.info").read_bytes())
    assert obj.coloricon is not None
    saved = save(obj)
    reloaded = load(saved)
    assert reloaded.coloricon is not None
    assert reloaded.coloricon.face.width == obj.coloricon.face.width
    assert reloaded.coloricon.normal.pixel_data == obj.coloricon.normal.pixel_data
    assert reloaded.coloricon.normal.palette == obj.coloricon.normal.palette


def test_save_with_argb():
    obj = load((TEST_ICONS / "OS4/drawer.info").read_bytes())
    assert obj.argb is not None
    saved = save(obj)
    reloaded = load(saved)
    assert reloaded.argb is not None
    assert reloaded.argb.normal.data == obj.argb.normal.data


def test_save_preserves_tooltypes():
    obj = load((TEST_ICONS / "Newicons/0016.info").read_bytes())
    user_tooltypes = [tt for tt in obj.tooltypes if not tt.startswith(("IM1=", "IM2="))]
    saved = save(obj)
    reloaded = load(saved)
    reloaded_user = [tt for tt in reloaded.tooltypes if not tt.startswith(("IM1=", "IM2="))]
    assert reloaded_user == user_tooltypes
