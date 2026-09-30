"""
Build a Stream Deck profile whose keys fire Lightkey cues, from three inputs:

  1. the user's own exported profile (.streamDeckProfile) — the template. It must contain at least
     one key using the "MIDI" plugin by Trevliga Spel (se.trevligaspel.midi.genericmidi) set to send
     a Note, and a Next Page and Previous Page key if the layout has more than one page. A Text key
     is optional (it becomes the page label). Everything else about the plugin's action shape is
     copied from that key, so the profile matches the plugin version the user actually has.
  2. the Lightkey show (.lightkeyproj) — the single source of truth for each cue's MIDI channel and
     note, its Lightkey behaviour, and the mutually exclusive group it belongs to.
  3. a layout (JSON) — which cue goes on which key of which page. See examples/streamdeck_layout.json.

The key MODE is derived, not chosen, from what the show says (docs/streamdeck-midi.md):

    cue in a mutually exclusive group, behaviour Flash  ->  Latch key in a latch group of that name
    not in a group, behaviour Flash                     ->  Hold key (lit while held)
    not in a group, behaviour Toggle / Activate         ->  Push key (one message per press)

and anything that could feed back on itself (Latch with Lightkey's "On/off" ticked, the pairing
that crashed Lightkey on a live rig) is refused rather than written.
"""
import colorsys
import copy
import io
import json
import os
import re
import subprocess
import sys
import uuid as _uuid
import zipfile
from plistlib import UID

from lightkey import bindings as BD
from lightkey import resolve as R
from lightkey.colour import unpack_rgb8

MIDI_PLUGIN = 'se.trevligaspel.midi.genericmidi'
TEXT = 'com.elgato.streamdeck.system.text'
NEXT, PREV = 'com.elgato.streamdeck.page.next', 'com.elgato.streamdeck.page.previous'
KNOWN_GRIDS = {'20GAA9902': (5, 3)}          # Stream Deck MK.2 (15 keys), verified
ZIP_TIME = (2026, 1, 1, 0, 0, 0)             # fixed, so a rebuild with the same input is byte-identical
NS = _uuid.UUID('9c2e71f4-0b86-4d3a-8e57-1f40a6c3b925')
GREY = '#8E8E93'
HERE = os.path.dirname(os.path.abspath(__file__))

CELLS = ('LABEL', 'NEXT', 'PREV')


class LayoutError(SystemExit):
    pass


def stable_id(*parts):
    return str(_uuid.uuid5(NS, ':'.join(str(p) for p in parts)))


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


# ---------------------------------------------------------------------------
# the template export
# ---------------------------------------------------------------------------

def read_template(path):
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
    package = json.loads(files['package.json'])
    prof_key = next(n for n in files if n.count('/') == 2 and n.endswith('.sdProfile/manifest.json'))
    profile = json.loads(files[prof_key])
    actions = [a for n, blob in files.items() if n.count('/') == 4 and n.endswith('/manifest.json')
               for c in (json.loads(blob)['Controllers'] or []) for a in (c['Actions'] or {}).values()]

    def first(uuid, pred=lambda a: True):
        return next((a for a in actions if a.get('UUID') == uuid and pred(a)), None)

    midi = first(MIDI_PLUGIN, lambda a: a.get('Settings', {}).get('g04') == 'Note')
    if midi is None:
        raise LayoutError('the template profile has no Trevliga MIDI key sending a Note: add one key with '
                          'the MIDI plugin set to Note, export the profile, and use that export')
    return {'package': package, 'profile': profile, 'midi': midi, 'text': first(TEXT),
            'next': first(NEXT), 'prev': first(PREV),
            'model': profile.get('Device', {}).get('Model') or package.get('DeviceModel')}


# ---------------------------------------------------------------------------
# what the show says about each cue
# ---------------------------------------------------------------------------

def _txt(objs, u):
    v = objs[int(u)] if isinstance(u, UID) else u
    if isinstance(v, dict):
        s = v.get('NS.string')
        return _txt(objs, s) if isinstance(s, UID) else s
    return v


def _kids(objs, u):
    o = objs[int(u)] if isinstance(u, UID) and int(u) else None
    return [int(x) for x in o.get('NS.objects', [])] if isinstance(o, dict) else []


def show_facts(show_path):
    """cue name -> list of {uuid, groups (mutex group names), bindings [...]} (names can repeat)."""
    data, objs = R.load(show_path)
    top = data['$top']
    owner = {}
    for gu in R.find_instances(objs, 'LXPresetGroup'):
        g = objs[gu]
        if g.get('presetsAreMutuallyExclusive'):
            for child in _kids(objs, g.get('childNodes')):
                owner.setdefault(child, []).append(_txt(objs, g['name']))
    by_uuid = {}
    for b in BD.list_bindings(objs, top):
        if b['kind'] == 'midi':
            by_uuid.setdefault(b['cue_uuid'], []).append(b)
    facts = {}
    for cu in R.find_instances(objs, 'LXCue'):
        c = objs[cu]
        uuid = str(R.resolve(objs, c.get('UUID'))).upper()
        groups = sorted({g for p in _kids(objs, c.get('presets')) for g in owner.get(p, [])})
        facts.setdefault(_txt(objs, c['name']), []).append(
            {'uuid': uuid, 'uid': cu, 'groups': groups, 'bindings': by_uuid.get(uuid, [])})
    return facts, objs


def look_palette(objs, cue_uid):
    """[deepest, palest] colour a cue shows (lit segments of its presets and sequence steps)."""
    import plistlib
    found = []
    for pu in _kids(objs, objs[cue_uid]['presets']):
        steps = _kids(objs, objs[pu].get('childNodes')) if R.classname(objs, objs[pu]) == 'LXSequence' else [pu]
        for k in steps:
            fp = objs[k].get('fpStore')
            if not isinstance(fp, UID) or not int(fp):
                continue
            for cont in plistlib.loads(objs[int(fp)]).get('umbrellaContainers', {}).values():
                for seg in cont.get('segmentContainers', []):
                    if seg.get('color') and seg.get('intensity', 1.0) > 0:
                        found.append(unpack_rgb8(seg['color'][0]))
    if not found:
        return [GREY]
    sat = lambda c: colorsys.rgb_to_hsv(*(x / 255 for x in c))[1]  # noqa: E731
    deep, pale = max(found, key=sat), min(found, key=sat)
    return ['#%02X%02X%02X' % deep] + (['#%02X%02X%02X' % pale] if pale != deep else [])


def plan_key(name, facts, layout):
    """Resolve one cue name on the layout to {channel, note, mode, latch, behaviour, ...}."""
    spec = layout.get('keys', {}).get(name, {})
    want_ch = spec.get('channel')
    channels = set(layout.get('channels') or [])
    cands = []
    for cue in facts.get(name, []):
        for b in cue['bindings']:
            if (want_ch is None or b['channel'] == want_ch) and (not channels or b['channel'] in channels):
                cands.append((cue, b))
    if not cands:
        raise LayoutError(f'{name!r}: no MIDI note in the show (on channels {sorted(channels) or "any"}). '
                          'Map one in Lightkey, or add it with lightkey.bindings.add_note_trigger.')
    if len(cands) > 1:
        opts = ', '.join(f'ch{b["channel"]}/{b["note"]}' for _, b in cands)
        raise LayoutError(f'{name!r} is bound more than once ({opts}): set "channel" for it under "keys", '
                          'or narrow "channels" for the whole layout')
    cue, b = cands[0]
    prefix = layout.get('group_prefix') or ''
    groups = [g for g in cue['groups'] if g.startswith(prefix)]
    if spec.get('group'):
        groups = [spec['group']]
    if len(groups) > 1:
        raise LayoutError(f'{name!r} is in several exclusive groups {groups}: set "group" for it under "keys"')
    behaviour = b['behaviour']
    if groups:
        mode = 'Latch'
    else:
        mode = 'Hold' if behaviour == BD.FLASH else 'Push'
    mode = spec.get('mode', mode)
    latch = layout.get('latch_prefix', 'Lightkey ') + groups[0][len(prefix):] if mode == 'Latch' and groups else None
    problems = []
    if b['on_off'] and mode in ('Latch', 'Toggle'):
        problems.append('Lightkey "On/off" is ticked on this trigger: a Latch/Toggle key also sends '
                        'note-offs, each would count as a press, and the cues can drive each other in a '
                        'loop. Untick On/off (it crashed Lightkey on a live rig). REFUSED.')
    if mode == 'Latch' and behaviour != BD.FLASH:
        problems.append(f'Latch key but Lightkey behaviour is {BD.BEHAVIOUR_NAMES.get(behaviour)}: pressing '
                        'the lit key sends a note-off that only Flash turns into "off". Set the trigger to '
                        'Flash (lightkey.bindings.set_behaviour).')
    return {'cue': name, 'channel': b['channel'], 'note': b['note'], 'mode': mode, 'latch': latch,
            'behaviour': behaviour, 'group': groups[0] if groups else None, 'cue_uid': cue['uid'],
            'problems': problems}


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build(template_path, show_path, layout, out_path, icons=False, icon_dir=None, strict=True):
    """Write `out_path`. Returns a summary dict. With icons=True (macOS only) renders 144px key
    icons and two preview sheets through AppKit; otherwise keys show their text as a title."""
    if os.path.exists(out_path):
        raise SystemExit(f'refusing to overwrite {out_path}')
    tpl = read_template(template_path)
    cols, rows = layout.get('grid') or KNOWN_GRIDS.get(tpl['model'], (5, 3))
    if tpl['model'] in KNOWN_GRIDS and KNOWN_GRIDS[tpl['model']] != (cols, rows):
        raise LayoutError(f'template is a {KNOWN_GRIDS[tpl["model"]]} deck, layout says {(cols, rows)}')
    pages = layout['pages']
    if len(pages) > 1 and not (tpl['next'] and tpl['prev']):
        raise LayoutError('more than one page, but the template has no Next Page / Previous Page key: '
                          'add both to the exported profile')

    facts, objs = show_facts(show_path)
    plans, seen = {}, set()
    for i, page in enumerate(pages):
        grid = page['keys']
        if len(grid) != rows or any(len(r) != cols for r in grid):
            raise LayoutError(f'page {i + 1} is not {cols} x {rows}')
        for row in grid:
            for cell in row:
                if cell is None or cell in CELLS:
                    continue
                if cell in seen:
                    raise LayoutError(f'{cell!r} appears twice: a latch group only redraws the page it is on')
                seen.add(cell)
                plans[cell] = plan_key(cell, facts, layout)
    problems = [(c, p) for c, pl in plans.items() for p in pl['problems']]
    if problems and strict:
        raise LayoutError('\n'.join(f'{c}: {p}' for c, p in problems))
    slots = [(p['channel'], p['note']) for p in plans.values()]
    if len(slots) != len(set(slots)):
        raise LayoutError('two keys send the same channel/note')

    # ---- key artwork
    look = {}
    for cell, pl in plans.items():
        spec = layout.get('keys', {}).get(cell, {})
        colors = spec.get('colors', 'look')
        if colors == 'look':
            colors = look_palette(objs, pl['cue_uid'])
        category = spec.get('category') or (pl['group'][len(layout.get('group_prefix') or ''):].upper()
                                            if pl['group'] else 'CUE')
        lines = spec.get('lines') or _default_lines(cell)
        look[cell] = {'category': category, 'lines': lines, 'colors': colors}

    icon_of = {}
    n_pages = len(pages)
    base = os.path.splitext(out_path)[0]
    if icons:
        icon_dir = icon_dir or base + '_icons'
        icon_of = _render_icons(look, pages, icon_dir, base, layout.get('profile_name', 'Lightkey'), cols, rows)

    # ---- pages
    midi_out = layout.get('midi_out', 'Lightkey Input')
    midi_in = layout.get('midi_in', 'Lightkey Output')
    page_ids, page_data = [], {}
    for i, page in enumerate(pages):
        label = page.get('label')
        acts, images = {}, {}
        for r_i, row in enumerate(page['keys']):
            for c_i, cell in enumerate(row):
                if cell is None:
                    continue
                pos = f'{c_i},{r_i}'
                if cell in ('NEXT', 'PREV'):
                    a = copy.deepcopy(tpl['next'] if cell == 'NEXT' else tpl['prev'])
                    a['ActionID'] = stable_id('nav', i, cell)
                elif cell == 'LABEL':
                    if tpl['text'] is None:
                        continue                        # no Text key in the template: leave it blank
                    a = copy.deepcopy(tpl['text'])
                    a['ActionID'] = stable_id('label', i)
                    title = ' '.join(label or [])
                    a['States'][0]['Title'] = title
                    if ('LABEL', i) in icon_of:
                        name = f'label_page{i + 1}.png'
                        a['States'][0].update({'Image': f'Images/{name}', 'ShowTitle': False})
                        images[name] = icon_of[('LABEL', i)]
                    else:
                        a['States'][0].update({'Title': '\n'.join(label or []), 'ShowTitle': True})
                else:
                    pl = plans[cell]
                    a = copy.deepcopy(tpl['midi'])
                    a['ActionID'] = stable_id('cue', cell)
                    s = a['Settings']
                    s['g45'] = s['g49'] = str(pl['note'])      # note number (both fields)
                    s['g47'] = str(pl['channel'] - 1)           # channel, 0-based
                    s['g04'] = 'Note'
                    s['g02'] = pl['mode']
                    if pl['latch']:
                        s['b14'] = pl['latch']
                    s['smo'], s['smi'] = midi_out, midi_in
                    states = a.get('States') or [{}, {}]
                    while len(states) < 2:
                        states.append(copy.deepcopy(states[0]))
                    a['States'] = states
                    if (cell, 'off') in icon_of:
                        for s_i, state in enumerate(('off', 'on')):
                            name = f'{slug(cell)}_{state}.png'
                            states[s_i].update({'Image': f'Images/{name}', 'ShowTitle': False})
                            images[name] = icon_of[(cell, state)]
                        states[0]['Title'] = cell
                    else:
                        for st in states:
                            st.update({'Title': '\n'.join(look[cell]['lines']), 'ShowTitle': True})
                acts[pos] = a
        pid = stable_id('page', i, ' '.join(label) if label else 'home')
        page_ids.append(pid)
        page_data[pid] = ({'Controllers': [{'Actions': acts, 'Type': 'Keypad'}], 'Icon': '', 'Name': ''}, images)
    default_id = stable_id('page', 'default')
    page_data[default_id] = ({'Controllers': [{'Actions': None, 'Type': 'Keypad'}], 'Icon': '', 'Name': ''}, {})

    name = layout.get('profile_name', 'Lightkey Service Panel')
    profile = copy.deepcopy(tpl['profile'])
    profile['Name'] = name
    profile['Pages'] = {'Current': '00000000-0000-0000-0000-000000000000', 'Default': default_id,
                        'Pages': page_ids}
    _write_zip(out_path, tpl['package'], profile, name, default_id, page_ids, page_data)

    from collections import Counter
    modes = Counter(p['mode'] for p in plans.values())
    groups = Counter(p['latch'] for p in plans.values() if p['latch'])
    spans = {g: sorted({i + 1 for i, pg in enumerate(pages) for row in pg['keys'] for c in row
                        if c in plans and plans[c]['latch'] == g}) for g in groups}
    return {'pages': n_pages, 'keys': len(plans), 'modes': dict(modes), 'latch_groups': dict(groups),
            'multi_page_groups': {g: p for g, p in spans.items() if len(p) > 1},
            'problems': problems, 'plans': plans, 'icons': bool(icon_of)}


def _default_lines(cue):
    tail = cue.split(': ', 1)[-1]
    words = tail.split()
    if len(words) <= 1:
        return [tail]
    half = (len(words) + 1) // 2
    return [' '.join(words[:half]), ' '.join(words[half:])]


def _write_zip(out_path, package, profile, name, default_id, page_ids, page_data):
    """The layout the Stream Deck app exports: compact sorted JSON, directory entries, page folders
    in UPPERCASE while manifests reference pages in lowercase."""
    prof_dir = f"Profiles/{stable_id('profile', name).upper()}.sdProfile/"
    dump = lambda o: json.dumps(o, separators=(',', ':'), ensure_ascii=False, sort_keys=True).encode()  # noqa: E731
    entries = [('package.json', dump(package)), ('Profiles/', None), (prof_dir, None),
               (prof_dir + 'Images/', None), (prof_dir + 'manifest.json', dump(profile)), (prof_dir + 'Profiles/', None)]
    for pid in [default_id] + page_ids:
        manifest, images = page_data[pid]
        d = f'{prof_dir}Profiles/{pid.upper()}/'
        entries += [(d, None), (d + 'Images/', None)]
        entries += [(d + 'Images/' + n, open(p, 'rb').read()) for n, p in sorted(images.items())]
        entries.append((d + 'manifest.json', dump(manifest)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for entry, blob in entries:
            zi = zipfile.ZipInfo(entry, ZIP_TIME)
            zi.create_system = 3
            if blob is None:
                zi.external_attr, zi.compress_type = (0o40755 << 16) | 0x10, zipfile.ZIP_STORED
                z.writestr(zi, b'')
            else:
                zi.external_attr, zi.compress_type = 0o100644 << 16, zipfile.ZIP_DEFLATED
                z.writestr(zi, blob)
    with open(out_path, 'wb') as f:
        f.write(buf.getvalue())


# ---------------------------------------------------------------------------
# icons (macOS: AppKit through JXA, nothing to install)
# ---------------------------------------------------------------------------

def _rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _lum(h):
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _hex(t):
    return '#%02X%02X%02X' % tuple(round(max(0.0, min(1.0, v)) * 255) for v in t)


def _accent(colors):
    c = max(colors, key=_lum)
    while _lum(c) < 0.2:
        c = _hex(tuple(x + (1 - x) * 0.25 for x in _rgb(c)))
    return c


def _ink(colors):
    avg = _hex(tuple(sum(_rgb(c)[i] for c in colors) / len(colors) for i in range(3)))
    contrast = lambda a, b: (max(_lum(a), _lum(b)) + 0.05) / (min(_lum(a), _lum(b)) + 0.05)  # noqa: E731
    return '#000000' if contrast(avg, '#000000') >= contrast(avg, '#FFFFFF') else '#FFFFFF'


def _render_icons(look, pages, icon_dir, base, title, cols, rows):
    if sys.platform != 'darwin':
        raise SystemExit('icons are rendered with macOS AppKit; run without --icons elsewhere')
    os.makedirs(icon_dir, exist_ok=True)
    specs, icon_of = [], {}
    for cue, lk in look.items():
        k = {'kind': 'key', 'category': lk['category'], 'lines': lk['lines'], 'colors': lk['colors'],
             'accent': _accent(lk['colors']), 'ink': _ink(lk['colors'])}
        k['pillInk'] = '#FFFFFF' if k['ink'] == '#000000' else '#000000'
        for state in ('off', 'on'):
            f = os.path.join(icon_dir, f'{slug(cue)}_{state}.png')
            specs.append(dict(k, state=state, file=f))
            icon_of[(cue, state)] = f
    for i, page in enumerate(pages):
        if page.get('label'):
            f = os.path.join(icon_dir, f'label_page{i + 1}.png')
            specs.append({'kind': 'label', 'lines': page['label'], 'sub': f'PAGE {i + 1} OF {len(pages)}', 'file': f})
            icon_of[('LABEL', i)] = f
    sheets = []
    for state in ('off', 'on'):
        blocks = []
        for i, page in enumerate(pages):
            cells = [[icon_of[('LABEL', i)] if c == 'LABEL' and ('LABEL', i) in icon_of
                      else c if c in ('NEXT', 'PREV') else None if c in (None, 'LABEL')
                      else icon_of[(c, state)] for c in row] for row in page['keys']]
            name = ' '.join(page['label']) if page.get('label') else f'PAGE {i + 1}'
            blocks.append({'title': f'Page {i + 1}  ·  {name}', 'cells': cells})
        sheets.append({'file': f'{base}_preview_{state}.png', 'cell': 72, 'gap': 8, 'columns': 3,
                       'gridCols': cols, 'gridRows': rows, 'blocks': blocks,
                       'title': f"{title}  ·  every key {'OFF' if state == 'off' else 'LIVE (cue active)'}"})
    spec_path = os.path.join(icon_dir, '_render_spec.json')
    with open(spec_path, 'w') as f:
        json.dump({'icons': specs, 'sheets': sheets}, f, indent=1, ensure_ascii=False)
    r = subprocess.run(['osascript', '-l', 'JavaScript', os.path.join(HERE, 'render_icons.js'), spec_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'icon rendering failed: {r.stderr.strip()}')
    return icon_of
