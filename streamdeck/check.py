"""
Check a Stream Deck profile against the Lightkey show it drives — and optionally diff it against
the previous profile — without touching either.

Every rule here is one that failed on a live rig before it was written down
(docs/streamdeck-midi.md, "Key modes and Lightkey behaviours"):

  FAIL  a key sends a channel/note no cue listens to (the key does nothing)
  FAIL  a Latch or Toggle key drives a trigger with Lightkey's "On/off" ticked (feedback loop;
        crashed Lightkey)
  FAIL  a Latch key drives a cue whose trigger is not Flash (the lit key cannot switch it off)
  FAIL  one latch group maps to cues from different Lightkey exclusive groups, or one Lightkey
        group is split across several latch groups (keys and cues disagree about what is lit)
  FAIL  two keys send the same channel/note
  WARN  a latch group spans pages (the deck only redraws the page it shows: a stale lit key)
  WARN  a Hold key on a non-Flash trigger, a Push key on a Flash trigger (stuck on until another
        cue displaces it), a key whose two note fields disagree, a port that is not Lightkey's
"""
import json
import zipfile

from lightkey import bindings as BD
from lightkey import resolve as R

from .profile import MIDI_PLUGIN, show_facts


def read_keys(path):
    """[{page, pos, title, mode, channel, note, note2, latch, out, in}] for every MIDI key."""
    keys = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        prof = json.loads(z.read(next(n for n in names if n.count('/') == 2 and n.endswith('.sdProfile/manifest.json'))))
        order = [p.lower() for p in prof.get('Pages', {}).get('Pages', [])]
        for n in names:
            if n.count('/') != 4 or not n.endswith('/manifest.json'):
                continue
            page_id = n.split('/')[3].lower()
            page = order.index(page_id) + 1 if page_id in order else 0
            for c in json.loads(z.read(n))['Controllers'] or []:
                for pos, a in (c['Actions'] or {}).items():
                    if a.get('UUID') != MIDI_PLUGIN:
                        continue
                    s = a.get('Settings', {})
                    keys.append({'page': page, 'pos': pos, 'title': (a.get('States') or [{}])[0].get('Title'),
                                 'mode': s.get('g02'), 'channel': int(s.get('g47', 0)) + 1,
                                 'note': int(s.get('g45', -1)), 'note2': int(s.get('g49', s.get('g45', -1))),
                                 'latch': s.get('b14') if s.get('g02') == 'Latch' else None,
                                 'out': s.get('smo'), 'in': s.get('smi'), 'type': s.get('g04')})
    return sorted(keys, key=lambda k: (k['page'], k['pos']))


def check(profile_path, show_path, midi_port='Lightkey Input'):
    fails, warns = [], []
    keys = read_keys(profile_path)
    facts, objs = show_facts(show_path)
    data, _ = R.load(show_path)
    slot = {(b['channel'], b['note']): b for b in BD.list_bindings(objs, data['$top']) if b['kind'] == 'midi'}
    groups_of = {c['uuid']: c['groups'] for cs in facts.values() for c in cs}

    seen = {}
    latch_to_groups, group_to_latch, latch_pages = {}, {}, {}
    for k in keys:
        where = f'page {k["page"]} key {k["pos"]} ({k["title"]!r})'
        s = (k['channel'], k['note'])
        if s in seen:
            fails.append(f'{where}: sends ch{s[0]}/{s[1]}, same as {seen[s]}')
        seen[s] = where
        if k['note'] != k['note2']:
            warns.append(f'{where}: the plugin\'s two note fields disagree ({k["note"]} vs {k["note2"]})')
        if k['type'] != 'Note':
            warns.append(f'{where}: message type is {k["type"]!r}, not Note')
        if k['out'] != midi_port:
            warns.append(f'{where}: MIDI out is {k["out"]!r}, not {midi_port!r}')
        b = slot.get(s)
        if b is None:
            fails.append(f'{where}: ch{s[0]}/{s[1]} is not bound to any cue in the show — the key does nothing')
            continue
        if b['cue_name'] is None:
            fails.append(f'{where}: ch{s[0]}/{s[1]} is bound to a cue that no longer exists (Bug 28)')
            continue
        cue = b['cue_name']
        if b['on_off'] and k['mode'] in ('Latch', 'Toggle'):
            fails.append(f'{where} -> {cue}: {k["mode"]} key on a trigger with "On/off" ticked — feedback loop, '
                         'this crashed Lightkey. Untick On/off.')
        if k['mode'] == 'Latch':
            if b['behaviour'] != BD.FLASH:
                fails.append(f'{where} -> {cue}: Latch key but the trigger is '
                             f'{BD.BEHAVIOUR_NAMES.get(b["behaviour"])}, not Flash: pressing the lit key cannot '
                             'switch the cue off')
            grp = tuple(groups_of.get(b['cue_uuid'], []))
            if not grp:
                warns.append(f'{where} -> {cue}: Latch key, but the cue is in no exclusive group in Lightkey')
            latch_to_groups.setdefault(k['latch'], set()).add(grp)
            for g in grp:
                group_to_latch.setdefault(g, set()).add(k['latch'])
            latch_pages.setdefault(k['latch'], set()).add(k['page'])
        elif k['mode'] == 'Hold' and b['behaviour'] != BD.FLASH:
            warns.append(f'{where} -> {cue}: Hold key but trigger is {BD.BEHAVIOUR_NAMES.get(b["behaviour"])}; '
                         'Flash makes it lit exactly while held')
        elif k['mode'] == 'Push' and b['behaviour'] == BD.FLASH:
            warns.append(f'{where} -> {cue}: Push key sends one message and never an off, so a Flash cue stays '
                         'on until something displaces it; use Toggle behaviour or a Hold key')
        elif k['mode'] == 'Toggle' and not b['on_off']:
            warns.append(f'{where} -> {cue}: plugin Toggle alternates on/off messages; with On/off unticked '
                         'Lightkey ignores the offs, so every other press does nothing')

    for latch, grps in latch_to_groups.items():
        if len(grps) > 1:
            fails.append(f'latch group {latch!r} mixes cues from different Lightkey groups {sorted(grps)}')
    for grp, latches in group_to_latch.items():
        if len(latches) > 1:
            fails.append(f'Lightkey group {grp!r} is split across latch groups {sorted(latches)}')
    for latch, pages in latch_pages.items():
        if len(pages) > 1:
            warns.append(f'latch group {latch!r} spans pages {sorted(pages)}: a key lit on a page you are not '
                         'looking at stays lit when another member is pressed (press any key on that page to fix)')
    return {'keys': len(keys), 'fails': fails, 'warns': warns}


def diff(old_path, new_path):
    """MIDI keys added, removed or changed between two profiles, matched by page and position
    (titles need not be unique: two keys can both read "Sage"). Keys are labelled
    'p<page> <col>,<row> <title>'."""
    a = {(k['page'], k['pos']): k for k in read_keys(old_path)}
    b = {(k['page'], k['pos']): k for k in read_keys(new_path)}
    fields = ('title', 'mode', 'channel', 'note', 'latch', 'out', 'in')
    name = lambda s, k: f'p{s[0]} {s[1]} ' + str(k['title']).replace('\n', ' ')  # noqa: E731
    return {'added': [name(s, b[s]) for s in sorted(set(b) - set(a))],
            'removed': [name(s, a[s]) for s in sorted(set(a) - set(b))],
            'changed': {name(s, b[s]): {f: (a[s][f], b[s][f]) for f in fields if a[s][f] != b[s][f]}
                        for s in sorted(set(a) & set(b)) if any(a[s][f] != b[s][f] for f in fields)}}
