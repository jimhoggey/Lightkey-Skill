#!/usr/bin/env python3
"""
Build a Stream Deck profile whose keys fire Lightkey cues over MIDI.

    python3 tools/build_streamdeck_profile.py \\
        --template "My Export.streamDeckProfile" \\
        --show MyShow_v5.lightkeyproj \\
        --layout layout.json \\
        --out Lightkey_Service_Panel.streamDeckProfile [--icons]

--template  a profile the user exported from the Stream Deck app, containing one key that uses the
            Trevliga Spel "MIDI" plugin set to Note, plus Next Page / Previous Page keys (and
            optionally a Text key for page labels). Its plugin settings are cloned for every key.
--show      the Lightkey project. Each cue's channel and note, its Lightkey behaviour and its
            exclusive group come from here, so the deck cannot disagree with the show.
--layout    JSON: which cue sits on which key. See examples/streamdeck_layout.json.
--icons     macOS only: render coloured key icons and two preview sheets (OFF / LIVE).

The profile is checked against the show before it is written; unsafe pairings are refused.
Read docs/streamdeck-midi.md first.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streamdeck import check as C  # noqa: E402
from streamdeck import profile as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--template', required=True)
    ap.add_argument('--show', required=True)
    ap.add_argument('--layout', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--icons', action='store_true')
    ap.add_argument('--icon-dir')
    args = ap.parse_args()

    layout = json.load(open(args.layout, encoding='utf-8'))
    summary = P.build(args.template, args.show, layout, args.out, icons=args.icons, icon_dir=args.icon_dir)
    groups = ', '.join(f'{g}={n}' for g, n in sorted(summary['latch_groups'].items()))
    print(f"{summary['pages']} pages, {summary['keys']} cue keys, modes {summary['modes']}")
    print(f'latch groups: {groups or "none"}')
    for g, pages in summary['multi_page_groups'].items():
        print(f'note: latch group {g!r} spans pages {pages} (a key lit on another page can go stale)')
    print(f'wrote {args.out}' + (' (+ icons and preview sheets)' if summary['icons'] else ''))

    result = C.check(args.out, args.show, midi_port=layout.get('midi_out', 'Lightkey Input'))
    for w in result['warns']:
        print('WARN', w)
    for f in result['fails']:
        print('FAIL', f)
    print(f"check: {result['keys']} keys, {len(result['fails'])} failures, {len(result['warns'])} warnings")
    sys.exit(1 if result['fails'] else 0)


if __name__ == '__main__':
    main()
