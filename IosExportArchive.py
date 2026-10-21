"""Split/restore the Xcode ZIP using ordinary Git files below GitHub's size limit."""
import argparse
import hashlib
import json
import pathlib
import re

PART_SIZE = 90 * 1024 * 1024
MANIFEST = "ios-export.parts.json"


def split(archive):
    root = archive.parent
    parts = []
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        while data := source.read(PART_SIZE):
            name = f"ios-export.zip.part{len(parts) + 1:03d}"
            temporary = root / (name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(root / name)
            digest.update(data)
            parts.append({"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if not parts:
        raise ValueError("Cannot split an empty Xcode export")
    manifest = {"version": 1, "size": archive.stat().st_size, "sha256": digest.hexdigest(), "parts": parts}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    expected = {part["name"] for part in parts}
    for old in root.glob("ios-export.zip.part*"):
        if re.fullmatch(r"ios-export\.zip\.part\d{3}", old.name) and old.name not in expected:
            old.unlink()
    print(f"Prepared {len(parts)} Git parts, total {manifest['size']} bytes, SHA256 {manifest['sha256']}")


def restore(root):
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if manifest["version"] != 1 or not manifest["parts"]:
        raise ValueError("Unsupported or empty Xcode export manifest")
    temporary = root / "ios-export.zip.restoring"
    digest = hashlib.sha256()
    total = 0
    try:
        with temporary.open("wb") as output:
            for index, part in enumerate(manifest["parts"], 1):
                if part["name"] != f"ios-export.zip.part{index:03d}":
                    raise ValueError("Invalid Xcode part name or order")
                part_digest = hashlib.sha256()
                part_size = 0
                with (root / part["name"]).open("rb") as source:
                    while data := source.read(4 * 1024 * 1024):
                        output.write(data)
                        digest.update(data)
                        part_digest.update(data)
                        part_size += len(data)
                if part_size != part["size"] or part_digest.hexdigest() != part["sha256"]:
                    raise ValueError("Xcode part verification failed: " + part["name"])
                total += part_size
        if total != manifest["size"] or digest.hexdigest() != manifest["sha256"]:
            raise ValueError("Restored Xcode ZIP verification failed")
        temporary.replace(root / "ios-export.zip")
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Restored and verified Xcode ZIP: {total} bytes, SHA256 {digest.hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["split", "restore"])
    parser.add_argument("path", type=pathlib.Path)
    args = parser.parse_args()
    if args.action == "split":
        split(args.path.resolve())
    else:
        restore(args.path.resolve())
