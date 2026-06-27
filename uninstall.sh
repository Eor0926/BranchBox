#!/usr/bin/env bash
set -e

APP_NAME="branchbox"

pkill -f "branchbox_cleaner.py --loop" >/dev/null 2>&1 || true

rm -rf "$HOME/.local/share/$APP_NAME/app"

rm -f "$HOME/.local/share/applications/branchbox.desktop"
rm -f "$HOME/.local/share/mime/packages/branchbox.xml"
rm -f "$HOME/.local/share/nemo/actions/create_branchbox.nemo_action"
rm -f "$HOME/.config/autostart/branchbox-cleaner.desktop"

rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/branchbox.svg"
rm -f "$HOME/.local/share/icons/hicolor/scalable/mimetypes/application-x-branchbox.svg"

update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

nemo -q >/dev/null 2>&1 || true

cat <<EOF_DONE
Removed BranchBox app files, MIME type, icon, Nemo action, and cleanup watcher.

Stored BranchBox contents were NOT deleted:
  $HOME/.local/share/branchbox/instances

To delete all stored BranchBox contents too, run:
  rm -rf "$HOME/.local/share/branchbox"
EOF_DONE
