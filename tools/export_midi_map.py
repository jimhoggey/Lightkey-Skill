#!/usr/bin/env python3
"""
Export a Lightkey project's MIDI map as CSV: one row per note binding, with the cue, the panels
that show it, its exclusive group, and the Lightkey behaviour — the reference an operator (or a
Stream Deck / DAW / timeline sender) needs, and a record to diff between versions.

    python3 tools/export_midi_map.py MyShow_v5.lightkeyproj                 # to stdout
    python3 tools/export_midi_map.py MyShow_v5.lightkeyproj -o midi_map_v5.csv

Columns: channel (1-based), note, cue, panel, group, behaviour, on_off, endpoint, cue_uuid.
A row with an empty cue is a dead binding (its cue was deleted or rebuilt — pitfalls.md Bug 28).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plistlib import UID  # noqa: E402

from lightkey import bindings as BD  # noqa: E402
from lightkey import resolve as R  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project')
    ap.add_argument('-o', '--out')
    args = ap.parse_args()

    data, objs = R.load(args.project)
    top = data['$top']

    def txt(u):
        v = objs[int(u)] if isinstance(u, UID) else u
        if isinstance(v, dict):
            s = v.get('NS.string')
            return txt(s) if isinstance(s, UID) else s
        return v

    def kids(u):
        o = objs[int(u)] if isinstance(u, UID) and int(u) else None
        return [int(x) for x in o.get('NS.objects', [])] if isinstance(o, dict) else []

    uuid_of = lambda u: str(R.resolve(objs, objs[u].get('UUID'))).upper()  # noqa: E731
    panels_of, groups_of = {}, {}
    for pu in kids(top.get('livePanels')):
        for iu in kids(objs[pu].get('items')):
            if R.classname(objs, objs[iu]) == 'LXCpanButton' and isinstance(objs[iu].get('cue'), UID):
                panels_of.setdefault(uuid_of(int(objs[iu]['cue'])), set()).add(txt(objs[pu]['name']))
    member_of = {}
    for gu in R.find_instances(objs, 'LXPresetGroup'):
        if objs[gu].get('presetsAreMutuallyExclusive'):
            for c in kids(objs[gu].get('childNodes')):
                member_of.setdefault(c, set()).add(txt(objs[gu]['name']))
    for cu in R.find_instances(objs, 'LXCue'):
        groups_of[uuid_of(cu)] = {g for p in kids(objs[cu].get('presets')) for g in member_of.get(p, ())}

    rows = []
    for b in BD.list_bindings(objs, top):
        if b['kind'] != 'midi':
            continue
        rows.append({'channel': b['channel'], 'note': b['note'], 'cue': b['cue_name'] or '',
                     'panel': ' | '.join(sorted(panels_of.get(b['cue_uuid'], ()))),
                     'group': ' | '.join(sorted(groups_of.get(b['cue_uuid'], ()))),
                     'behaviour': BD.BEHAVIOUR_NAMES.get(b['behaviour'], b['behaviour']),
                     'on_off': b['on_off'], 'endpoint': b['endpoint'] or 'any', 'cue_uuid': b['cue_uuid']})
    rows.sort(key=lambda r: (r['channel'], r['note']))
    out = open(args.out, 'w', newline='') if args.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=list(rows[0]) if rows else ['channel', 'note', 'cue'])
    w.writeheader()
    w.writerows(rows)
    if args.out:
        out.close()
        dead = sum(1 for r in rows if not r['cue'])
        print(f'{len(rows)} note bindings ({dead} dead) -> {args.out}', file=sys.stderr)


if __name__ == '__main__':
    main()
