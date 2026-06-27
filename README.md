# BranchBox

DISCLAIMER: AI GENERATED

BranchBox is a Linux Mint Cinnamon/Nemo utility that creates visual file-tree launcher boxes on the desktop.

A `.branchbox` file acts like a special desktop item. When opened, it shows a borderless visual tree of files stored in a hidden per-instance folder.

## Features

- Create BranchBox items from the Nemo right-click menu
- Each `.branchbox` file has its own hidden storage folder
- Multiple independent BranchBoxes are supported
- Empty BranchBoxes open directly to their storage folder
- Folder structure appears as branch lines instead of folder icons
- Files display as clickable icons
- Double-click files to open them
- `.desktop` launchers are parsed and launched correctly, including terminal launchers
- `.exe` files launch through Wine
- Custom editable appearance settings
- Morphed background fade around icons and branch lines
- Window closes when focus is lost
- Trash-based cleanup for deleted BranchBox launchers
- Workspace/icon-moving systems are supported because missing files are not treated as deleted

## Install

```bash
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-gdkpixbuf-2.0 python3-cairo python3-gi-cairo xdg-utils wine nemo shared-mime-info desktop-file-utils
./install.sh
```

## Create a BranchBox

Right-click the Desktop or inside a folder and choose:

```text
Create BranchBox
```

This creates:

```text
New BranchBox.branchbox
```

You can rename it.

## Add files

Open the BranchBox. If it is empty, it opens directly to its hidden storage folder.

You can also right-click inside the BranchBox and choose:

```text
Open Storage Folder
```

Place files and folders in that folder.

Folders become branch structure. Files become visible clickable items.

## Where files are stored

BranchBox launcher files are visible wherever you create them, usually on the Desktop:

```text
~/Desktop/New BranchBox.branchbox
```

The actual stored files are hidden under:

```text
~/.local/share/branchbox/instances/<id>/items
```

The registry is stored here:

```text
~/.local/share/branchbox/registry.json
```

## Trash cleanup behavior

BranchBox does not treat a missing launcher path as deletion. This prevents workspace managers that move icons around from emptying BranchBoxes.

If a registered `.branchbox` launcher is actually moved to Trash, BranchBox recovers its hidden contents to:

```text
~/Desktop/Recovered BranchBoxes
```

Then it removes that instance from the BranchBox registry.

## Uninstall

```bash
./uninstall.sh
```

The uninstaller removes the app, MIME registration, icon, Nemo right-click action, and cleanup watcher.

It does not delete stored BranchBox contents unless you manually remove:

```bash
~/.local/share/branchbox
```
