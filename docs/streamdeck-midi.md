# Stream Deck → Lightkey over MIDI

An optional add-on: a Stream Deck profile whose keys fire Lightkey cues, light up while their cue is
live, and stay in step with the show. Everything here was built and corrected over ten versions of a
show run weekly by volunteers on a 15-key Stream Deck MK.2; each rule below is the fix for something
that failed on that rig.

Use it when the user asks for a Stream Deck profile, wants hardware buttons for their cues, or asks
to "link the MIDI notes". The Lightkey file is built as normal first; this runs after it.

Code: `streamdeck/` (profile builder and checker), `lightkey/bindings.py` (the Lightkey side),
`tools/build_streamdeck_profile.py`, `tools/check_streamdeck_profile.py`,
`tools/export_midi_map.py`, `examples/streamdeck_layout.json`.

## How the pieces connect

```
Stream Deck key ──> "MIDI" plugin (Trevliga Spel) ──> port "Lightkey Input" ──> Lightkey trigger ──> cue
     ^                                                                                       │
     └──── key lights ◀── plugin "action when received" ◀── port "Lightkey Output" ◀── Lightkey feedback
```

* **The plugin:** "MIDI" by Trevliga Spel (`se.trevligaspel.midi.genericmidi`), from the Stream
  Deck store. Free. Each key sends a Note on a channel.
* **The ports:** Lightkey publishes its own virtual ports, `Lightkey Input` (it listens) and
  `Lightkey Output` (it sends feedback). Point the plugin's MIDI out at `Lightkey Input` and MIDI in
  at `Lightkey Output`. Don't rely on ports the plugin creates for itself: on the rig they showed as
  "[Not present!]" on the booth Mac.
* **Feedback needs no setup in Lightkey:** it sends the cue state for every triggered cue to
  `Lightkey Output` automatically, and the plugin lights the key when the value received is 127.
* **The show file is the source of truth.** Each key's channel, note, mode and latch group are read
  from the `.lightkeyproj`, so the deck cannot drift from the show. Bind the notes in Lightkey first
  (in the GUI, or with `lightkey.bindings.add_note_trigger`), then build the profile.

## Key modes and Lightkey behaviours

The plugin's key mode (`g02`) and the Lightkey trigger's behaviour (`activationBehavior`) have to be
chosen as a pair. Every row here is what the rig ended up on; the notes are what went wrong first.

| The cue is… | Stream Deck key | Lightkey trigger | Why |
|---|---|---|---|
| one of a set where only one can be on (house levels, colour looks, mover positions) — a **mutually exclusive group** in Lightkey | **Latch**, in a latch group named after the Lightkey group | **Flash**, On/off unticked | Pressing a key sends note-on (cue on); the key it unlights sends note-off (that cue off); pressing the lit key again sends note-off (cue off). Only Flash turns a note-off into "off". With Activate the lit key could not switch its own cue off; with Toggle the displaced key's off was ignored and the deck and show disagreed. |
| on its own, press to toggle | **Push** | **Toggle**, On/off unticked | One note-on per press, never an off, so each press toggles exactly once. |
| a momentary effect (flash, crash-out) | **Hold** | **Flash** | Note-on on press, note-off on release: lit exactly while held. |

**Never:** a Latch or plugin-Toggle key on a trigger with **On/off ticked** (`onOff: True`). Every
note-off then counts as a press, cues toggle each other through the feedback path, and Lightkey
crashed on the rig (`pitfalls.md` Bug 31). The builder refuses it; the checker fails it.

The builder derives the mode from the show: in an exclusive group → Latch; not in a group with Flash
→ Hold; otherwise → Push. Set a behaviour in the show, not a mode in the layout, and the two agree.

## Latch groups

* **Latch groups are global to the Stream Deck app**, across every profile the user has. Prefix
  them (`"latch_prefix": "Lightkey "`) so they can't collide with another profile's groups.
* **One Lightkey group = one latch group.** The checker fails a latch group that mixes cues from two
  Lightkey groups, or a Lightkey group split across two latch groups.
* **A latch group only redraws keys on the page the deck is showing.** If a group spans two pages,
  pressing a member on page 2 leaves the previously lit key on page 1 lit ("House 10% still lit after
  pressing 20%"). The show is right; the key is stale until any key on that page is pressed. Fit
  each group on one page where you can: a 15-key deck holds a 10-step level ladder plus navigation.
  The builder and checker report every group that spans pages.
* **Keys only light for cues triggered through MIDI or by Lightkey feedback.** A cue that an
  exclusive group switches off *inside Lightkey* (because another member was clicked with the mouse)
  does not send an off, so a Toggle key would stay lit. Latch keys avoid this for anything pressed
  on the deck. Clicking cues with the mouse while the deck is in use can still leave a key stale.

## The layout file

`examples/streamdeck_layout.json`, annotated. The essentials:

```json
{
 "profile_name": "Lightkey Service Panel",
 "grid": [5, 3],
 "channels": [2],
 "latch_prefix": "Lightkey ",
 "pages": [
  {"label": null, "keys": [["House: 5%", "House: 10%", "House: 20%", "House: 50%", "House: 100%"],
                           ["...", "...", "...", "...", null],
                           ["...", "...", "BLACKOUT", null, "NEXT"]]}
 ],
 "keys": {"House: 10%": {"category": "HOUSE", "lines": ["10%"], "colors": ["#FFB020"]}}
}
```

* Cells: a cue name (exactly as in Lightkey), `LABEL`, `NEXT`, `PREV`, or `null`.
* `channels`: only bindings on these channels count. Shows reuse cue names across panels; if a name
  is bound twice the builder stops and asks you to pick.
* `group_prefix`: only exclusive groups whose names start with this become latch groups (useful when
  a file keeps an old panel's groups alongside the current ones).
* `keys` is optional artwork: `colors: "look"` takes the deepest and palest colour the cue shows.

Design for a volunteer: the home page carries what every service needs (house levels, preach, the
main looks); one idea per page; `NEXT` bottom-right and `PREV` above it on every page; nothing
important on a page that needs three presses to reach.

## Building and checking

```bash
# 1. the user exports their current profile from the Stream Deck app (it must contain one MIDI-plugin
#    key set to Note, a Next Page and a Previous Page key, and optionally a Text key for page labels)
# 2. build
python3 tools/build_streamdeck_profile.py --template "Export.streamDeckProfile" \
    --show MyShow_v5.lightkeyproj --layout layout.json --out Panel_v5.streamDeckProfile --icons
# 3. check any profile against the show, and diff against the one it replaces
python3 tools/check_streamdeck_profile.py Panel_v5.streamDeckProfile MyShow_v5.lightkeyproj \
    --against Panel_v4.streamDeckProfile
```

`--icons` (macOS) renders a key image per state: off = dark key with a coloured ring and a strip of
the cue's colours; live = the colours as a fill with a LIVE pill, so a pale look still reads as lit.
It also writes two preview sheets (`*_preview_off.png`, `*_preview_on.png`) — send those to the user
before they import; they catch layout mistakes faster than the deck does.

On every later show version: rebuild the profile from the new show (notes are re-read), run the
check with `--against` the previous profile, and tell the user which keys changed.

## Installing on the booth Mac

1. Double-click the `.streamDeckProfile`; the Stream Deck app imports it as a new profile.
2. Select it on the deck (the app's profile menu). Importing does not switch to it.
3. Lightkey must be running **before** the Stream Deck app starts, or the plugin can start before
   `Lightkey Input` exists and the keys stay dead until the Stream Deck app is restarted. Turn off
   the Stream Deck app's own "launch at login" and open it after Lightkey.
4. **App Nap:** the Stream Deck app runs out of sight behind a full-screen Lightkey, which is exactly
   what macOS App Nap slows down. Symptom: presses do nothing, then all fire at once when someone
   clicks the Stream Deck app. Fix once: `defaults write -g NSAppSleepDisabled -bool true`, then quit
   and reopen the Stream Deck app.

## Testing on the rig

Give the user this order, and ask for results before the next change:

1. Press a key on the home page: the cue comes on and the key lights.
2. Press another key in the same group: the first unlights, the second lights, the show follows.
3. Press the lit key again: its cue goes off and the key unlights.
4. A Hold key: lit while held, off on release.
5. Switch pages mid-group: note any stale key (expected across pages; see Latch groups).
6. Click a cue in Lightkey with the mouse: the matching key follows (feedback).

If one press ever changes several cues at once, **unplug the Stream Deck** and run the checker on
that profile and show.

## The profile file format (for the curious)

A `.streamDeckProfile` is a ZIP:

```
package.json                                   {"DeviceModel": "20GAA9902", ...}
Profiles/<PROFILE-ID>.sdProfile/manifest.json   {"Name", "Device": {"Model"}, "Pages":
                                                  {"Current", "Default", "Pages": [page ids, lowercase]}}
Profiles/<PROFILE-ID>.sdProfile/Profiles/<PAGE-ID>/manifest.json
                                                {"Controllers": [{"Type": "Keypad",
                                                  "Actions": {"col,row": action}}]}
Profiles/<PROFILE-ID>.sdProfile/Profiles/<PAGE-ID>/Images/<name>.png
```

* JSON is compact with sorted keys; profile version `"3.0"`. Page folders are UPPERCASE UUIDs, the
  profile manifest lists them lowercase. The "Default" page is an extra empty page.
* Directory entries are present in the ZIP. `streamdeck/profile.py` writes the same shape with a
  fixed timestamp, so a rebuild with the same inputs is byte-identical.
* An action carries `UUID` (the plugin action id), `Settings`, and `States` — two for a MIDI key:
  `States[0]` off, `States[1]` on, each with `Image: "Images/<name>.png"` and `ShowTitle`.

MIDI plugin `Settings` fields that matter (Trevliga Spel, verified on plugin 4.2):

| Field | Meaning |
|---|---|
| `g04` | message type: `"Note"` |
| `g02` | key mode: `"Latch"`, `"Push"`, `"Hold"`, `"Toggle"` |
| `g45`, `g49` | note number (both carry it; keep them equal) |
| `g47` | channel, **0-based** as a string (`"3"` = channel 4) |
| `b14` | latch group name (Latch keys) |
| `smo`, `smi` | MIDI out / in port names |

Copy every other field from a key the user made: the builder clones the template key so the profile
matches the plugin version the user has installed. Known device grid: MK.2 `20GAA9902` = 5 × 3.
