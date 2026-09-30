---
name: lightkey-streamdeck
description: Build and check Elgato Stream Deck profiles whose keys fire Lightkey lighting cues over MIDI, with keys that light while their cue is live. Use when the user asks for a Stream Deck profile or page for their Lightkey show, wants hardware buttons for cues, asks to "link the MIDI notes", mentions the Trevliga Spel MIDI plugin, a .streamDeckProfile file, keys that don't fire or stay lit, or a Stream Deck that stops responding behind full-screen Lightkey. An add-on to lightkey-patcher, which builds the show file itself.
---

# Lightkey + Stream Deck (MIDI)

An add-on to the **lightkey-patcher** skill. That skill builds and revises the `.lightkeyproj`; this
one builds the Stream Deck profile that drives it, and checks that the two agree. Run it only when the
user asks for Stream Deck keys, or the show already has a profile that must follow a new version.

## Where the files referenced below live

Paths are relative to the **root of this plugin/repository** (from this skill's directory,
`../../`): `docs/streamdeck-midi.md` (read it first), `streamdeck/`, `lightkey/bindings.py`,
`tools/build_streamdeck_profile.py`, `tools/check_streamdeck_profile.py`,
`tools/export_midi_map.py`, `examples/streamdeck_layout.json`. Python 3 standard library only;
`--icons` also needs macOS (it draws with AppKit through `osascript`).

## What you need from the user

1. **The show** — their newest `.lightkeyproj` save.
2. **An exported profile** from their Stream Deck app (right-click a profile → Export). It must
   contain one key using the **MIDI** plugin by Trevliga Spel set to send a **Note**, plus a **Next
   Page** and a **Previous Page** key; a **Text** key is optional (page labels). The builder clones
   these so the result matches the plugin version they have. No MIDI plugin yet? It is free in the
   Stream Deck store.
3. **What goes where** — which cues, on which page. Propose a layout; they approve it.

## Stages

1. **Notes first, in the show.** Every cue on the deck needs a MIDI note in Lightkey.
   `python3 tools/export_midi_map.py <show>` lists what is bound. Missing notes: add them in the show
   build with `lightkey.bindings` (`free_notes`, `add_note_trigger`) — through the lightkey-patcher
   revision workflow (`docs/update-workflow.md`), because this changes the show file.
2. **Pair behaviours with key types** (`docs/streamdeck-midi.md` → Key modes). The builder derives
   each key's mode from the show:
   * cue in a mutually exclusive group → **Latch** key; its trigger must be **Flash**
   * standalone cue with a **Toggle** trigger → **Push** key
   * momentary cue with a **Flash** trigger → **Hold** key
   * **never** "On/off" ticked on a trigger a Latch or Toggle key drives — it crashed Lightkey.
   If the show pairs them wrongly, fix the show (`bindings.set_behaviour`), not the layout.
3. **Layout** — copy `examples/streamdeck_layout.json`. Home page = what every service needs; one idea
   per page; NEXT bottom-right, PREV above it; fit each exclusive group on one page (a latch group only
   redraws the page on screen). Set `channels` if cue names repeat across panels.
4. **Build** — `tools/build_streamdeck_profile.py --template … --show … --layout … --out … --icons`
   (`--icons` needs macOS). It refuses unsafe pairings and runs the checker on its own output.
5. **Check and diff** — `tools/check_streamdeck_profile.py <profile> <show> --against <previous>`.
   Zero FAILs; every WARN explained to the user; the diff lists only the keys you meant to change.
6. **Hand off** — the profile, the two preview sheets (`*_preview_off.png`, `*_preview_on.png`), and
   the install + test steps from `docs/streamdeck-midi.md` → Installing and Testing on the rig. Say
   which latch groups span pages (stale keys are expected there).

## When the show changes

Every new show version: rebuild the profile from the new show (it re-reads every note), check it with
`--against` the old profile, and send it along with the show even if only a note moved. A profile
that is one version behind its show is the most common reason a key "stops working".

## Troubleshooting the user will report

| They say | Likely | Do |
|---|---|---|
| Keys do nothing, then all fire at once when the Stream Deck app is clicked | macOS App Nap | `defaults write -g NSAppSleepDisabled -bool true`, reopen the Stream Deck app |
| No key works at all | Stream Deck app started before Lightkey; wrong profile selected; port | restart the Stream Deck app after Lightkey; check `smo` is `Lightkey Input` |
| One key does nothing | its note isn't bound, or is bound to a deleted cue | run the checker; `export_midi_map.py` |
| A key stays lit after another is pressed | its latch group spans pages | expected; press any key on that page; tighten the layout |
| A lit key can't switch its cue off | trigger is Activate/Toggle, not Flash | fix the show trigger to Flash |
| One press changes lots of cues | Latch/Toggle key + On/off ticked | unplug the deck now; run the checker; untick On/off |
