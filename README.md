# BranchBox

DISCLAIMER: AI GENERATED

BranchBox is a Linux desktop visual file-tree launcher for Cinnamon/Nemo.

A `.branchbox` file acts like a special desktop item. When opened, it displays a borderless visual tree of hidden stored files. Folders are used as hidden branch points. Only files display as clickable icons.

## Features

- Create multiple `.branchbox` items
- Each item has its own hidden storage folder
- Hidden contents are stored under `~/.local/share/branchbox/instances/<id>/items`
- Right-click Desktop or inside a folder to create a BranchBox
- Empty BranchBoxes open directly to their storage folder
- Double-click displayed files to open them
- `.exe` files launch through Wine
- Editable morphed background, opacity, fade, text color, and text backing
- Borderless window opens from the clicked icon position
- If a `.branchbox` file is deleted, stored contents are moved to `~/Desktop/Recovered BranchBoxes`

## Requirements

Linux Mint Cinnamon/Nemo is the intended environment.

Install dependencies:

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-gdkpixbuf-2.0 python3-cairo python3-gi-cairo xdg-utils wine nemo shared-mime-info desktop-file-utils
```

## Install

From inside the extracted BranchBox folder:

```bash
./install.sh
```

## Create a BranchBox

Right-click the Desktop or inside a folder, then choose:

```text
Create BranchBox
```

This creates:

```text
New BranchBox.branchbox
```

You can rename it.

## Add files

Double-click the new `.branchbox` file. If it is empty, it opens the storage folder.

Put files and folders inside that storage folder.

Folders become branch structure. Files become visible clickable items.

## Edit appearance

Open a non-empty BranchBox, then right-click the background:

```text
Edit Appearance
```

## Uninstall

```bash
./uninstall.sh
```

The uninstaller removes the app, MIME registration, icon, Nemo action, and cleanup watcher.

It does not delete stored BranchBox contents unless you manually remove:

```bash
rm -rf "$HOME/.local/share/branchbox"
```

## Current default appearance

The default appearance uses the uploaded `New BranchBox.branchbox` settings: very low morph background opacity, white text, and no file-name text backing.

BranchBox also closes automatically when it loses focus, such as when the user clicks the desktop or another window.
