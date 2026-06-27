#!/usr/bin/env bash
set -e

APP_NAME="branchbox"
APP_TITLE="BranchBox"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="$HOME/.local/share/$APP_NAME/app"
DATA_DIR="$HOME/.local/share/$APP_NAME"
INSTANCES_DIR="$DATA_DIR/instances"
APPLICATIONS_DIR="$HOME/.local/share/applications"
MIME_DIR="$HOME/.local/share/mime/packages"
NEMO_ACTIONS_DIR="$HOME/.local/share/nemo/actions"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_APP_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_MIME_DIR="$HOME/.local/share/icons/hicolor/scalable/mimetypes"

mkdir -p "$APP_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$INSTANCES_DIR"
mkdir -p "$APPLICATIONS_DIR"
mkdir -p "$MIME_DIR"
mkdir -p "$NEMO_ACTIONS_DIR"
mkdir -p "$AUTOSTART_DIR"
mkdir -p "$ICON_APP_DIR"
mkdir -p "$ICON_MIME_DIR"

rm -rf "$APP_DIR/branchbox"
cp -r "$PROJECT_DIR/branchbox" "$APP_DIR/branchbox"

if [ -f "$PROJECT_DIR/assets/branchbox.svg" ]; then
  cp "$PROJECT_DIR/assets/branchbox.svg" "$ICON_APP_DIR/branchbox.svg"
else
  cat > "$ICON_APP_DIR/branchbox.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="24" fill="#2f343f"/>
  <circle cx="64" cy="28" r="10" fill="#d8dee9"/>
  <circle cx="34" cy="82" r="10" fill="#88c0d0"/>
  <circle cx="64" cy="82" r="10" fill="#a3be8c"/>
  <circle cx="94" cy="82" r="10" fill="#ebcb8b"/>
  <path d="M64 38v20M64 58H34v14M64 58h30v14M64 58v14" stroke="#d8dee9" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
SVG
fi

cp "$ICON_APP_DIR/branchbox.svg" "$ICON_MIME_DIR/application-x-branchbox.svg"

cat > "$APPLICATIONS_DIR/branchbox.desktop" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=BranchBox
Comment=Open BranchBox visual file tree
Exec=python3 $APP_DIR/branchbox/main.py %f
Icon=branchbox
Terminal=false
Categories=Utility;FileTools;
MimeType=application/x-branchbox;
NoDisplay=false
EOF_DESKTOP

chmod +x "$APPLICATIONS_DIR/branchbox.desktop"

cat > "$MIME_DIR/branchbox.xml" <<'EOF_MIME'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-branchbox">
    <comment>BranchBox</comment>
    <glob pattern="*.branchbox"/>
    <icon name="application-x-branchbox"/>
    <generic-icon name="application-x-branchbox"/>
  </mime-type>
</mime-info>
EOF_MIME

cat > "$NEMO_ACTIONS_DIR/create_branchbox.nemo_action" <<EOF_ACTION
[Nemo Action]
Active=true
Name=Create BranchBox
Comment=Create a new BranchBox in this folder
Exec=python3 $APP_DIR/branchbox/create_branchbox.py %P
Icon-Name=branchbox
Selection=none
Extensions=any;
EOF_ACTION

cat > "$AUTOSTART_DIR/branchbox-cleaner.desktop" <<EOF_AUTOSTART
[Desktop Entry]
Type=Application
Name=BranchBox Cleaner
Comment=Recover hidden BranchBox contents when a BranchBox file is deleted
Exec=python3 $APP_DIR/branchbox/branchbox_cleaner.py --loop
Terminal=false
X-GNOME-Autostart-enabled=true
EOF_AUTOSTART

# Remove earlier test/dev install leftovers.
rm -f "$HOME/Templates/DeskTree.desktree"
rm -f "$HOME/Templates/Branch Box.branchbox"
rm -f "$HOME/.local/share/nemo/actions/create_branch_box.nemo_action"
rm -f "$HOME/.local/share/applications/desktree.desktop"
rm -f "$HOME/.local/share/mime/packages/desktree.xml"

update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

xdg-mime default branchbox.desktop application/x-branchbox || true
gio mime application/x-branchbox branchbox.desktop >/dev/null 2>&1 || true

pkill -f "branchbox_cleaner.py --loop" >/dev/null 2>&1 || true
nohup python3 "$APP_DIR/branchbox/branchbox_cleaner.py" --loop >/dev/null 2>&1 &

nemo -q >/dev/null 2>&1 || true

cat <<EOF_DONE
Installed BranchBox.

Right-click Desktop or inside a folder, then choose:
  Create BranchBox

Each BranchBox file stores its contents under:
  $INSTANCES_DIR/<unique-id>/items

Deleted BranchBox contents recover to:
  $HOME/Desktop/Recovered BranchBoxes
EOF_DONE
