#!/usr/bin/env python3
"""
Template for a REVISION of a show the user already runs (docs/update-workflow.md, stage 6).

Copy this next to the user's files as build_v<N>.py, keep the skeleton, replace the CHANGES
section. The skeleton does what every revision must:

  * refuse to overwrite anything, and never write over the source
  * re-find every object by NAME in this file (UIDs move on every Lightkey save — Bug 23)
  * edit in place: rewrite fpStore bytes and cue fields; never rebuild a cue (Bug 28)
  * count what it touched and assert the counts, so a changed file shape fails loudly
  * add MIDI triggers only on free notes, through lightkey.bindings

As shipped it makes two example changes so it runs end to end on any project that has the named
cues: it raises one cue's priority, and binds a MIDI note to another if it has none.

Usage: python3 build_next.py <user's latest Lightkey save> <out.lightkeyproj> [panel name]
"""
import os
import plistlib
import sys
from collections import Counter
from plistlib import UID

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))       # repo root; adjust when copied elsewhere
from lightkey import bindings as BD  # noqa: E402
from lightkey.build import Builder  # noqa: E402
from lightkey.resolve import classname, find_instances, load, resolve  # noqa: E402

# ---- CHANGES: the only part you should need to edit -------------------------------------------
PANEL = None                                 # live panel whose buttons define "the" cue of a name,
                                             # for files where names repeat across panels
RAISE = {'House: 10%': 7}                    # cue name -> new priority
BIND = {'House: 20%': (16, None)}            # cue name -> (channel 1-based, note or None = first free)
EXPECT = {'priority raised': 1}              # what the build must have done; asserted below


def main():
    global PANEL
    src, out = sys.argv[1], sys.argv[2]
    if len(sys.argv) > 3:
        PANEL = sys.argv[3]
    if os.path.abspath(src) == os.path.abspath(out) or os.path.exists(out):
        sys.exit(f'refusing to overwrite {out}')
    data, objs = load(src)
    top = data['$top']
    b = Builder(data)
    n_base = len(objs)
    counts = Counter()

    def txt(u):
        v = objs[int(u)] if isinstance(u, UID) else u
        if isinstance(v, dict):
            s = v.get('NS.string')
            return txt(s) if isinstance(s, UID) else s
        return v

    def kids(u):
        o = objs[int(u)] if isinstance(u, UID) and int(u) else None
        return [int(x) for x in o.get('NS.objects', [])] if isinstance(o, dict) else []

    panel_cues = None
    if PANEL is not None:
        panel = next((objs[u] for u in kids(top['livePanels']) if txt(objs[u]['name']) == PANEL), None)
        assert panel is not None, f'no live panel named {PANEL!r}'
        panel_cues = {int(objs[i]['cue']) for i in kids(panel['items'])
                      if classname(objs, objs[i]) == 'LXCpanButton' and isinstance(objs[i].get('cue'), UID)}

    def cues_named(name):
        """Every cue with this name — on PANEL only, when PANEL is set. Names repeat across panels in
        real shows; an assert here beats silently editing the wrong copy."""
        found = [u for u in find_instances(objs, 'LXCue') if txt(objs[u]['name']) == name
                 and (panel_cues is None or u in panel_cues)]
        assert found, f'no cue named {name!r}' + (f' on panel {PANEL!r}' if PANEL else '')
        return found

    def read_store(uid):
        return plistlib.loads(objs[int(objs[uid]['fpStore'])])

    def write_store(uid, store):
        # a fresh bytes object, so an fpStore shared with another preset can never change with it
        objs[uid] = dict(objs[uid], fpStore=b.add(plistlib.dumps(store, fmt=plistlib.FMT_BINARY)))

    def steps_of(uid):
        """A preset yields itself; a sequence yields its steps."""
        if classname(objs, objs[uid]) == 'LXSequence':
            return kids(objs[uid]['childNodes'])
        return [uid]

    # ---- the changes -----------------------------------------------------------------------
    for name, prio in RAISE.items():
        for cu in cues_named(name):
            objs[cu]['priority'] = prio
            counts['priority raised'] += 1

    bound = BD.list_bindings(objs, top)
    for name, (channel, note) in BIND.items():
        found = cues_named(name)
        assert len(found) == 1, f'{name!r} names {len(found)} cues: set PANEL to pick one'
        cu = found[0]
        cue_uuid = str(resolve(objs, objs[cu].get('UUID'))).upper()
        if any(r['cue_uuid'] == cue_uuid and r['kind'] == 'midi' for r in bound):   # by UUID, not name
            counts['already bound'] += 1
            continue
        note = note if note is not None else BD.free_notes(objs, top, channel)[0]
        BD.add_note_trigger(b, top, cu, channel=channel, note=note, behaviour=BD.TOGGLE)
        counts['note bound'] += 1
        print(f'{name}: channel {channel} note {note}')

    # Example of a look edit, left commented: squeeze one look's colours, step by step.
    # for pu in kids(objs[cues_named('Warm Glow')[0]]['presets']):
    #     for su in steps_of(pu):
    #         store = read_store(su)
    #         for fid, spec in store['umbrellaContainers'].items():
    #             seg = spec['segmentContainers'][0]
    #             ...                                  # change only what you mean to change
    #         write_store(su, store)
    #         counts['steps recoloured'] += 1
    _ = (read_store, write_store, steps_of)

    # ---- assert, then write ------------------------------------------------------------------
    for k, v in EXPECT.items():
        assert counts[k] == v, f'{k}: expected {v}, got {counts[k]} ({dict(counts)})'
    with open(out, 'wb') as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
    print(f'{dict(counts)}; {len(objs) - n_base} objects added; wrote {out}')


if __name__ == '__main__':
    main()
