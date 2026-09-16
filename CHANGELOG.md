# Changelog

## Unreleased

**`lightkey/build.py`** — the `Builder` and constructors the docs have always called are now
shipped instead of left to the reader: `build_fpstore`, `mk_preset`, `mk_seq_preset`,
`mk_preset_group`, `mk_root_preset_group`, `mk_sequence`, `mk_cue`, `mk_button`,
`mk_text_label`, `clone_text_attrs`, `mk_cpan_frame`. Key sets match `docs/class-schemas.md`;
names are raw strings (Bug 14), no UID is hardcoded (Bug 15), font and colour objects are
discovered from the source file, empty collections reuse its singletons, and
`activeSpeedModifiers` / `LXCpanFrame.members` are NSSets. `mk_text_label` defaults to
`autoAdjustsWidth: False` — with `True` Lightkey re-measures on load and the box can grow over
neighbouring buttons (Bug 24). `mk_cpan_frame` adds the `LXCpanFrame` / `LXCanvasItem` class
definitions when the source file lacks them.

Previously `docs/patterns.md` and the SKILL quick-starts called `mk_sequence`, `mk_cpan_frame`,
`b.ns_array` and friends, while the only shipped builder was the cut-down one inside
`examples/build_dimmer_panel.py` with different method names (`array`, `nsset`, `uuid`) and no
sequence, label or frame constructors at all. The example now imports the shared module, so
there is one builder rather than two that disagree.

Verified end to end against a real 34-fixture project: 27 structural and semantic checks pass,
including mutex rockers, a one-shot cue, a 13pt cloned hint font and colour hues decoding back
to the families they were named for.

## 0.3.0 — 2026-09-30

A correctness fix in the shipped library, one new corner of the format, and a pass that removed
rig-identifying data from the docs.

**Corrections**
- `fp_dim()` wrote `shutterState 2` for an off state. 2 is **strobe**, so a layered cue that later
  raised intensity inherited a strobe — the exact trap `docs/pitfalls.md` warns about. It now
  writes `1` (open) unconditionally, like the other helpers. Anyone who built off states with
  `fp_dim()` on moving heads should rebuild them.
- `class-schemas.md` said name fields are `NSMutableString`; they are raw plist strings (Bug 14).
  Corrected everywhere it appeared.
- Pattern cross-references in `pitfalls.md` were off by one section; Bugs 27–29 were at the wrong
  heading level and escaped their section grouping; `patterns.md` contents now lists all 28
  sections.

**New format knowledge** (`docs/fpstore-format.md`)
- **Custom capabilities** (`LXCustomCapability` — Macro, Function, Haze, Fan Speed). A capability
  with no built-in Lightkey feature is named in `definedFeatures` as
  `custom--<PROFILE UUID>--<personality>--<index>`, where `<index>` is the capability's position
  **after sorting the personality's capabilities by channel offset**, not its raw array position.
  A profile that stores its capabilities out of channel order will otherwise be addressed on the
  wrong channel.
- That feature's value lives in `fixtureContainer`, not a `segmentContainer`, as
  `[settingIndex, fractionWithinThatSetting]`.
- `LXSetting` DMX range bytes are signed (`NS.type` 67 = signed char), so anything above 127 reads
  negative and must be masked with `& 0xFF`.

**Documentation hygiene**
- Removed rig-identifying data found by an independent audit of every tracked file: a person's
  name, a third-party project's preset names, a fixture model spec, a real patch address, and
  pan/tilt aims measured on one rig. Each is replaced by the rule it was evidence for, plus
  advice to read the value from your own profile and confirm aims on your own rig.

**Housekeeping**
- `colour.py` docstring imports from `lightkey.colour` rather than a loose `colour_helpers`.
- `build_skill_zip.py` no longer ships `.DS_Store` inside the bundle.
- Repository links updated after the GitHub repos were renamed.
- `lightkey.__version__` is `0.3.0`.

## 0.2.0 — 2026-09-08

Consolidates a second round of real-rig work (a MIDI-driven video opener sharing a file with a
hand-operated service panel).

**Corrections**
- `shutterState 2` is **strobe** (with `strobeSpeed`), not closed. How to decode the enum from a
  fixture profile's `LXShutterStrobeCapability.settings`. Off = intensity 0 + `shutterState 1`.

**New failure modes** (`docs/pitfalls.md`)
- Bug 27: a Python int written where a UID belongs parses fine and makes Lightkey decode the
  panel as empty — and re-save it empty. `Validator.references_are_uids()` (in
  `structural_parity()`) catches it.
- Bug 28: rebuilt cues get new UUIDs, silently orphaning MIDI/keyboard bindings.
- Bug 29: appending into a group that shares the empty-array singleton.
- Bug 26 refined: mutual exclusion is per preset member, not per cue.

**New patterns** (`docs/patterns.md` §23–§28): one-shot cues via finite `holdDuration`
(verified on hardware), timeline/MIDI show blocks with an EXIT cue, twin flows generated from a
static preset's stored bytes, carving into a layout the user likes, strobes and hard-cut chases,
moving-head position vocabulary.

**Schemas** (`docs/class-schemas.md`): MIDI/key bindings, `LXDMXFixture` → profile →
personality → capabilities, cue timing semantics, observed button tints.

**Tooling**: `inspect_project.py --midi` (dead bindings flagged);
`Validator.no_overlap(ignore_preexisting=True)`, `one_shot()`, `single_member_in()`,
`fixtures_dark()`. Segment-key vocabulary table in `docs/fpstore-format.md`.

**Scrub**: all examples now use generic zone names; nothing identifies a particular venue.

## 0.1.0 — first public release
