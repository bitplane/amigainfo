"""CLI tool for inspecting and converting Amiga .info files."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .load import load
from .palettes import WB_1X, WB_2X
from .render import (
    argb_to_image,
    classic_to_image,
    coloricon_to_image,
    newicon_to_image,
    to_image,
)


def _info_text(obj) -> str:
    """Format a human-readable summary of a DiskObject."""
    lines = []
    type_name = obj.type.name if hasattr(obj.type, "name") else str(obj.type)
    lines.append(f"Type:       {type_name}")
    lines.append(f"Position:   ({obj.current_x}, {obj.current_y})")
    lines.append(f"Gadget:     {obj.gadget.width}x{obj.gadget.height}")
    lines.append(f"Stack:      {obj.stack_size}")

    if obj.default_tool:
        lines.append(f"DefaultTool: {obj.default_tool}")

    formats = []
    if obj.classic:
        depth = obj.classic.normal.header.depth
        has_sel = obj.classic.selected is not None
        formats.append(f"classic ({depth} bitplanes, selected={has_sel})")
    if obj.newicon:
        ni = obj.newicon.normal
        has_sel = obj.newicon.selected is not None
        formats.append(f"newicon ({ni.width}x{ni.height}, {len(ni.palette)} colors, selected={has_sel})")
    if obj.coloricon:
        ci = obj.coloricon.face
        has_sel = obj.coloricon.selected is not None
        formats.append(f"coloricon ({ci.width}x{ci.height}, selected={has_sel})")
    if obj.argb:
        a = obj.argb.normal
        has_sel = obj.argb.selected is not None
        formats.append(f"argb ({a.width}x{a.height}, selected={has_sel})")

    lines.append("Formats:    " + ", ".join(formats) if formats else "Formats:    none")

    if obj.drawer_data:
        dd = obj.drawer_data
        lines.append(f"Drawer:     {dd.width}x{dd.height} at ({dd.left_edge}, {dd.top_edge})")

    # Filter out NewIcon data lines from display
    user_tooltypes = [tt for tt in obj.tooltypes if not tt.startswith(("IM1=", "IM2="))]
    if user_tooltypes:
        lines.append("ToolTypes:")
        for tt in user_tooltypes:
            lines.append(f"  {tt}")

    return "\n".join(lines)


def _json_default(obj):
    """JSON serializer for types that aren't natively serializable."""
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if hasattr(obj, "name"):
        return obj.name
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _convert_one(args, input_path: Path, output_path: Path | None):
    """Process a single .info file."""
    data = input_path.read_bytes()
    obj = load(data)

    if args.info:
        print(f"--- {input_path} ---")
        print(_info_text(obj))
        return

    if args.json:
        print(json.dumps(dataclasses.asdict(obj), indent=2, default=_json_default))
        return

    # Render image
    palette_map = {"wb1x": WB_1X, "wb2x": WB_2X}

    if args.format:
        fmt = args.format
        selected = args.selected
        if fmt == "argb" and obj.argb:
            src = obj.argb.selected if selected and obj.argb.selected else obj.argb.normal
            img = argb_to_image(src)
        elif fmt == "coloricon" and obj.coloricon:
            src = obj.coloricon.selected if selected and obj.coloricon.selected else obj.coloricon.normal
            img = coloricon_to_image(src)
        elif fmt == "newicon" and obj.newicon:
            src = obj.newicon.selected if selected and obj.newicon.selected else obj.newicon.normal
            img = newicon_to_image(src)
        elif fmt == "classic" and obj.classic:
            src = obj.classic.selected if selected and obj.classic.selected else obj.classic.normal
            palette = palette_map.get(args.palette) if args.palette else None
            img = classic_to_image(src, palette)
        else:
            print(f"Error: format '{fmt}' not available in {input_path}", file=sys.stderr)
            sys.exit(1)
    else:
        img = to_image(obj, selected=args.selected)

    if output_path is None:
        output_path = input_path.with_suffix(".png")

    img.save(output_path)
    print(f"{input_path} -> {output_path} ({img.size[0]}x{img.size[1]} {img.mode})")


def main():
    parser = argparse.ArgumentParser(
        prog="amigainfo",
        description="Inspect and convert Amiga .info icon files.",
    )
    parser.add_argument("input", nargs="+", type=Path, help="Input .info file(s)")
    parser.add_argument(
        "output", nargs="?", type=Path, default=None, help="Output image file (default: input with .png)"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--info", action="store_true", help="Show human-readable metadata")
    group.add_argument("--json", action="store_true", help="Dump metadata as JSON")

    parser.add_argument("--selected", action="store_true", help="Use selected (highlighted) state")
    parser.add_argument(
        "--format",
        choices=["classic", "newicon", "coloricon", "argb"],
        help="Extract a specific image format layer",
    )
    parser.add_argument(
        "--palette",
        choices=["wb1x", "wb2x"],
        help="Palette for classic icons (default: auto-detect)",
    )

    args = parser.parse_args()

    # Handle the ambiguity: if last arg looks like an output file (not .info),
    # treat it as the output rather than an input
    if args.output is None and len(args.input) > 1:
        last = args.input[-1]
        if last.suffix.lower() != ".info":
            args.output = last
            args.input = args.input[:-1]

    if len(args.input) == 1:
        _convert_one(args, args.input[0], args.output)
    else:
        if args.output and not (args.info or args.json):
            print("Error: cannot specify output file with multiple inputs", file=sys.stderr)
            sys.exit(1)
        for path in args.input:
            _convert_one(args, path, None)


if __name__ == "__main__":
    main()
