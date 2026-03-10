from pathlib import Path

import pytest
from PIL import Image

import amigainfo
from amigainfo.models import DiskObject
from amigainfo.pillow_plugin import _accept

TEST_ICONS = Path(__file__).resolve().parent / "test-icons"


def all_info_files():
    return sorted(TEST_ICONS.rglob("*.info"))


@pytest.fixture(params=all_info_files(), ids=lambda p: str(p.relative_to(TEST_ICONS)))
def icon_path(request):
    return request.param


def test_open_all_icons(icon_path):
    img = Image.open(icon_path)
    assert isinstance(img, Image.Image)


def test_open_returns_rgba(icon_path):
    img = Image.open(icon_path)
    assert img.mode == "RGBA"


def test_open_size_nonzero(icon_path):
    img = Image.open(icon_path)
    assert img.size[0] > 0
    assert img.size[1] > 0


def test_frame_count_os4_drawer():
    img = Image.open(TEST_ICONS / "OS4" / "drawer.info")
    # OS4 drawer has ARGB + ColorIcon + classic = multiple generations
    assert img.n_frames >= 2


def test_seek_all_frames():
    img = Image.open(TEST_ICONS / "OS4" / "drawer.info")
    for i in range(img.n_frames):
        img.seek(i)
        img.load()
        assert img.size[0] > 0
        assert img.size[1] > 0


def test_frame0_is_best():
    """For an icon with ARGB+classic, frame 0 should be ARGB (larger) not classic."""
    img = Image.open(TEST_ICONS / "OS4" / "drawer.info")
    obj = amigainfo.load((TEST_ICONS / "OS4" / "drawer.info").read_bytes())
    argb_size = (obj.argb.normal.width, obj.argb.normal.height)
    assert img.size == argb_size


def test_disk_object_in_info():
    img = Image.open(TEST_ICONS / "OS4" / "drawer.info")
    assert "disk_object" in img.info
    assert isinstance(img.info["disk_object"], DiskObject)


def test_accept_rejects_non_icon():
    assert not _accept(b"\x00\x00\x00\x00")
    assert not _accept(b"\x89PNG")
    assert not _accept(b"")


def test_accept_matches_icon():
    assert _accept(b"\xe3\x10\x00\x01")


def test_extension_registered():
    assert Image.registered_extensions().get(".info") == "WBINFO"


def test_open_via_path():
    path = TEST_ICONS / "ColorIcons" / "AmigaMail.info"
    img = Image.open(str(path))
    assert isinstance(img, Image.Image)
    assert img.size[0] > 0
