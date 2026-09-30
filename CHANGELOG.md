# Changelog

## 0.5.0 — 2026-09-30

A revision workflow for shows that already run, the Lightkey side of MIDI as a library, and an
optional second skill that builds Stream Deck profiles for the cues. Two bundles from this release
on: `lightkey-patcher-skill.zip` (as before) and `lightkey-streamdeck-skill.zip` (the add-on).
The plugin manifests move from `0.2.0` straight to `0.5.0` — they were not bumped for 0.3.0 or
0.4.0, so Claude Code installs never saw those updates; `/plugin marketplace update lightkey-format`
now brings everything since 0.2.0.

### Revising a show that already runs

**`docs/update-workflow.md`** — the loop the SKILL was missing: ten stages from request to
hand-off, each with a gate. Build on the user's newest Lightkey save (never your last output);
diagnose every "it doesn't work" before changing anything (a symptom → cause table); route each
change to the doc section and helper it needs (a request → knowledge table); ask only the real
choices, with a recommended option; build in place; validate in three layers; hand off with an
ordered rig test and a rollback file; write hardware results back into the docs. `SKILL.md` now
summarises it and points there for every revision.

**`examples/revision/`** — `build_next.py` and `validate_next.py`, the templates a revision copies:
refuse to overwrite, re-find by name scoped to one panel (names repeat across panels), edit in
place, counted assertions; and structure → preservation → semantics checks.

**`lightkey/validate.py`**
- `unchanged_except(presets, cues)`: every preset (by fpStore bytes) and cue (timing, priority)
  you did not name is exactly what the user saved, matched by UUID. The check that lets a revision
  say "nothing else changed".
- `bindings_intact()`: every source MIDI/key binding survives with the same trigger and cue.
- `Validator(src, out, panel='Name')`: the panel checks no longer assume `$top.selectedLivePanel`,
  which Lightkey 6 re-saves can drop (the checks raised `KeyError` on such files).

**`lightkey/bindings.py`** — list MIDI and keyboard bindings, find free notes, add note triggers
(cloned from one the user made in the GUI; refuses a used note; stable binding UUIDs), change a
trigger's behaviour. Proven across ten shipped versions with ~260 triggers.

**`tools/export_midi_map.py`** — the show's MIDI map as CSV (channel, note, cue, panel, group,
behaviour, On/off, port); dead bindings show an empty cue.

**Docs**
- `fpstore-format.md` → Custom capabilities → **Built-in programmes and modes, in practice**:
  what a weekly-revised show added to 0.3.0's encoding — Lightkey reshuffles the capabilities
  array between saves (so the channel sort is the only stable index), a key for the wrong
  personality silently does nothing, default values vanish on re-save, 0.5 lands mid-band on a
  stepped setting, programmes still need Intensity, and "works in Design view" means outranked.
- `class-schemas.md` → Bindings: the full `activationBehavior` enum (0 Toggle, 1 Flash, 2 Activate,
  3 Deactivate), 0-based channels, `onOff`, `endpointName` $null = any port; scripted bindings are
  no longer "not exercised".
- `pitfalls.md` Bugs 30–32: a cue outranked by priority (works in Design view, not as a cue);
  controller note-offs + "On/off" ticked → feedback loop and crash; custom-capability index counted
  in array order.

### Optional add-on: Stream Deck profiles over MIDI

**`skills/lightkey-streamdeck/`** — a second skill in the plugin, used only when the user asks for
Stream Deck keys or the show already has a profile. **`docs/streamdeck-midi.md`** holds everything
learned driving a show from a 15-key Stream Deck over ten versions: the plugin and Lightkey's
`Lightkey Input` / `Lightkey Output` ports and feedback; which Stream Deck key mode pairs with which
Lightkey trigger behaviour (Latch ↔ Flash, Push ↔ Toggle, Hold ↔ Flash; never On/off with Latch);
latch groups (global across profiles, one per Lightkey group, only redraw the visible page);
App Nap and start order on the booth Mac; a rig test order; the profile file format and the
plugin's settings fields.

**`streamdeck/`** with **`tools/build_streamdeck_profile.py`** and
**`tools/check_streamdeck_profile.py`**: build a profile from the user's exported profile + the show +
a layout JSON (`examples/streamdeck_layout.json`), deriving each key's note, mode and latch group from
the show so the deck cannot disagree with it; optional AppKit-rendered key icons and preview sheets
on macOS; refuses unsafe pairings; checks any profile against a show and diffs it against the
previous one. Verified by regenerating a hand-built 12-page, 105-key production profile exactly
(every note, channel, mode, latch group and position), and by running the checker against the
profile/show pair that crashed Lightkey on the rig: it fails every affected key.

**`tools/build_skill_zip.py`** builds one claude.ai bundle per skill
(`lightkey-patcher-skill.zip`, `lightkey-streamdeck-skill.zip`).

- `lightkey.__version__`, `plugin.json` and `marketplace.json` are `0.5.0`.

## 0.4.0 — 2026-09-30

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
to the families they were named for. Re-verified before release against a 36-fixture project:
`examples/build_dimmer_panel.py` builds a five-step dimmer row and the output passes 13 checks,
including key-set parity for every class it mints and `references_are_uids()`.

**Note for anyone on 0.3.0 or earlier**: the skill bundle shipped `lightkey/` without
`build.py`, so the constructors `docs/patterns.md` calls were not importable. Re-download
`lightkey-patcher-skill.zip` from this release.

- `lightkey.__version__` is `0.4.0`.

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
