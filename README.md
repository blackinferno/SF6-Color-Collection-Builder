# Important

This tool is not meant to replace, reupload, or take credit for the work of mod creators.

Color Collection Builder is only a convenience tool that helps you organize compatible color mods into a single collection so you can enjoy more of the community’s work at once.

Please support, credit, and thank the original modders. If you share a collection using their work, make sure to follow each creator’s permissions and give proper credit.

# SF6 Color Collection Builder

Windows desktop app for building custom Street Fighter 6 color-slot collection zips.

The tool scans SF6 color mod `.zip` files, shows detected characters, costumes, and color slots, then lets you assign those source colors into a custom collection that can be saved as a Fluffy Mod Manager compatible zip.

## Download

Most users should download the Windows release zip here:

<https://github.com/blackinferno/SF6-Color-Collection-Builder/releases>

You do not need Python unless you want to run or modify the source code.

## Features

- Scan a mods folder for `.zip` files.
- Detect SF6 `.user.2` color files, `modinfo.ini`, and preview images.
- Display available characters, costumes, and normal/DX/EX source slots.
- Assign source slots into a custom collection.
- Replace or clear occupied collection slots.
- Save/export a collection zip.
- Reopen app-created collection zips and preserve original source mod names and source slots.
- Show a full current collection summary by character.
- Remember the last mods folder, save folder, and window size.
- Check GitHub releases for updates.

## Install

Extract the release zip and run:

```text
SF6 Color Collection Builder.exe
```

The app stores local preferences in `settings.ini` beside the executable. Delete that file to reset remembered folders and window size.

## Run From Source

```powershell
python -m pip install -e ".[dev]"
python -m app.main
```

## Test

```powershell
python -m pytest
```

## Build

PyInstaller is required for local builds.

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

The built app is written to:

```text
dist/SF6 Color Collection Builder/
```

## Supported Color Files

Supported filenames are case-insensitive:

```text
esf001_001_cmd_002.user.2
esf001_001_cmd_dx_003.user.2
esf001_002_cmd_ex_004.user.2
```

Slots `001` through `010` are supported.
