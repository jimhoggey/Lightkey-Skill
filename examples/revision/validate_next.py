#!/usr/bin/env python3
"""
Template validator for a revision (docs/update-workflow.md, stage 7). Pairs with build_next.py.

Three layers, in this order:
  1. structure  — the file will decode (class defs, key sets, raw names, UIDs not ints)
  2. preservation — nothing you did not mean to change changed: presets byte-for-byte, cue
     timing/priority, every source button, every source MIDI/key binding
  3. semantics  — one assertion per claim you will make to the user

Usage: python3 validate_next.py <source> <out> [panel name]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
from lightkey import bindings as BD  # noqa: E402
from lightkey.validate import Validator  # noqa: E402

# ---- what this revision is ALLOWED to change (by name) -----------------------------------------
CHANGED_PRESETS = []
CHANGED_CUES = ['House: 10%']


def main():
    src, out = sys.argv[1], sys.argv[2]
    panel = sys.argv[3] if len(sys.argv) > 3 else None
    v = Validator(src, out, panel=panel)

    # 1. structure
    v.structural_parity()
    v.buttons_resolve()
    v.no_overlap(ignore_preexisting=True)
    v.labels_fit()

    # 2. preservation
    v.preserved_buttons()
    v.bindings_intact()
    v.unchanged_except(presets=CHANGED_PRESETS, cues=CHANGED_CUES)

    # 3. semantics: one v.chk per claim in your hand-off notes
    cue = v.oB[v.cue_by('House: 10%')]
    v.chk(cue['priority'] == 7, 'House: 10% now priority 7')
    rows = [r for r in BD.list_bindings(v.oB, v.sB['$top']) if r['cue_name'] == 'House: 20%']
    v.chk(rows and not any(r['on_off'] for r in rows), 'House: 20% is bound, On/off unticked')

    sys.exit(0 if v.report() else 1)


if __name__ == '__main__':
    main()
