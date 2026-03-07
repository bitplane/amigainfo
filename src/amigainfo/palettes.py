"""Default Workbench palettes for classic Amiga icons.

Classic .info files don't contain palette data — they use the system
Workbench palette. These are the standard palettes from each OS generation.
"""

# OS 1.x — 4 colors
WB_1X: tuple[tuple[int, int, int], ...] = (
    (85, 170, 255),  # 0: Blue
    (255, 255, 255),  # 1: White
    (0, 0, 0),  # 2: Black
    (255, 136, 0),  # 3: Orange
)

# OS 2.x/3.x — 8 colors (standard Workbench palette)
WB_2X: tuple[tuple[int, int, int], ...] = (
    (149, 149, 149),  # 0: Grey
    (0, 0, 0),  # 1: Black
    (255, 255, 255),  # 2: White
    (59, 103, 162),  # 3: Blue
    (123, 123, 123),  # 4: Dark grey
    (175, 175, 175),  # 5: Light grey
    (170, 144, 124),  # 6: Brown/tan
    (255, 169, 151),  # 7: Salmon
)

# Default palette — the newest old-style palette
DEFAULT = WB_2X
