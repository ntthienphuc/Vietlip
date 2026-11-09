"""Verify all immutable payload files after copying or installing the bundle."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "PAYLOAD_MANIFEST.json").read_text(encoding="utf8"))
failed = []
for item in manifest["files"]:
    target = (root / item["path"]).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        failed.append(item["path"])
        continue
    with target.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != item["sha256"]:
        failed.append(item["path"])
print(json.dumps({"files_checked": len(manifest["files"]), "failed": failed}, indent=2))
raise SystemExit(1 if failed else 0)
