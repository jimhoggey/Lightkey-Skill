#!/usr/bin/env python3
"""
Check a Stream Deck profile against the Lightkey show it drives, and optionally diff it against the
profile it replaces.

    python3 tools/check_streamdeck_profile.py Panel_v5.streamDeckProfile MyShow_v5.lightkeyproj
    python3 tools/check_streamdeck_profile.py Panel_v5.streamDeckProfile MyShow_v5.lightkeyproj \\
        --against Panel_v4.streamDeckProfile

Works on any profile, including one made by hand in the Stream Deck app: every MIDI key must reach
a real cue, and no key may pair with a trigger in a way that has failed on a live rig
(streamdeck/check.py lists the rules). Exit status 1 on any FAIL.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streamdeck import check as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('profile')
    ap.add_argument('show')
    ap.add_argument('--against', help='previous .streamDeckProfile to diff with')
    ap.add_argument('--port', default='Lightkey Input', help='MIDI port the keys should send to')
    args = ap.parse_args()

    result = C.check(args.profile, args.show, midi_port=args.port)
    for w in result['warns']:
        print('WARN', w)
    for f in result['fails']:
        print('FAIL', f)
    print(f"{result['keys']} MIDI keys: {len(result['fails'])} failures, {len(result['warns'])} warnings")

    if args.against:
        d = C.diff(args.against, args.profile)
        print(f"\nagainst {os.path.basename(args.against)}:")
        print('  added:  ', d['added'] or 'none')
        print('  removed:', d['removed'] or 'none')
        for title, ch in d['changed'].items():
            print(f'  changed: {title}: ' + ', '.join(f'{f} {a!r} -> {b!r}' for f, (a, b) in ch.items()))
        if not d['changed']:
            print('  changed: none')
    sys.exit(1 if result['fails'] else 0)


if __name__ == '__main__':
    main()
