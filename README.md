# amigainfo

A Python library for loading and converting Amiga `.info` icon files.

Supports all four generations of the format:

- **Classic** (OS 1.x-3.1) — planar bitmap icons
- **NewIcons** — higher color icons encoded in ToolTypes strings
- **GlowIcons / ColorIcons** (OS 3.5+) — IFF FORM ICON with RLE compression
- **ARGB** (OS4) — 32-bit icons with zlib-compressed ARGB data

## Install

```
pip install amigainfo
```

## Library usage

```python
from amigainfo import load, to_image

# Load and render the best available image
obj = load(open("MyApp.info", "rb").read())
img = to_image(obj)
img.save("MyApp.png")

# Access metadata
print(obj.type)          # IconType.TOOL
print(obj.default_tool)  # "SYS:Utilities/MultiView"
print(obj.tooltypes)     # ["PUBSCREEN=Workbench", ...]

# Render a specific format or state
from amigainfo import classic_to_image, WB_1X

img = classic_to_image(obj.classic.normal, palette=WB_1X)
img = to_image(obj, selected=True)
```

## CLI

Convert `.info` files to standard image formats:

```bash
# Convert to PNG (picks the best available image format)
amigainfo icon.info icon.png

# Output format follows the file extension
amigainfo icon.info icon.webp

# Batch convert (outputs alongside inputs as .png)
amigainfo *.info

# Use the selected (highlighted) icon state
amigainfo --selected icon.info icon.png

# Extract a specific format layer
amigainfo --format classic icon.info icon.png
amigainfo --format newicon icon.info icon.png
amigainfo --format coloricon icon.info icon.png
amigainfo --format argb icon.info icon.png

# Override the palette for classic icons
amigainfo --palette wb1x icon.info icon.png
```

Inspect metadata:

```bash
# Human-readable summary
amigainfo --info icon.info

# JSON dump
amigainfo --json icon.info
```

## Format overview

Amiga `.info` files are icon files used by AmigaOS Workbench. The format evolved
over several OS generations, with each new format layered on top of the previous
for backward compatibility.

Every standard `.info` file starts with a DiskObject header (`0xE310` magic)
containing a Gadget structure, icon metadata (type, position, tooltypes, default
tool), and planar bitmap image data. Later formats append additional image data:

| Format | Era | Image type | Palette |
|--------|-----|-----------|---------|
| Classic | OS 1.x-3.1 | Planar bitmaps (1-8 bitplanes) | System Workbench palette |
| NewIcons | Mid-90s | Chunky pixels encoded in ToolTypes | Embedded in data |
| GlowIcons | OS 3.5+ | RLE-compressed indexed color (IFF) | Embedded in data |
| ARGB | OS 4 | zlib-compressed 32-bit ARGB | Full color |

Each file can contain up to two images: normal and selected (highlighted) states.

## Data model

The `load()` function returns a `DiskObject` with all parsed data accessible:

```
DiskObject
├── magic, version, type
├── gadget (Gadget: dimensions, flags, user_data)
├── default_tool, tool_window, tooltypes
├── current_x, current_y, stack_size
├── drawer_data (DrawerData: window state, OS2+ display flags)
├── classic (ClassicImages: normal/selected planar bitmaps)
├── newicon (NewIconImages: normal/selected palette+pixels)
├── coloricon (ColorIconImages: FACE chunk + normal/selected IMAG)
└── argb (ARGBImages: normal/selected 32-bit image data)
```

## Default palettes

Classic icons don't store palette data — they rely on the system Workbench
palette. Two palettes are included:

- `WB_1X` — OS 1.x, 4 colors (blue, white, black, orange)
- `WB_2X` — OS 2.x/3.x, 8 colors (the standard Workbench palette)

The default is `WB_2X`. The `to_image()` function auto-selects based on
`gadget.user_data` (OS 2.x+ icons set this to 1).

## License

Public domain (WTFPL).
