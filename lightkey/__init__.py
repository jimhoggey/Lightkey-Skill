"""Unofficial tooling for Lightkey .lightkeyproj files.

    from lightkey.resolve import load, find_instances, classname
    from lightkey.colour  import pack_color, c8, unpack_rgb8
    from lightkey.build   import Builder, build_fpstore, mk_preset, mk_cue, mk_button
    from lightkey.validate import Validator
    from lightkey.bindings import list_bindings, free_notes, add_note_trigger

Read docs/pitfalls.md before writing to a project file, and docs/update-workflow.md before
revising a show someone already runs.
"""
from .build import Builder, build_fpstore                  # noqa: F401
from .colour import pack_color, c8, unpack_rgb8            # noqa: F401
from .resolve import load, classname, find_instances       # noqa: F401

__version__ = '0.5.0'
