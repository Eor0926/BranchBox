#!/usr/bin/env python3
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote

APP_NAME = "branchbox"
BASE_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
INSTANCES_DIR = BASE_DATA_DIR / "instances"
REGISTRY_FILE = BASE_DATA_DIR / "registry.json"


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


def clean_target_dir(value):
    if not value:
        return Path.home() / "Desktop"

    value = str(value).strip().strip('"').strip("'")

    if value.startswith("file://"):
        parsed = urlparse(value)
        value = unquote(parsed.path)

    path = Path(value).expanduser()

    if path.is_file():
        return path.parent

    if path.exists() and path.is_dir():
        return path

    return Path.home() / "Desktop"


def unique_file(folder, base="New BranchBox", ext=".branchbox"):
    candidate = folder / f"{base}{ext}"
    if not candidate.exists():
        return candidate

    i = 2
    while True:
        candidate = folder / f"{base} {i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1


def main():
    target_dir = clean_target_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    target_dir.mkdir(parents=True, exist_ok=True)

    output = unique_file(target_dir)
    instance_id = str(uuid.uuid4())

    data = {
        "format": 1,
        "id": instance_id,
        "name": output.stem,
        "config": {},
    }

    output.write_text(json.dumps(data, indent=2))

    items_dir = INSTANCES_DIR / instance_id / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    registry = safe_json_read(REGISTRY_FILE)
    registry[instance_id] = {
        "file": str(output.resolve()),
        "name": output.stem,
    }
    safe_json_write(REGISTRY_FILE, registry)

    print(output)


if __name__ == "__main__":
    main()
