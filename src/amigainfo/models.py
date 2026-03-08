from __future__ import annotations

from dataclasses import dataclass, field

from .enums import IconType


@dataclass
class Gadget:
    """Embedded Gadget structure from the DiskObject header (44 bytes on disk)."""

    left_edge: int = 0
    top_edge: int = 0
    width: int = 0
    height: int = 0
    flags: int = 0
    activation: int = 0
    gadget_type: int = 0
    gadget_render: int = 0
    select_render: int = 0
    user_data: int = 0


@dataclass
class DrawerData:
    """Drawer window state.

    Contains NewWindow fields for the drawer window, scroll offsets,
    and optional OS 2.x+ display flags (DrawerData2).
    """

    # NewWindow fields
    left_edge: int = 0
    top_edge: int = 0
    width: int = 0
    height: int = 0
    detail_pen: int = 0xFF
    block_pen: int = 0xFF

    # Scroll offsets
    current_x: int = 0
    current_y: int = 0

    # DrawerData2 (OS 2.x+ only, when ga_UserData & 0xFF == 1)
    flags: int = 0
    view_modes: int = 0


@dataclass
class ImageHeader:
    """Amiga Image structure header (20 bytes on disk).

    Describes a single planar bitmap. The actual pixel data
    is stored separately.
    """

    left_edge: int = 0
    top_edge: int = 0
    width: int = 0
    height: int = 0
    depth: int = 0
    plane_pick: int = 0
    plane_on_off: int = 0


@dataclass
class ClassicImage:
    """A single classic planar bitmap image with its header."""

    header: ImageHeader
    planes: list[bytes] = field(default_factory=list)


@dataclass
class ClassicImages:
    """Classic planar bitmap images (OS 1.x-3.1).

    Always present in a standard .info file. Up to two images:
    normal (from GadgetRender) and selected (from SelectRender).
    """

    normal: ClassicImage
    selected: ClassicImage | None = None


@dataclass
class NewIconImage:
    """A single decoded NewIcon image."""

    width: int = 0
    height: int = 0
    transparent: bool = False
    palette: list[tuple[int, int, int]] = field(default_factory=list)
    pixel_data: list[int] = field(default_factory=list)


@dataclass
class NewIconImages:
    """NewIcon images decoded from ToolTypes strings.

    Identified by the "*** DON'T EDIT THE FOLLOWING LINES!! ***" sentinel.
    Image data is in IM1= (normal) and IM2= (selected) tooltypes.
    """

    normal: NewIconImage
    selected: NewIconImage | None = None


@dataclass
class FaceChunk:
    """FACE chunk from IFF FORM ICON (GlowIcons/OS 3.5+)."""

    width: int = 0
    height: int = 0
    flags: int = 0
    aspect_x: int = 0
    aspect_y: int = 0
    max_palette_bytes: int = 0


@dataclass
class ColorIconImage:
    """A single IMAG chunk image from IFF FORM ICON."""

    width: int = 0
    height: int = 0
    transparent_color: int = 0
    has_transparent: bool = False
    depth: int = 0
    palette: list[tuple[int, int, int]] = field(default_factory=list)
    pixel_data: list[int] = field(default_factory=list)


@dataclass
class ColorIconImages:
    """GlowIcons / ColorIcon images from IFF FORM ICON (OS 3.5+).

    Found appended after classic .info data as FORM ICON chunks.
    """

    face: FaceChunk
    normal: ColorIconImage
    selected: ColorIconImage | None = None


@dataclass
class ARGBImage:
    """A single 32-bit ARGB image, zlib-compressed in the file."""

    width: int = 0
    height: int = 0
    data: bytes = b""


@dataclass
class ARGBImages:
    """32-bit ARGB images from IFF FORM ICON ARGB chunks (OS4)."""

    normal: ARGBImage
    selected: ARGBImage | None = None


@dataclass
class PNGImages:
    """OS4 PNG icon images. Two concatenated PNG files."""

    normal: bytes = b""
    selected: bytes | None = None


@dataclass
class DiskObject:
    """Top-level Amiga .info file structure.

    Every standard .info file starts with a DiskObject header containing
    metadata and a Gadget structure. Image data may be present in multiple
    formats, layered on top of each other for backward compatibility:

    - classic: Planar bitmaps (always present for 0xE310 files)
    - newicon: Higher color images encoded in ToolTypes
    - coloricon: GlowIcons IMAG chunks (OS 3.5+)
    - argb: 32-bit ARGB image data (OS4)
    """

    # Header fields
    magic: int = 0xE310
    version: int = 1
    type: IconType = IconType.TOOL

    # Gadget (layout/behavior metadata)
    gadget: Gadget = field(default_factory=Gadget)

    # Metadata
    default_tool: str | None = None
    tool_window: str | None = None
    tooltypes: list[str] = field(default_factory=list)
    current_x: int = 0
    current_y: int = 0
    stack_size: int = 0
    drawer_data: DrawerData | None = None

    # Image layers (progressive enhancement)
    classic: ClassicImages | None = None
    newicon: NewIconImages | None = None
    coloricon: ColorIconImages | None = None
    argb: ARGBImages | None = None
    png: PNGImages | None = None
