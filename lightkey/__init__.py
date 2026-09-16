"""Unofficial tooling for Lightkey .lightkeyproj files.

    from lightkey.resolve import load, find_instances, classname
    from lightkey.colour  import pack_color, c8, unpack_rgb8
    from lightkey.build   import Builder, build_fpstore, mk_preset, mk_cue, mk_button
    from lightkey.validate import Validator

Read docs/pitfalls.md before writing to a project file.
"""
from .build import Builder, build_fpstore                  # noqa: F401
from .colour import pack_color, c8, unpack_rgb8            # noqa: F401
from .resolve import load, classname, find_instances       # noqa: F401

__version__ = '0.3.0'
