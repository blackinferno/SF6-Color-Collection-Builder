# SF6 Color Collection Builder — Concept / Build Spec

## Purpose

Make it easy to build a custom Street Fighter 6 color-slot collection mod from existing color mods.

The tool is a convenience utility, not a universal mod merger. It should scan normal SF6 color mod `.zip` files, let the user choose which source color file to use, rename the slot number, and export one Fluffy Mod Manager-compatible custom collection `.zip`.

The main goal is a compact, visual workflow where the user can see everything at once:

```text
Mod List | Character | Costume | Slot | Custom Collection
```

Unavailable options should be dimmed/disabled. Available options should be highlighted. With this layout, a separate help/tutorial screen should not be necessary.

---

## Target app

* Windows desktop app
* Final output should be an `.exe`
* Recommended stack: Python + PySide6 + PyInstaller
* Distribution/update path: GitHub Releases
* Update check can be simple: app checks latest GitHub release and opens the release page if newer
* Do not build a complex auto-updater for the first version

---

## Scope for v0.1

### In scope

* Scan a selected folder for `.zip` mods only
* Read mod metadata from `modinfo.ini` where available
* Show preview image using Fluffy Mod Manager-like behavior
* Detect supported `.user.2` color slot files
* Support normal, DX, and EX color file patterns
* Support max 10 slots per type: Normal, DX, EX
* Let user select:

  * Mod
  * Character
  * Costume
  * Type tab: Normal / DX / EX
  * Source slot
  * Target collection slot
* Rename only the final 3-digit slot number when exporting
* Export a Fluffy-compatible collection `.zip`
* Allow occupied target slots to be replaced
* Allow some target slots to remain empty
* Allow save/load of an existing custom collection project or existing custom collection zip where practical

### Out of scope for v0.1

* `.7z` support
* `.pak` support
* Universal mod merging
* Multi-file dependency support
* Cross-character assignment
* Cross-costume assignment
* Cross-type assignment between Normal/DX/EX
* Complex auto-updater
* Full mod manager replacement

Notes:

* Each supported color mod is expected to require one `.user.2` file per color slot.
* Fringe cases may require cross-slot files, but those are likely not reliably compatible between different mods and can be ignored.
* The tool does not need to guarantee every renamed mod works. It is primarily a convenience tool.

---

## Supported file name patterns

The tool must support these file name patterns, case-insensitively:

```text
esf001_001_cmd_002.user.2
esf001_001_cmd_dx_003.user.2
esf001_002_cmd_ex_004.user.2
```

Use this regex, case-insensitive:

```regex
^(esf\d{3})_(\d{3})_cmd(?:_(dx|ex))?_(\d{3})\.user\.2$
```

Extracted fields:

```text
character = esf001
costume   = 001
type      = normal / dx / ex
slot      = 001–010
```

Type mapping:

| UI Tab | Filename pattern part | Example                        |
| ------ | --------------------- | ------------------------------ |
| Normal | `cmd`                 | `esf001_001_cmd_002.user.2`    |
| DX     | `cmd_dx`              | `esf001_001_cmd_dx_003.user.2` |
| EX     | `cmd_ex`              | `esf001_001_cmd_ex_004.user.2` |

Filename case does not matter. The game/FFM can handle different cases, but the app may normalize output names to lowercase for consistency.

---

## Compatibility rule

Assignments are only valid within the same:

```text
character + costume + type
```

Examples:

Valid:

```text
esf001_001_cmd_002.user.2    -> esf001_001_cmd_005.user.2
esf001_001_cmd_dx_003.user.2 -> esf001_001_cmd_dx_008.user.2
esf001_002_cmd_ex_004.user.2 -> esf001_002_cmd_ex_010.user.2
```

Invalid:

```text
esf001_001_cmd_002.user.2    -> esf002_001_cmd_002.user.2
esf001_001_cmd_002.user.2    -> esf001_002_cmd_002.user.2
esf001_001_cmd_002.user.2    -> esf001_001_cmd_dx_002.user.2
```

The app should prevent invalid assignments by dimming/disabling incompatible choices rather than showing many warning dialogs.

---

## Folder / zip scanning behavior

User selects the SF6 mods folder, usually something like:

```text
Fluffy Mod Manager\Games\SF6\Mods
```

The tool scans only `.zip` files in that folder for v0.1.

Inside each zip, the scanner should search for relevant files regardless of nesting level. Do not assume `natives` is at the zip root.

Look for:

```text
modinfo.ini
*.png / *.jpg / *.jpeg / *.webp
natives/stm/product/model/esf/**/*.user.2
```

Supported `.user.2` files are those whose basename matches the supported filename regex.

The scanner should create records for each detected color file.

Example internal source-file record:

```json
{
  "zip_path": "C:/Mods/SomeMod.zip",
  "mod_name": "Some Mod",
  "author": "Creator",
  "preview_image_path_in_zip": "SomeMod/preview.png",
  "internal_file_path": "SomeMod/natives/stm/product/model/esf/esf001/001/esf001_001_cmd_002.user.2",
  "character": "esf001",
  "costume": "001",
  "type": "normal",
  "source_slot": "002"
}
```

---

## Preview image behavior

Show images similarly to Fluffy Mod Manager where possible.

Suggested priority:

1. Use image referenced by `modinfo.ini` if there is a clear image field.
2. Otherwise use image next to `modinfo.ini`.
3. Otherwise use the first reasonable image file found in the zip.
4. Otherwise show a placeholder.

Preview support does not need to be perfect in v0.1.

---

## Main UI layout

The main layout should use five vertical sections:

```text
Mod List | Character | Costume | Slot | Custom Collection
```

Everything should be compact and visible at once.

### 1. Mod List section

Shows scanned zip mods.

Each mod row should show compact info such as:

```text
[thumbnail] Mod Name
            Author
            detected file count / short summary
```

Include search/filter at the top.

Clicking a mod updates the availability in Character, Costume, and Slot sections.

### 2. Character section

Show all supported characters.

* Characters available in the selected mod are highlighted/clickable.
* Characters not available in the selected mod are dimmed/disabled.

The tool can initially display internal IDs like `esf001`, but a friendly character-name mapping can be added later.

### 3. Costume section

Show costume numbers vertically.

Example:

```text
Costume 1
Costume 2
Costume 3
```

Internal values remain:

```text
001
002
003
```

Available costumes are highlighted/clickable. Missing costumes are dimmed/disabled.

### 4. Slot section

The Slot section contains a tab switcher:

```text
Normal | DX | EX
```

Below the tabs, show source slots vertically from 01 to 10:

```text
01
02
03
04
05
06
07
08
09
10
```

Available source slots for the selected mod + character + costume + type are highlighted/clickable.

Unavailable source slots are dimmed/disabled.

Vertical is preferred over a grid because it uses less horizontal space and matches the Custom Collection section.

### 5. Custom Collection section

Shows target slots vertically from 01 to 10 for the current:

```text
selected character + selected costume + selected type tab
```

Example:

```text
Custom Collection — Normal
01  empty
02  Some Mod Name
03  empty
04  Another Mod Name
05  empty
06  empty
07  empty
08  empty
09  empty
10  empty
```

Occupied target slots should be highlighted.

Empty target slots should be normal/clickable.

If a source slot is selected, compatible target slots can be subtly highlighted to show that the user can assign there.

Dropping/clicking onto an occupied slot replaces the existing assignment. A confirmation can be optional, but replacement is allowed.

---

## Interaction model

Primary interaction for v0.1 can be click-based:

1. User selects a mod in Mod List.
2. User selects an available character.
3. User selects an available costume.
4. User selects Normal/DX/EX tab.
5. User selects an available source slot.
6. User selects a target slot in Custom Collection.
7. Assignment is created or replaces the previous assignment in that target slot.

Drag and drop can be added later, but click-to-assign is enough for v0.1.

Useful optional shortcuts:

* Double-click a source slot to assign it to the next empty target slot.
* Right-click a target slot to clear it.
* Right-click a target slot to view source mod details.

---

## Export behavior

When exporting, the user chooses a collection name.

The output should be a Fluffy-compatible zip, saved to the selected Mods folder or user-selected output location.

Example output structure:

```text
My Custom Collection.zip
└─ My Custom Collection/
   ├─ modinfo.ini
   ├─ My Custom Collection.png
   └─ natives/
      └─ stm/
         └─ product/
            └─ model/
               └─ esf/
                  └─ esf001/
                     └─ 001/
                        ├─ esf001_001_cmd_001.user.2
                        ├─ esf001_001_cmd_002.user.2
                        └─ esf001_001_cmd_dx_003.user.2
```

For each assignment:

1. Read the selected source file bytes from the source zip.
2. Rename only the final slot number.
3. Write the file into the correct output path.

Example:

```text
source:
esf001_001_cmd_dx_003.user.2

target slot 008:
esf001_001_cmd_dx_008.user.2
```

Generated `modinfo.ini` should update the `name` field to match the save/collection name.

A simple generated `modinfo.ini` is acceptable for v0.1 as long as Fluffy Mod Manager recognizes it.

Example:

```ini
name=My Custom Collection
version=1.0
description=Generated by SF6 Color Collection Builder
author=User
```

---

## Save / load behavior

The tool should support:

* Create new collection
* Save collection project
* Save As
* Load existing collection project or existing `My Custom Collection.zip` where practical
* Export zip

If full reconstruction from an exported zip is difficult, a simple project file can be used for v0.1.

Suggested project file format:

```json
{
  "collection_name": "My Custom Collection",
  "mods_folder": "C:/Fluffy Mod Manager/Games/SF6/Mods",
  "assignments": [
    {
      "character": "esf001",
      "costume": "001",
      "type": "normal",
      "target_slot": "002",
      "source_zip": "C:/Mods/SomeMod.zip",
      "source_internal_file_path": "SomeMod/natives/stm/product/model/esf/esf001/001/esf001_001_cmd_005.user.2",
      "source_slot": "005",
      "source_mod_name": "Some Mod"
    }
  ]
}
```

---

## Menu / top bar

Include basic software-style menu sections.

### File

* New
* Open / Load
* Save
* Save As
* Export Zip
* Settings
* Close

### Donate

* Buy Me a Coffee
* Patreon

Donate menu items should open the relevant pages in the user’s browser. Placeholder URLs are fine during early development.

### Optional Help/About

A full Help section should not be necessary because the layout should explain itself through dimming/highlighting.

An About dialog is okay for version number and update check.

---

## Visual state rules

Use clear visual states instead of excessive warning messages.

| State                       | Meaning                                  |
| --------------------------- | ---------------------------------------- |
| Dimmed/disabled             | Not available in selected mod/context    |
| Highlighted                 | Available/clickable                      |
| Strong outline              | Currently selected                       |
| Filled/colored target row   | Target slot already assigned             |
| Subtle glow on target slots | Source slot selected and ready to assign |

Avoid modal dialogs unless necessary.

---

## Suggested repo structure

```text
sf6-color-collection-builder/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ models.py
│  ├─ parser.py
│  ├─ scanner.py
│  ├─ exporter.py
│  ├─ project_io.py
│  ├─ settings.py
│  └─ ui/
│     ├─ main_window.py
│     ├─ mod_list.py
│     ├─ option_column.py
│     ├─ slot_column.py
│     └─ collection_column.py
├─ assets/
│  └─ placeholder.png
├─ tests/
│  ├─ test_parser.py
│  ├─ test_scanner.py
│  └─ test_exporter.py
├─ pyproject.toml
├─ README.md
└─ build_exe.ps1
```

---

## Implementation priority

### Phase 1 — core parser/scanner

* Parse supported filenames
* Scan zip files
* Read modinfo.ini
* Detect preview images
* Build internal source-file records
* Add tests for parser

### Phase 2 — basic UI

* Build five-column PySide6 layout
* Show mod list
* Show character/costume/slot availability
* Add Normal/DX/EX tabs
* Add custom collection target slots

### Phase 3 — assignment/export

* Click source slot then target slot to assign
* Store assignments
* Replace occupied target slot when assigned again
* Export Fluffy-compatible zip
* Generate modinfo.ini

### Phase 4 — polish

* Save/load project file
* Remember last mods folder
* Search/filter mod list
* Preview image improvements
* Basic settings
* GitHub update checker
* PyInstaller `.exe` build script
