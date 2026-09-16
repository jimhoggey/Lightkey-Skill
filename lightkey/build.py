"""
Builder and constructors for writing new objects into a Lightkey archive.

This is the API that docs/patterns.md and the SKILL quick-starts already call.
It appends to an existing archive's `$objects`, reusing that file's class
definitions and empty-collection singletons instead of minting parallel ones.

    import plistlib
    from lightkey.build import Builder, build_fpstore, mk_preset, mk_cue, mk_button

    with open(src, 'rb') as f:
        archive = plistlib.load(f)

    b = Builder(archive)
    p = mk_preset(b, 'Front Wash 60%', build_fpstore(specs))
    c = mk_cue(b, 'Front Wash 60%', [p])
    btn = mk_button(b, c, 10, 10, 90, 44, tint='Blue')

Every constructor returns a `plistlib.UID`. Write those straight into your arrays
and reference fields — a bare `int` parses fine and then makes Lightkey decode the
whole array as empty (pitfalls.md Bug 27).

Names are RAW plist strings here, never `NSMutableString` wrappers (Bug 14), and
nothing in this module hardcodes a UID literal (Bug 15). Read docs/pitfalls.md
before using any of it.
"""

import plistlib
import uuid as _uuid
from plistlib import UID

UID_NULL = UID(0)


class Builder:
    """Appends objects to an existing archive, reusing its classes and singletons.

    Construct one per archive, after `plistlib.load()` and before you write
    anything. It scans `$objects` once for class definitions and for the shared
    empty NSArray / NSDictionary that real files already carry.
    """

    def __init__(self, archive):
        self.archive = archive
        self.objs = archive['$objects']
        self._cls = {o['$classname']: UID(i) for i, o in enumerate(self.objs)
                     if isinstance(o, dict) and '$classname' in o}
        self._empty_arr = self._empty_dict = None
        self._text_attrs = None
        na, nd = self._cls.get('NSArray'), self._cls.get('NSDictionary')
        for i, o in enumerate(self.objs):
            if not isinstance(o, dict):
                continue
            cref = o.get('$class')
            if self._empty_arr is None and cref == na and o.get('NS.objects') == []:
                self._empty_arr = UID(i)
            if (self._empty_dict is None and cref == nd
                    and o.get('NS.keys') == [] and o.get('NS.objects') == []):
                self._empty_dict = UID(i)

    # -- primitives ---------------------------------------------------------

    def add(self, obj):
        """Append any object and return its UID."""
        u = UID(len(self.objs))
        self.objs.append(obj)
        return u

    def cls(self, name):
        """UID of an EXISTING class definition. Never mints a duplicate."""
        if name not in self._cls:
            raise SystemExit(
                f'class {name!r} is not defined in this project — see pitfalls.md Bug 10. '
                f'Use add_class_def() only for classes you have confirmed in another '
                f'Lightkey file.')
        return self._cls[name]

    def add_class_def(self, classname, class_chain):
        """Add a class definition the source file lacks. Idempotent.

        Only for classes verified to exist in Lightkey itself — `LXCpanFrame` and
        `LXCanvasItem` are the usual cases. Inventing a plausible-sounding class
        name crashes Lightkey on open with no error message (SKILL rule 9).
        """
        if classname in self._cls:
            return self._cls[classname]
        uid = self.add({'$classname': classname, '$classes': list(class_chain)})
        self._cls[classname] = uid
        return uid

    def classname_of(self, obj):
        """Class name of an object dict (or None). Accepts a UID or the dict."""
        if isinstance(obj, (UID, int)):
            idx = int(obj)
            obj = self.objs[idx] if idx else None
        if isinstance(obj, dict) and isinstance(obj.get('$class'), UID):
            cdef = self.objs[int(obj['$class'])]
            return cdef.get('$classname') if isinstance(cdef, dict) else None
        return None

    _cn = classname_of      # the short name the docs' snippets use

    def raw_str(self, text):
        """A name / rect / tint: a RAW plist string, no class wrapper (Bug 14)."""
        return self.add(text)

    def mstr(self, text):
        """An NSMutableString. Only NSTextStorage's `NSString` field wants one —
        every `name` field wants raw_str instead."""
        return self.add({'NS.string': text, '$class': self.cls('NSMutableString')})

    def uuid_obj(self):
        return self.add({'NS.uuidbytes': _uuid.uuid4().bytes, '$class': self.cls('NSUUID')})

    def ns_array(self, uids, mutable=False):
        """NSArray of UIDs. An empty immutable one returns the file's shared
        singleton — so never mutate the result in place, or every other empty
        array in the file grows with it (Bug 29). Build the list first, mint last.
        """
        uids = list(uids)
        if not uids and not mutable and self._empty_arr is not None:
            return self._empty_arr
        return self.add({'NS.objects': uids,
                         '$class': self.cls('NSMutableArray' if mutable else 'NSArray')})

    def ns_dict(self, items=()):
        """NSDictionary from (key_uid, value_uid) pairs. Empty reuses the singleton."""
        items = list(items)
        if not items and self._empty_dict is not None:
            return self._empty_dict
        return self.add({'NS.keys': [k for k, _ in items],
                         'NS.objects': [v for _, v in items],
                         '$class': self.cls('NSDictionary')})

    def ns_set(self, uids):
        """NSSet — what `activeSpeedModifiers` and `LXCpanFrame.members` require,
        even when empty. An NSArray there is silently rejected (SKILL rule 6)."""
        return self.add({'NS.objects': list(uids), '$class': self.cls('NSSet')})

    # -- discovered styling -------------------------------------------------

    @property
    def text_attrs(self):
        """(fillColor, NSAttributes, strokeColor) borrowed from an existing label.

        Font and colour objects are found by walking for a real `LXTextCanvasItem`
        rather than hardcoding UIDs, which do not survive across files (Bug 15).
        """
        if self._text_attrs is None:
            self._text_attrs = self._find_text_attrs()
        return self._text_attrs

    def _find_text_attrs(self):
        for o in self.objs:
            if self.classname_of(o) != 'LXTextCanvasItem':
                continue
            fill, stroke = o.get('fillColor'), o.get('strokeColor')
            cref = o.get('contents')
            attrs = UID_NULL
            if isinstance(cref, UID):
                ts = self.objs[int(cref)]
                if isinstance(ts, dict) and isinstance(ts.get('NSAttributes'), UID):
                    attrs = ts['NSAttributes']
            if isinstance(fill, UID) and int(attrs):
                return fill, attrs, (stroke if isinstance(stroke, UID) else fill)
        raise SystemExit(
            'no LXTextCanvasItem in this project to copy font/colour from — add one '
            'label in Lightkey and re-export, or lift the NSAttributes structure from a '
            'reference project (class-schemas.md -> LXTextCanvasItem).')


# ---------------------------------------------------------------------------
# fpStore
# ---------------------------------------------------------------------------

def build_fpstore(fixture_specs, effects=None):
    """Serialise the inner binary plist an LXPreset carries (old schema).

    `fixture_specs` maps fixture UUID string -> {
        'defined_features':  ['Intensity', 'Color', 'Shutter', 'PanTilt', ...],
        'segment':           {...},          # the per-beam state
        'fixture_container': {...},          # optional, e.g. moving-head speed
    }

    Only declare the features you actually set — an intensity-only preset composes
    freely with a colour preset, a preset that declares both overrides both
    (patterns.md §2). See fpstore-format.md for the segment keys.
    """
    umbrella = {}
    for fixture_uuid, spec in fixture_specs.items():
        umbrella[fixture_uuid] = {
            'definedFeatures': list(spec['defined_features']),
            'fixtureContainer': spec.get('fixture_container', {}),
            'segmentContainers': [spec['segment']],
        }
    store = {'isMutable': False, 'umbrellaContainers': umbrella}
    if effects is not None:
        store['effects'] = effects
    return plistlib.dumps(store, fmt=plistlib.FMT_BINARY)


# ---------------------------------------------------------------------------
# Constructors — key sets match docs/class-schemas.md exactly
# ---------------------------------------------------------------------------

def mk_preset(b, name, fpstore_bytes):
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'active': False, 'childNodes': b.ns_array([]),
        'fpStore': b.add(fpstore_bytes),
        '$class': b.cls('LXPreset'),
    })


def mk_seq_preset(b, name, fpstore_bytes, duration=-1.0):
    """A sequence child: an LXPreset with the extra `duration` field.
    -1.0 means "use the sequence's own holdDuration"."""
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'active': False, 'childNodes': b.ns_array([]),
        'fpStore': b.add(fpstore_bytes),
        'duration': float(duration),
        '$class': b.cls('LXPreset'),
    })


def mk_preset_group(b, name, child_uids, mutually_exclusive=False):
    """A group. `mutually_exclusive` is what gives buttons rocker behaviour —
    and it only applies WITHIN one group, so join the user's existing group
    rather than creating a second one with the same intent (Bug 25)."""
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'childNodes': b.ns_array(child_uids),
        'presetsAreMutuallyExclusive': mutually_exclusive,
        '$class': b.cls('LXPresetGroup'),
    })


def mk_root_preset_group(b, name='Cue Orphan Presets Group'):
    """Mint a fresh one per cue — orphanPresetsGroup is never shared (SKILL rule 8)."""
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'childNodes': b.ns_array([]),
        'presetsAreMutuallyExclusive': False,
        '$class': b.cls('LXRootPresetGroup'),
    })


def mk_sequence(b, name, child_uids, hold=1.0, crossfade=0.5, repeat=0,
                autoreverses=False, smoothes_movements=True):
    """Cycle through sequence-child presets. Cycle time = N * (hold + crossfade),
    or 2 * (hold + crossfade) for a 2-step autoreversing pair.

    `crossfade=0.0` is a valid hard cut for chases and strobes (patterns.md §27).
    `repeat=0` loops forever; 1 plays once.
    """
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'active': False,
        'childNodes': b.ns_array(child_uids),
        'presetsAreMutuallyExclusive': False,
        'random': False, 'beatQuantum': 1, 'reversed': False,
        'holdDuration': float(hold),
        'hasVariableFadeTimes': False,
        'autoreverses': bool(autoreverses),
        'beatMultiplier': 24, 'speed': 1.0,
        'crossfadeDuration': float(crossfade),
        'smoothesFixtureMovements': bool(smoothes_movements),
        'usesConstantFixtureMovementVelocity': False,
        'repeatCount': int(repeat),
        'beatControlled': False, 'beatOffset': 0, 'freezesAtEnd': False,
        '$class': b.cls('LXSequence'),
    })


def mk_cue(b, name, preset_uids, fade_in=2.5, fade_out=2.5, priority=6, hold=-1.0):
    """A cue. `preset_uids` may hold LXPreset and/or LXSequence UIDs.

    `hold=-1.0` latches until something releases it. A finite hold makes the cue
    release itself — that is how one-shot hits for MIDI senders are built
    (patterns.md §23). Higher `priority` wins on the LTP stack.

    One member per mutex group per cue: two members of the same group displace
    each other (Bug 26).
    """
    empty = b.ns_dict()
    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'active': False, 'activateAtStartup': False, 'activateAtShutdown': False,
        'excludeFromLiveTriggers': False, 'requiresUnlockedApp': False,
        'fadeInDuration': float(fade_in), 'fadeOutDuration': float(fade_out),
        'fadeDuration': 0.5, 'holdDuration': float(hold),
        'priority': int(priority), 'intensity': 1.0,
        'presets': b.ns_array(preset_uids),
        'orphanPresetsGroup': mk_root_preset_group(b),
        'metaModifiers': empty, 'metaModifierDefaults': empty,   # same singleton
        'activeSpeedModifiers': b.ns_set([]),                    # NSSet, not NSArray
        'intensityFeatures': UID_NULL,
        '$class': b.cls('LXCue'),
    })


def mk_button(b, cue_uid, x, y, w, h, tint=None, momentary=False):
    """A panel button. `tint` is an AppKit colour NAME — 'Red', 'Orange', 'Yellow',
    'Green', 'Blue', 'Purple', 'Gray' — or None for untinted. Display only.

    On a button that already exists, rewrite `rect` and nothing else (Bug 21).
    """
    return b.add({
        'cue': cue_uid,
        'rect': b.raw_str(f'{{{{{x}, {y}}}, {{{w}, {h}}}}}'),
        'type': 0,
        'behavior': 1 if momentary else 0,
        'vertical': False,
        'titleAlignment': 0, 'titleUnderlineStyle': 0,
        'clusterRequiresSelection': False,
        'colorName': b.raw_str(tint) if tint else UID_NULL,
        'titleFont': UID_NULL,
        '$class': b.cls('LXCpanButton'),
    })


def mk_text_label(b, text, cx, cy, w, h, attrs=None, auto_width=False):
    """A section label. Positioned by CENTRE plus size — there is no `rect` — and
    the text renders at its own font size no matter what box you declare, so an
    undersized box puts text under your buttons (Bug 24). Keep `h` >= font size
    x 1.4 and check with `Validator.no_overlap()` / `labels_fit()`.

    `auto_width` stays False because you are computing the layout: with True,
    Lightkey re-measures the string on load and the box can grow across its
    neighbours. Pass `attrs` from `clone_text_attrs()` for a smaller hint font.
    """
    fill, default_attrs, stroke = b.text_attrs
    contents = b.add({
        'NSString': b.mstr(text), 'NSDelegate': UID_NULL,
        'NSAttributes': attrs if attrs is not None else default_attrs,
        '$class': b.cls('NSTextStorage'),
    })
    return b.add({
        'strokeWidth': 0.0, 'autoAdjustsWidth': bool(auto_width),
        'strokeColor': stroke,
        'unrotatedSize': b.raw_str(f'{{{w}, {h}}}'),
        'strokeOpacity': 0.0, 'fillOpacity': 0.0, 'opacity': 1.0,
        'center': b.raw_str(f'{{{cx}, {cy}}}'),
        'fillColor': fill,
        'contents': contents,
        'strokeType': 0, 'splineKnots': UID_NULL, 'angleCCW': 0.0,
        '$class': b.cls('LXTextCanvasItem'),
    })


def clone_text_attrs(b, size):
    """An NSAttributes dict at a different font size, for helper text under a title.

    Clones the project's own attributes and NSFont and changes only `NSSize`, so no
    new class definitions are involved (class-schemas.md -> Mixed font sizes).
    """
    _fill, attrs_uid, _stroke = b.text_attrs
    attrs = b.objs[int(attrs_uid)]
    keys = [b.objs[int(k)] if isinstance(k, UID) else k for k in attrs['NS.keys']]
    if 'NSFont' not in keys:
        raise SystemExit('the project label attributes carry no NSFont to clone')
    values = list(attrs['NS.objects'])
    font = dict(b.objs[int(values[keys.index('NSFont')])])
    font['NSSize'] = float(size)
    values[keys.index('NSFont')] = b.add(font)
    return b.add({'NS.keys': list(attrs['NS.keys']), 'NS.objects': values,
                  '$class': attrs['$class']})


def mk_cpan_frame(b, name, x, y, w, h, member_button_uids,
                  show_speed_slider=True, priority=10):
    """A titled bounding box around buttons, optionally with live sliders.

    The buttons must ALSO stay in the panel's own `items` array — the frame points
    at them, it doesn't contain them — and they keep absolute panel coordinates.

    Adds the `LXCpanFrame` / `LXCanvasItem` class definitions if the source file
    lacks them; both are real Lightkey classes.
    """
    b.add_class_def('LXCanvasItem', ['LXCanvasItem', 'LXCanvasItemObjC', 'NSObject'])
    b.add_class_def('LXCpanFrame', ['LXCpanFrame', 'LXCanvasItem',
                                    'LXCanvasItemObjC', 'NSObject'])

    if show_speed_slider:
        # Keys are raw strings and values raw floats; the 1.0 is shared by all three.
        one = b.add(1.0)
        meta = b.ns_dict([(b.raw_str('fadeTime'), one),
                          (b.raw_str('intensity'), one),
                          (b.raw_str('speed'), one)])
    else:
        meta = b.ns_dict()

    return b.add({
        'name': b.raw_str(name), 'UUID': b.uuid_obj(),
        'rect': b.raw_str(f'{{{{{x}, {y}}}, {{{w}, {h}}}}}'),
        'members': b.ns_set(member_button_uids),
        'showsBackButton': False, 'showsForwardButton': False,
        'priority': int(priority),
        'titleAlignment': 0, 'titleUnderlineStyle': 0,
        'titleFont': UID_NULL,
        'metaModifiers': meta,
        'metaModifierDefaults': b.ns_dict(),
        'activeSpeedModifiers': b.ns_set([]),
        '$class': b.cls('LXCpanFrame'),
    })
