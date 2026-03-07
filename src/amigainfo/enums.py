from enum import IntEnum, IntFlag


class IconType(IntEnum):
    """do_Type values from the DiskObject structure."""

    DISK = 1
    DRAWER = 2
    TOOL = 3
    PROJECT = 4
    GARBAGE = 5
    KICK = 7
    APPICON = 8


class GadgetFlag(IntFlag):
    """Gadget flag bits (ga_Flags)."""

    GADGHIGHBITS = 0x0003
    GADGHCOMP = 0x0000
    GADGHBOX = 0x0001
    GADGHIMAGE = 0x0002
    GADGHNONE = 0x0003
    GADGIMAGE = 0x0004
    GRELBOTTOM = 0x0008
    GRELRIGHT = 0x0010
    GRELWIDTH = 0x0020
    GRELHEIGHT = 0x0040
    SELECTED = 0x0080
    GADGDISABLED = 0x0100


class GadgetActivation(IntFlag):
    """Gadget activation bits (ga_Activation)."""

    RELVERIFY = 0x0001
    GADGIMMEDIATE = 0x0002
    ENDGADGET = 0x0004
    FOLLOWMOUSE = 0x0008
    RIGHTBORDER = 0x0010
    LEFTBORDER = 0x0020
    TOPBORDER = 0x0040
    BOTTOMBORDER = 0x0080
    TOGGLESELECT = 0x0100
