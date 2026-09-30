# Updating a show the user already runs

The SKILL's three phases (inspect, clarify, build) describe making something. This is the loop for
**changing** a show that runs every week — "make the warm look less white", "the bar programmes don't
work", "add two positions for the movers". It is the process that took one venue's show through ten
tested versions without losing any of the user's own work.

Follow the stages in order. Each ends with a gate: don't start the next stage until it holds.

```
 1 Request ─ 2 Base file ─ 3 Diagnose ─ 4 Route ─ 5 Decide ─ 6 Build ─ 7 Validate
                                                                            │
                        10 Learn ◀── 9 Hand-off ◀── 8 Companion files ◀─────┘
```

## 1. Request: turn the message into a change list

Write the request back as a numbered list of concrete changes, each tagged with its kind:

* **fix** — something doesn't work ("the programmes do nothing")
* **adjust** — something works but looks wrong ("too much white in the loop")
* **add** — new cues, positions, a test section
* **layout** — panel or Stream Deck arrangement
* **routine** — docs, runbook, how the booth is operated (not a file change)

Note what the user asked you *not* to touch ("don't mess too much with the lighting", "leave the
opener"). Those become assertions in stage 7.

**Gate:** every item is one change with one kind. Anything vague becomes a question in stage 5.

## 2. Base file: build on the user's newest save, never on your last output

* Ask for, or find, the **newest file the user saved from Lightkey** — a re-save of your last
  version carries their GUI edits (renamed buttons, their own presets, patched fixtures). Look at
  modification times; a file named "vN Final" saved after you shipped vN is the base.
* Never build on your own previous output when a newer user save exists: that deletes their work
  (`pitfalls.md` Bug 22).
* Run `tools/inspect_project.py <base>` and, for a Stream Deck show, `--midi`.
* Diff the base against what you shipped last time: new groups, cues, presets and fixtures are the
  user's. Record them in the hand-off notes as "kept".
* UIDs from a previous session are worthless (Bug 23). Re-find everything by name — and remember
  names repeat across panels (an old panel kept as a backup has the same cue names). Scope lookups
  to the live panel's buttons.

**Gate:** you can name the base file, and you know what the user changed since your last version.

## 3. Diagnose (every "fix" item): prove the cause before changing anything

Read the data first. A correct-looking file with a wrong result has a cause you can find:

| Symptom | Look at first | Usually |
|---|---|---|
| A cue "does nothing" but the same values work from Lightkey's **Design** view | cues that touch the same fixtures at **higher priority** | Outranked (Bug 30). Design overrides every cue. |
| A button/key does nothing at all | `inspect_project.py --midi`: is the note bound, to a cue that exists? | Dead binding (Bug 28), wrong channel (0-based in the file), wrong port |
| Colour is wrong everywhere | `tools/probe_colour.py` | Byte order (fpstore-format.md → Colour packing) |
| Colours look **whiter/paler** on the rig than in the data | which fixtures are RGBW (profile colour components) | The white LED mixes in pale shades; keep saturation up, use `coolWhite` deliberately |
| One moving head aims differently from identical siblings | its stored angles vs the siblings' | Physical: mounting or pan/tilt home, not the file |
| A lit Stream Deck key when the cue is off | is its latch group split across pages? | Stale page (streamdeck-midi.md → Latch groups) |
| One press changes several cues | Stream Deck key modes vs trigger On/off | Feedback loop (Bug 31) — unplug the deck, run the checker |
| Built-in fixture function does the wrong thing | the custom-capability index | Counted in array order, not by channel (Bug 32) |
| Everything after a save is empty | Bug 27 | ints written where UIDs belong |

Tell the user the cause and how you proved it, and offer a quick test that confirms it on the rig
without a new file ("switch FX: OFF off, then press Prog 1").

**Gate:** every fix item has a stated cause backed by something you read in the file.

## 4. Route: pick up the knowledge each change needs

| The change | Read | Use |
|---|---|---|
| Colours of a look, a palette, a gradient | fpstore-format.md → Colour packing; patterns §10, §18 | `lightkey/colour.py` (`c8`, `unpack_rgb8`); `probe_colour.py` first |
| An animated look / flow / chase | patterns §13, §22, §25; §5 and §15 for tempo | sequence steps: rewrite the existing steps' bytes in place |
| A new look that should rocker with the others | patterns §1, §9; Bug 25, 26 | join the EXISTING exclusive group |
| Layering (effects over colour, intensity over looks) | patterns §2, §12, §16; Bug 20 | priorities; one feature per layer |
| Moving-head positions and movement | fpstore-format.md → Moving-head practicalities; patterns §28 | clone a position the user confirmed; turn only what must turn |
| A fixture's built-in programmes, macros, modes | fpstore-format.md → Custom capabilities | read the setting table from the user's profile |
| Strobes, hard-cut chases | patterns §27 | `shutterState 2` + `strobeSpeed` |
| One-shot hits, timeline / MIDI show blocks | patterns §23, §24 | finite `holdDuration` |
| Panel buttons and labels | patterns §8, §17, §19, §26; Bug 21, 24 | `mk_button`, `mk_text_label`; `no_overlap(ignore_preexisting=True)` |
| MIDI notes for cues | class-schemas.md → Bindings; Bug 28 | `lightkey/bindings.py`: `free_notes`, `add_note_trigger` |
| Stream Deck keys | streamdeck-midi.md | `tools/build_streamdeck_profile.py` (stage 8) |

Always: `pitfalls.md` before writing code; `lightkey/build.py` for anything new.

**Gate:** for each change you can name the doc section and the helper you will use.

## 5. Decide: ask only the real choices

Ask when the answer changes what you build and only the user can know it — taste, the room, what the
volunteers are used to. For each question give 2–4 concrete options, **mark the one you recommend**
and say in one line what each does. Good questions from real revisions:

* "Fix the white: deep amber + a travelling warm-white pair / just remove the pale end / keep it and
  add a new cue to compare?"
* "Wall positions: each side to its own wall + a forward variant / one wall at a time?"
* "Test keys: Lightkey panel only / also on the Stream Deck?"

Don't ask what the file can tell you (fixture types, which notes are free, which group a cue is in),
and don't ask permission for the obvious default — state it in the hand-off.

**Gate:** no open question would change the build.

## 6. Build: a new versioned script, editing in place

* Copy `examples/revision/build_next.py` to `build_v<N>.py` next to the user's files. Keep its
  skeleton: refuse to overwrite; re-find by name; scope to the live panel; count and assert.
* **Edit in place.** Rewrite fpStore bytes (as a fresh bytes object — `write_store`) and cue fields.
  Don't rebuild cues (bindings die, Bug 28); don't regenerate panels (Bug 22).
* New cues go into existing groups where they belong; new groups get a panel section with a
  plain-English label.
* New MIDI notes: `free_notes()` then `add_note_trigger()`, on a channel block that keeps the new work
  separable. Carry every existing (channel, note) forward unchanged.
* Keep each change small and named in the script's docstring: what, why, and the evidence from
  stage 3. The docstring is the change log.
* Write the output as `<name>_v<N>.lightkeyproj` and never touch the base file.

**Gate:** the script runs clean and every count assertion holds.

## 7. Validate: prove the claims, and prove nothing else moved

Copy `examples/revision/validate_next.py` to `validate_v<N>.py`. Three layers:

1. **Structure** — `structural_parity()`, `buttons_resolve()`, `no_overlap(ignore_preexisting=True)`,
   `labels_fit()`. The file will decode.
2. **Preservation** — `preserved_buttons()`, `bindings_intact()`, and
   **`unchanged_except(presets=[...], cues=[...])`**: every preset and cue you did not name is
   byte-for-byte what the user saved. This is the check that lets you say "nothing else changed" and
   mean it. It also catches a lookup that matched the wrong copy of a repeated name.
3. **Semantics** — one `v.chk()` per sentence you will write in the hand-off: the colours decode to
   the family you claim, the new positions carry the pan you claim, the priority is what you claim,
   the notes are free and unique.

For a show on a live rig, 50–100 checks is proportionate. Never promise it will open in Lightkey —
say it passed and ask for a test.

**Gate:** every check passes, and every claim in your notes has a check behind it.

## 8. Companion files

* **MIDI map** — `tools/export_midi_map.py <out> -o midi_map_v<N>.csv` so the operator (and the next
  version) has the full note list.
* **Stream Deck** (if the show has one, or the user asks) — rebuild the profile from the new show and
  check it against the previous profile:
  `tools/build_streamdeck_profile.py … --icons`, then
  `tools/check_streamdeck_profile.py <new profile> <new show> --against <old profile>`.
  The diff should list exactly the keys you meant to add or move. See `streamdeck-midi.md`.
* **Volunteer docs** (runbooks, SOPs) — only where this version changes what a person does. Keep
  version numbers out of anything a volunteer reads; they go stale.

## 9. Hand-off

Deliver the show file, any companion files, and short operator notes (`OPERATOR_NOTES_v<N>.md`):

* **What changed** — one paragraph per change, in the user's words, with the cause for fixes.
* **What was kept** — the user's own additions since last time, and anything they said not to touch.
* **Test in this order** — numbered steps for the rig, each with what they should see, and what to
  report if they don't ("if a mover swings toward the centre, tell me which one").
* **Rollback** — the file to go back to.
* **Open questions** — anything you guessed (an aim, a routine) that needs their eyes.

Flag clearly what has not been tested on hardware.

## 10. Learn

When the test results come back:

* Record what was **verified on hardware** and what was not, per change.
* A failure with a new cause goes into `pitfalls.md` as a Bug with symptom, cause, fix, detection.
  A technique that worked goes into `patterns.md` or the relevant format doc.
* Update the defaults: if the user confirmed an aim, a colour, a behaviour, later versions derive
  from it.

The docs in this repo are the accumulated output of this stage. Keep them generic: no venue names,
fixture addresses or rig-measured values — describe the lesson, not the venue.
