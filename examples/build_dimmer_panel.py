#!/usr/bin/env python3
"""
End-to-end example: add a working "rocker switch" dimmer row to an existing project.

Demonstrates the load-bearing patterns in one readable file:
  * discovering fixtures instead of hardcoding UUIDs
  * building an fpStore (old umbrellaContainers schema)
  * a mutually-exclusive LXPresetGroup so the buttons release each other
  * attaching under the EXISTING root preset group, never replacing it
  * reusing the source file's class definitions and empty-collection singletons

The archive plumbing — raw-string names, NSSet for activeSpeedModifiers, a
per-cue orphanPresetsGroup — lives in lightkey/build.py, so this file stays
about the design decisions rather than the schemas.

Usage:
    python3 examples/build_dimmer_panel.py input.lightkeyproj output.lightkeyproj

Then open the output in Lightkey. The new panel is selected on launch; your original
panels are kept as extra tabs. Read docs/pitfalls.md before adapting this.
"""
import os
import plistlib
import sys
import uuid as _uuid
from plistlib import UID

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from lightkey.build import (Builder, build_fpstore, mk_button, mk_cue,  # noqa: E402
                            mk_preset, mk_preset_group)
from lightkey.resolve import find_instances  # noqa: E402

LEVELS = [('Off', 0.0), ('25%', 0.25), ('50%', 0.5), ('75%', 0.75), ('100%', 1.0)]


def fp_intensity(fixture_uuids, level):
    """Intensity-only fpStore: touches the dimmer and nothing else, so colour
    presets can compose with it freely (docs/patterns.md §2)."""
    return build_fpstore({u: {'defined_features': ['Intensity'],
                              'segment': {'intensity': float(level)}}
                          for u in fixture_uuids})


def fixture_uuids(objs, limit=None):
    """Discover fixture UUIDs from the project — never hardcode them (Bug 23)."""
    found = []
    for u in find_instances(objs, 'LXDMXFixture'):
        for v in objs[u].values():
            if isinstance(v, UID):
                cand = objs[int(v)]
                if isinstance(cand, dict) and 'NS.uuidbytes' in cand:
                    found.append(str(_uuid.UUID(bytes=cand['NS.uuidbytes'])).upper())
                    break
    return found[:limit] if limit else found


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    if os.path.abspath(src) == os.path.abspath(out):
        sys.exit('refusing to overwrite the input file')

    with open(src, 'rb') as f:
        archive = plistlib.load(f)
    top, objs = archive['$top'], archive['$objects']
    before = len(objs)
    b = Builder(archive)

    fixtures = fixture_uuids(objs)
    if not fixtures:
        sys.exit('no LXDMXFixture objects found — is this a Lightkey project?')
    print(f'{len(fixtures)} fixtures found; building a {len(LEVELS)}-step dimmer row')

    presets, buttons = [], []
    for i, (label, level) in enumerate(LEVELS):
        p = mk_preset(b, f'Dim {label}', fp_intensity(fixtures, level))
        presets.append(p)
        buttons.append(mk_button(b, mk_cue(b, f'All: {label}', [p], priority=4),
                                 16 + i * 96, 24, 90, 40))

    # Mutual exclusion — this is what makes the buttons behave like a rocker switch.
    group = mk_preset_group(b, 'Example Dimmer', presets, mutually_exclusive=True)

    # Attach under the EXISTING root. Replacing top.rootPresetGroup makes the Live
    # panel render empty (Bug 13).
    root = objs[int(top['rootPresetGroup'])]
    root_children = objs[int(root['childNodes'])]
    root_children['NS.objects'] = [group] + list(root_children.get('NS.objects', []))

    panel = b.add({'name': b.raw_str('Example Dimmer Panel'), 'UUID': b.uuid_obj(),
                   'items': b.ns_array(buttons), 'fadeDuration': 0.3,
                   '$class': b.cls('LXControlPanel')})
    top['livePanels'] = b.ns_array([panel] + list(objs[int(top['livePanels'])]['NS.objects']))
    top['selectedLivePanel'] = panel

    with open(out, 'wb') as f:
        plistlib.dump(archive, f, fmt=plistlib.FMT_BINARY)
    print(f'wrote {out}  ({before} -> {len(objs)} objects)')
    print('Now validate it:  python3 -c "from lightkey.validate import Validator; '
          f"v=Validator('{src}','{out}'); v.structural_parity(); v.buttons_resolve(); v.report()\"")


if __name__ == '__main__':
    main()
