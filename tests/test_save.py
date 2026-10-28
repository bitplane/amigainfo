from pathlib import Path

import pytest

from amigainfo import ClassicImage, ClassicImages, DiskObject, Gadget, IconType, ImageHeader, load, save

TEST_ICONS = Path(__file__).resolve().parent / "test-icons"


def all_info_files():
    return sorted(TEST_ICONS.rglob("*.info"))


def icon_id(path):
    return str(path.relative_to(TEST_ICONS))


@pytest.fixture(params=all_info_files(), ids=lambda p: icon_id(p))
def icon_path(request):
    return request.param


def _strip_newicon(obj):
    """Return a copy with NewIcon data removed for comparison.

    NewIcon data is re-encoded with per-line bit alignment, so externally
    generated files may decode slightly differently after a round-trip.
    NewIcon stability is verified separately.
    """
    import dataclasses

    return dataclasses.replace(
        obj,
        tooltypes=[tt for tt in obj.tooltypes if not tt.startswith(("IM1=", "IM2="))],
        newicon=None,
    )


def test_round_trip(icon_path):
    original = load(icon_path.read_bytes())
    saved = save(original)
    reloaded = load(saved)
    assert _strip_newicon(reloaded) == _strip_newicon(original)
    # Verify NewIcon data survives a second round-trip (save->load->save->load).
    # The first load of an externally-generated file may differ because the
    # original encoder used a continuous bitstream while we use per-line encoding,
    # but our own output must be stable.
    if reloaded.newicon:
        saved2 = save(reloaded)
        reloaded2 = load(saved2)
        assert reloaded2.newicon == reloaded.newicon


def test_save_minimal():
    obj = DiskObject(type=IconType.TOOL, gadget=Gadget(width=32, height=32))
    data = save(obj)
    reloaded = load(data)
    assert reloaded.type == IconType.TOOL
    assert reloaded.gadget.width == 32
    assert reloaded.gadget.height == 32


def test_save_constructed_classic_image_sets_presence_flags():
    image = ClassicImage(
        header=ImageHeader(width=1, height=1, depth=1, plane_pick=1),
        planes=[b"\x80\x00"],
    )
    obj = DiskObject(
        type=IconType.TOOL,
        gadget=Gadget(width=1, height=1),
        classic=ClassicImages(normal=image, selected=image),
    )

    reloaded = load(save(obj))

    assert reloaded.classic == obj.classic
    assert reloaded.gadget.gadget_render != 0
    assert reloaded.gadget.select_render != 0


def test_save_removed_classic_image_clears_presence_flags():
    obj = load((TEST_ICONS / "OS1.3/Prefs.info").read_bytes())
    obj.classic = None

    reloaded = load(save(obj))

    assert reloaded.classic is None
    assert reloaded.gadget.gadget_render == 0
    assert reloaded.gadget.select_render == 0


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


@pytest.mark.parametrize("field", ["default_tool", "tool_window", "tooltypes"])
@pytest.mark.parametrize("value", ["", "x", "ab", "abc"])
def test_png_preserves_short_final_string(field, value):
    png = load((TEST_ICONS / "PNG/def_DF0.info").read_bytes()).png
    expected = ["A=1", value] if field == "tooltypes" else value
    obj = DiskObject(png=png, **{field: expected})

    reloaded = load(save(obj))

    assert getattr(reloaded, field) == expected


@pytest.mark.parametrize("attribute", [b"\x80\x00\x10\x01\x00", b"\x80\x00\x10\x0aab"])
def test_png_rejects_truncated_attribute(attribute):
    from amigainfo.save import _make_png_chunk

    png = load((TEST_ICONS / "PNG/def_DF0.info").read_bytes()).png.normal
    data = png[:-12] + _make_png_chunk(b"icOn", attribute) + png[-12:]

    with pytest.raises(ValueError, match="Truncated or malformed"):
        load(data)


@pytest.mark.parametrize("pixel_type", [list, bytes])
def test_save_constructed_coloricon(pixel_type):
    from amigainfo import ColorIconImage, ColorIconImages, FaceChunk, to_image

    pixels = pixel_type([0, 1, 2, 3])
    palette = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
    image = ColorIconImage(width=2, height=2, depth=2, palette=palette, pixel_data=pixels)
    obj = DiskObject(coloricon=ColorIconImages(face=FaceChunk(width=2, height=2, max_palette_bytes=12), normal=image))

    reloaded = load(save(obj))

    assert list(reloaded.coloricon.normal.pixel_data) == [0, 1, 2, 3]
    assert reloaded.coloricon.normal.palette == palette
    assert to_image(reloaded).tobytes() == to_image(obj).tobytes()
    assert image.pixel_data is pixels


@pytest.mark.parametrize("size", [0, 65537])
def test_save_coloricon_rejects_unrepresentable_pixel_count(size):
    from amigainfo import ColorIconImage
    from amigainfo.save import _write_imag_chunk

    with pytest.raises(ValueError, match="pixel data"):
        _write_imag_chunk(ColorIconImage(pixel_data=[0] * size))


@pytest.mark.parametrize("gadget_size", [0, 10])
@pytest.mark.parametrize("with_classic", [False, True])
def test_save_argb_without_coloricon_preserves_dimensions(gadget_size, with_classic):
    from amigainfo import ARGBImage, ARGBImages, to_image

    normal = ARGBImage(width=2, height=3, data=b"\xff\x12\x34\x56" * 6)
    selected = ARGBImage(width=2, height=3, data=b"\x80\x65\x43\x21" * 6)
    obj = DiskObject(
        gadget=Gadget(width=gadget_size, height=gadget_size),
        argb=ARGBImages(normal=normal, selected=selected),
    )
    if with_classic:
        obj.classic = ClassicImages(
            normal=ClassicImage(header=ImageHeader(width=1, height=1, depth=1, plane_pick=1), planes=[b"\x80\x00"])
        )

    reloaded = load(save(obj))

    assert reloaded.argb == obj.argb
    assert reloaded.coloricon is None
    assert reloaded.classic == obj.classic
    assert reloaded.gadget.width == gadget_size
    assert reloaded.gadget.height == gadget_size
    for state in (False, True):
        assert to_image(reloaded, selected=state).size == (2, 3)
        assert to_image(reloaded, selected=state).tobytes() == to_image(obj, selected=state).tobytes()


@pytest.mark.parametrize("size", [(1, 1), (256, 256)])
def test_save_argb_face_dimension_boundaries(size):
    from amigainfo import ARGBImage, ARGBImages

    image = ARGBImage(width=size[0], height=size[1], data=b"\xff\x12\x34\x56" * (size[0] * size[1]))
    obj = DiskObject(argb=ARGBImages(normal=image))

    assert load(save(obj)).argb == obj.argb


@pytest.mark.parametrize("size", [(0, 1), (1, 0), (257, 1), (1, 257)])
def test_save_argb_rejects_unrepresentable_dimensions(size):
    from amigainfo import ARGBImage, ARGBImages

    obj = DiskObject(argb=ARGBImages(normal=ARGBImage(width=size[0], height=size[1])))
    with pytest.raises(ValueError, match="dimensions"):
        save(obj)


def test_save_argb_rejects_mismatched_selected_dimensions():
    from amigainfo import ARGBImage, ARGBImages

    obj = DiskObject(
        argb=ARGBImages(
            normal=ARGBImage(width=1, height=1, data=b"\xff" * 4),
            selected=ARGBImage(width=2, height=1, data=b"\xff" * 8),
        )
    )
    with pytest.raises(ValueError, match="dimensions"):
        save(obj)
