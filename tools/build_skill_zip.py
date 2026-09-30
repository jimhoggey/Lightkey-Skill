#!/usr/bin/env python3
"""
Build the upload bundles for claude.ai's Skills UI — one ZIP per skill:

    dist/lightkey-patcher-skill.zip      the Lightkey file skill
    dist/lightkey-streamdeck-skill.zip   the Stream Deck add-on

claude.ai wants a different shape from a Claude Code plugin:

  * the ZIP must contain the skill FOLDER as its root, not loose files
  * SKILL.md must sit at the top of that folder (this repo keeps them in
    skills/<name>/ so the plugin layout works)
  * frontmatter `description` is capped at 200 characters, and `name` at 64

So a plain "Download ZIP" from GitHub will not import. This script repackages the
same canonical sources into bundles that do, and shortens each description to fit.
Both bundles carry the same code and docs, so either works alone.

Usage:
    python3 tools/build_skill_zip.py                          # both -> dist/
    python3 tools/build_skill_zip.py --skill lightkey-patcher --out /tmp/x.zip
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# claude.ai hard limits
MAX_NAME, MAX_DESC = 64, 200

# Directories copied into every bundle, keeping their names so the paths written in
# SKILL.md (docs/..., lightkey/...) resolve unchanged.
PAYLOAD_DIRS = ['docs', 'lightkey', 'streamdeck', 'tools', 'examples']
PAYLOAD_FILES = ['LICENSE', 'README.md']

CLAUDE_AI_NOTE = '''On claude.ai the user must upload their files into the conversation before you
can read them, and anything you write must be offered back to them as a file download —
you cannot touch their local disk. Never hand back a modified file as the only copy;
tell them to keep their original.
'''

SKILLS = {
    'lightkey-patcher': {
        # The canonical description is long and trigger-rich, which suits Claude Code.
        'short_desc': ('Inspect and modify macOS Lightkey .lightkeyproj DMX lighting projects: '
                       'format schemas, colour packing, panel building, and known failure modes.'),
        # Replaces the plugin-specific "where the files live" section.
        'location': '''## Where the files referenced below live

Everything referenced here is bundled inside this skill folder — `docs/pitfalls.md`,
`lightkey/resolve.py` and so on are relative to the skill's own directory. Read them with
the Read tool as you need them; don't load all the docs at once.

The Python needs no dependencies beyond the standard library. From the skill directory:

```python
import sys; sys.path.insert(0, '.')          # or the absolute path to this skill folder
from lightkey.resolve import load, find_instances, classname
from lightkey.colour import pack_color, c8, unpack_rgb8
from lightkey.validate import Validator
```

Two CLI tools are bundled and should usually be your first move on a new file:

```bash
python3 tools/inspect_project.py  <project>.lightkeyproj   # structure, schema, groups
python3 tools/probe_colour.py     <project>.lightkeyproj   # prove the colour byte order
```

''' + CLAUDE_AI_NOTE + '\n',
    },
    'lightkey-streamdeck': {
        'short_desc': ('Build and check Stream Deck profiles that fire Lightkey cues over MIDI: '
                       'key modes paired with trigger behaviours, latch groups, lit keys, and a '
                       'safety checker.'),
        'location': '''## Where the files referenced below live

Everything referenced here is bundled inside this skill folder — `docs/streamdeck-midi.md`
(read it first), `streamdeck/`, `lightkey/bindings.py`, `tools/build_streamdeck_profile.py`,
`tools/check_streamdeck_profile.py`, `tools/export_midi_map.py` and
`examples/streamdeck_layout.json` are relative to the skill's own directory. Python 3 standard
library only. Run the tools from the skill directory. `--icons` needs macOS (AppKit through
`osascript`), so on claude.ai build without it: keys then show their text as titles.

''' + CLAUDE_AI_NOTE + '\n',
    },
}


def build_skill_md(name):
    """Canonical SKILL.md -> bundle SKILL.md (short description, bundle-relative paths)."""
    cfg = SKILLS[name]
    text = open(os.path.join(REPO, 'skills', name, 'SKILL.md'), encoding='utf-8').read()
    if not text.startswith('---'):
        sys.exit(f'{name}: SKILL.md has no YAML frontmatter')
    end = text.index('---', 3)
    front, body = text[3:end], text[end + 3:]

    fm_name = re.search(r'^name:\s*(.+)$', front, re.M).group(1).strip()
    if fm_name != name:
        sys.exit(f'{name}: frontmatter name is {fm_name!r}; it must match the folder')
    if len(fm_name) > MAX_NAME:
        sys.exit(f'name is {len(fm_name)} chars, claude.ai allows {MAX_NAME}')
    if len(cfg['short_desc']) > MAX_DESC:
        sys.exit(f'{name}: short description is {len(cfg["short_desc"])} chars, claude.ai allows {MAX_DESC}')

    # Swap in the short description, dropping the long multi-line original.
    front = re.sub(r'^description:.*?(?=^\w+:|\Z)', f'description: {cfg["short_desc"]}\n',
                   front, flags=re.M | re.S)

    # Replace the plugin-relative location section with the bundle-relative one.
    body, n = re.subn(r'## Where the files referenced below live\n.*?(?=^## )',
                      lambda _m: cfg['location'], body, flags=re.M | re.S)
    if n != 1:
        sys.exit(f'{name}: SKILL.md needs exactly one "## Where the files referenced below live" section')

    # Fix references to the plugin/marketplace install, which don't apply here.
    body = body.replace('root of this\nplugin/repository', 'root of this skill folder')
    return f'---{front}---{body}'


def build(name, out):
    skill_md = build_skill_md(name)
    desc = re.search(r'^description:\s*(.+)$', skill_md, re.M).group(1)
    print(f'{name}: description {len(desc)}/{MAX_DESC} chars')

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, name)
        os.makedirs(root)
        with open(os.path.join(root, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write(skill_md)
        for d in PAYLOAD_DIRS:
            shutil.copytree(os.path.join(REPO, d), os.path.join(root, d),
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
        for f in PAYLOAD_FILES:
            shutil.copy2(os.path.join(REPO, f), root)

        if os.path.exists(out):
            os.remove(out)
        count = 0
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in sorted(filenames):
                    full = os.path.join(dirpath, fn)
                    z.write(full, os.path.relpath(full, tmp))   # folder as ZIP root
                    count += 1

    size = os.path.getsize(out)
    print(f'wrote {out}  ({count} files, {size / 1024:.0f} KB); ZIP root: {name}/SKILL.md')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skill', choices=sorted(SKILLS), help='build one skill (default: all)')
    ap.add_argument('--out', help='output path (only with --skill)')
    args = ap.parse_args()
    if args.out and not args.skill:
        sys.exit('--out needs --skill')
    for name in ([args.skill] if args.skill else sorted(SKILLS)):
        build(name, args.out or os.path.join(REPO, 'dist', f'{name}-skill.zip'))


if __name__ == '__main__':
    main()
