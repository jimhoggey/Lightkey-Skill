"""
MIDI (and keyboard) bindings: read Lightkey's trigger map, find free notes, add note triggers.

This is the Lightkey half of linking an external controller — a Stream Deck, a DAW, a
ProPresenter timeline — to cues. The controller half lives in `streamdeck/`; the design rules
that make the two agree are in `docs/streamdeck-midi.md`.

    from lightkey.bindings import list_bindings, free_notes, add_note_trigger, FLASH

    for bnd in list_bindings(objs, top):
        print(bnd['channel'], bnd['note'], bnd['cue_name'], bnd['behaviour'])

    b = Builder(archive)
    for cue_uid, note in zip(new_cues, free_notes(objs, top, channel=4, count=len(new_cues))):
        add_note_trigger(b, top, cue_uid, channel=4, note=note, behaviour=FLASH)

Channels are 1-based everywhere in this API, the way a person and a Stream Deck plugin count
them. Lightkey stores them 0-based; the conversion happens here and nowhere else.

`add_note_trigger` clones the trigger and action shape from a binding the user made in
Lightkey's GUI, so the file must already contain at least one MIDI binding. Map one note by hand
in Lightkey first if it has none — minting LXMIDITrigger from the schema alone is the kind of
guess stability rule 9 warns about.
"""
import uuid as _uuid
from plistlib import UID

from . import resolve as R

# LXAction.params.activationBehavior — verified against the app's own strings and on a rig.
TOGGLE, FLASH, ACTIVATE, DEACTIVATE = 0, 1, 2, 3
BEHAVIOUR_NAMES = {TOGGLE: 'toggle', FLASH: 'flash', ACTIVATE: 'activate', DEACTIVATE: 'deactivate'}
NOTE_COMMAND = 159          # LXMIDITrigger.commandType observed for note messages

_NS = _uuid.UUID('6f9619ff-8b86-d011-b42d-00c04fc964ff')


def _deref(objs, u):
    return objs[int(u)] if isinstance(u, UID) else u


def _txt(objs, u):
    v = _deref(objs, u)
    if isinstance(v, dict):
        s = v.get('NS.string')
        return _txt(objs, s) if isinstance(s, UID) else s
    return v


def _kids(objs, u):
    o = _deref(objs, u)
    return list(o.get('NS.objects', [])) if isinstance(o, dict) else []


def _params(objs, action):
    p = _deref(objs, _deref(objs, action)['params'])
    return {_txt(objs, k): v for k, v in zip(p['NS.keys'], p['NS.objects'])}


def configuration(objs, top, category='MIDIBindingsCategory'):
    """The LXBindingsConfiguration currently in use for a category, or None."""
    cat = top.get(category)
    if not isinstance(cat, UID) or not int(cat):
        return None
    cfg = _deref(objs, objs[int(cat)].get('currentConfiguration'))
    return cfg if isinstance(cfg, dict) else None


def cue_names_by_uuid(objs):
    return {str(R.resolve(objs, objs[u].get('UUID'))).upper(): _txt(objs, objs[u].get('name'))
            for u in R.find_instances(objs, 'LXCue')}


def list_bindings(objs, top):
    """Every MIDI and keyboard binding, as plain dicts:
    kind ('midi'|'key'), channel (1-based) and note for MIDI, key for keyboard, cue_uuid,
    cue_name (None when the cue no longer exists — Bug 28), behaviour (int), on_off, endpoint."""
    names = cue_names_by_uuid(objs)
    out = []
    for category, kind in (('MIDIBindingsCategory', 'midi'), ('keyBindingsCategory', 'key')):
        cfg = configuration(objs, top, category)
        if cfg is None:
            continue
        for bu in _kids(objs, cfg.get('bindings')):
            bnd = objs[int(bu)]
            trig = _deref(objs, bnd['trigger'])
            prm = _params(objs, bnd['action'])
            cue = R.resolve(objs, prm.get('cueUUID'))
            cue = str(cue).upper() if cue else None
            row = {'kind': kind, 'binding_uid': int(bu), 'cue_uuid': cue, 'cue_name': names.get(cue),
                   'behaviour': _deref(objs, prm.get('activationBehavior')),
                   'channel': None, 'note': None, 'key': None, 'on_off': None, 'endpoint': None}
            if kind == 'midi':
                ep = trig.get('endpointName')
                row.update(channel=trig['channel'] + 1, note=trig['note'], on_off=trig.get('onOff'),
                           command=trig.get('commandType'),
                           endpoint=_txt(objs, ep) if isinstance(ep, UID) and int(ep) else None)
            else:
                sc = _deref(objs, trig.get('shortcut'))
                row['key'] = _txt(objs, sc.get('characters')) if isinstance(sc, dict) else None
            out.append(row)
    return out


def used_slots(objs, top):
    """{(channel 1-based, note)} already taken by a MIDI binding."""
    return {(b['channel'], b['note']) for b in list_bindings(objs, top) if b['kind'] == 'midi'}


def free_notes(objs, top, channel, count=1, start=0, stop=127):
    """The first `count` unused notes on `channel` (1-based), lowest first."""
    taken = {n for c, n in used_slots(objs, top) if c == channel}
    free = [n for n in range(start, stop + 1) if n not in taken]
    if len(free) < count:
        raise SystemExit(f'only {len(free)} free notes on channel {channel} in {start}-{stop}')
    return free[:count]


def _template(objs, top):
    cfg = configuration(objs, top)
    if cfg is None or not _kids(objs, cfg.get('bindings')):
        raise SystemExit('this project has no MIDI binding to clone: map one note to any cue in '
                         "Lightkey's GUI, save, and run again (docs/streamdeck-midi.md)")
    for bu in _kids(objs, cfg['bindings']):
        bnd = objs[int(bu)]
        trig = _deref(objs, bnd['trigger'])
        if trig.get('commandType') == NOTE_COMMAND:
            p = _deref(objs, _deref(objs, bnd['action'])['params'])
            keys = {_txt(objs, k): k for k in p['NS.keys']}
            if set(keys) == {'type', 'activationBehavior', 'cueUUID'}:
                return cfg, dict(trig), keys, p['NS.objects'][list(p['NS.keys']).index(keys['type'])]
    raise SystemExit('no note binding with the expected action shape to clone')


_KEEP = object()


def add_note_trigger(b, top, cue_uid, channel, note, behaviour=FLASH, on_off=False, endpoint=_KEEP):
    """Bind a MIDI note to a cue. Returns the new LXBinding UID.

    channel   1-based
    behaviour FLASH (note-on activates, note-off deactivates) is the one a Stream Deck Latch or
              Hold key needs; TOGGLE for a Push key. See docs/streamdeck-midi.md before choosing.
    on_off    Lightkey's "On/off" tick. Leave it False: with True every message counts as a press,
              and a controller that sends note-offs (Latch keys do) makes cues toggle each other
              in a loop — that combination has crashed Lightkey.
    endpoint  _KEEP copies the template's input port; None = any port; or a port name.

    The binding UUID is derived from cue + channel + note, so re-running a build is stable.
    Refuses a channel/note already in use.
    """
    objs = b.objs
    if (channel, note) in used_slots(objs, top):
        raise SystemExit(f'MIDI channel {channel} note {note} is already bound')
    cfg, trig, keys, toggle_cue_value = _template(objs, top)
    trig.update(channel=channel - 1, note=note, onOff=bool(on_off), commandType=NOTE_COMMAND)
    if endpoint is None:
        trig['endpointName'] = UID(0)
    elif endpoint is not _KEEP:
        trig['endpointName'] = b.raw_str(endpoint)
    cue_bytes = objs[int(objs[int(cue_uid)]['UUID'])]['NS.uuidbytes']
    behaviour_uid = next((UID(i) for i, o in enumerate(objs) if type(o) is int and o == behaviour), None)
    if behaviour_uid is None:
        behaviour_uid = b.add(int(behaviour))
    params = b.ns_dict([(keys['type'], toggle_cue_value), (keys['activationBehavior'], behaviour_uid),
                        (keys['cueUUID'], b.add({'NS.uuidbytes': cue_bytes, '$class': b.cls('NSUUID')}))])
    action = b.add({'params': params, '$class': b.cls('LXAction')})
    bid = _uuid.uuid5(_NS, f'{cue_bytes.hex()}:{channel}:{note}')
    binding = b.add({'UUID': b.add({'NS.uuidbytes': bid.bytes, '$class': b.cls('NSUUID')}),
                     'action': action, 'trigger': b.add(trig), '$class': b.cls('LXBinding')})
    # Every element a UID, never a bare int (Bug 27); mint the array last (Bug 29).
    cfg['bindings'] = b.ns_array([UID(int(x)) for x in _kids(objs, cfg['bindings'])] + [binding])
    return binding


def set_behaviour(b, top, binding_uid, behaviour):
    """Change one existing binding's activationBehavior. The binding keeps its UUID and trigger;
    it gets a fresh action + params pair rather than an in-place edit, because an action or params
    object shared with another binding would otherwise change both."""
    objs = b.objs
    action = _deref(objs, objs[binding_uid]['action'])
    p = _deref(objs, action['params'])
    keys = [_txt(objs, k) for k in p['NS.keys']]
    values = list(p['NS.objects'])
    uid = next((UID(j) for j, o in enumerate(objs) if type(o) is int and o == behaviour), None)
    values[keys.index('activationBehavior')] = uid if uid is not None else b.add(int(behaviour))
    params = b.ns_dict(list(zip(p['NS.keys'], values)))
    objs[binding_uid] = dict(objs[binding_uid], action=b.add(dict(action, params=params)))
