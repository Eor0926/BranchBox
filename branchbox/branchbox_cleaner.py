#!/usr/bin/env python3
import json
import shutil
import sys
import time
from pathlib import Path

APP_NAME = "branchbox"
BASE_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
INSTANCES_DIR = BASE_DATA_DIR / "instances"
REGISTRY_FILE = BASE_DATA_DIR / "registry.json"
RECOVERY_DIR = Path.home() / "Desktop" / "Recovered BranchBoxes"
TRASH_FILES = Path.home() / ".local" / "share" / "Trash" / "files"

SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
]

EXCLUDED_DIRS = {
    ".local",
    ".cache",
    ".config",
    ".steam",
    ".var",
    "Games",
    "snap",
    "Trash",
}


def safe_json_read(path):
    try:
        path = Path(path)
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def safe_json_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def folder_has_contents(path):
    path = Path(path)
    return path.exists() and any(path.iterdir())


def unique_recovery_folder(name, instance_id):
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in name if c not in "/\\:*?\"<>|").strip() or "BranchBox"
    base = RECOVERY_DIR / f"{safe_name} - {instance_id[:8]}"

    if not base.exists():
        return base

    i = 2
    while True:
        candidate = RECOVERY_DIR / f"{safe_name} - {instance_id[:8]} ({i})"
        if not candidate.exists():
            return candidate
        i += 1


def branchbox_has_id(path, instance_id):
    try:
        data = json.loads(Path(path).read_text())
        return data.get("id") == instance_id
    except Exception:
        return False


def is_excluded(path):
    try:
        rel = Path(path).relative_to(Path.home())
        return bool(rel.parts and rel.parts[0] in EXCLUDED_DIRS)
    except Exception:
        return False


def find_active_branchbox(instance_id):
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue

        try:
            for path in root.rglob("*.branchbox"):
                if is_excluded(path):
                    continue
                if branchbox_has_id(path, instance_id):
                    return path
        except Exception:
            pass

    return None


def find_trashed_branchbox(instance_id):
    if not TRASH_FILES.exists():
        return None

    try:
        for path in TRASH_FILES.rglob("*.branchbox"):
            if branchbox_has_id(path, instance_id):
                return path
    except Exception:
        pass

    return None


def recover_instance_contents(instance_id, name):
    instance_dir = INSTANCES_DIR / instance_id
    items_dir = instance_dir / "items"

    if folder_has_contents(items_dir):
        target = unique_recovery_folder(name, instance_id)
        target.mkdir(parents=True, exist_ok=True)

        for child in list(items_dir.iterdir()):
            destination = target / child.name

            if destination.exists():
                destination = target / f"{child.stem} - recovered{child.suffix}"

            shutil.move(str(child), str(destination))

    if instance_dir.exists():
        shutil.rmtree(instance_dir, ignore_errors=True)


def cleanup_once():
    registry = safe_json_read(REGISTRY_FILE)
    changed = False

    for instance_id, info in list(registry.items()):
        branchbox_file = Path(info.get("file", "")).expanduser()
        name = info.get("name", "BranchBox")

        if branchbox_file.exists():
            continue

        # Workspace/icon managers may move .branchbox launchers. If we can find the
        # same ID somewhere active, update the registry instead of recovering.
        active_file = find_active_branchbox(instance_id)
        if active_file:
            registry[instance_id]["file"] = str(active_file.resolve())
            registry[instance_id]["name"] = active_file.stem
            changed = True
            continue

        # Only treat the launcher as deleted when the actual .branchbox file is in Trash.
        # A merely missing path is ignored to avoid breaking workspace file movement.
        trashed_file = find_trashed_branchbox(instance_id)
        if not trashed_file:
            continue

        recover_instance_contents(instance_id, name)
        registry.pop(instance_id, None)
        changed = True

    if changed:
        safe_json_write(REGISTRY_FILE, registry)


def main():
    if "--loop" in sys.argv:
        while True:
            cleanup_once()
            time.sleep(10)
    else:
        cleanup_once()


if __name__ == "__main__":
    main()
