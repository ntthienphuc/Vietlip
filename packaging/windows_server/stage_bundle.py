"""Build a relocatable Windows runtime from the locally verified Python 3.11 env.

Only runtime files, the selected SO17 model and licenses are copied. Personal
captures, signing credentials, research checkpoints and source .env are excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

REPO = Path(__file__).resolve().parents[2]


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def ignore(path, names):
    skipped = {name for name in names if name in {
        "__pycache__", ".git", ".pytest_cache", ".ruff_cache", "tests", "test",
    } or name.endswith((".pyc", ".pyo"))}
    root = Path(path)
    if root.name == "torch":
        skipped |= {"include"}
    if root.name == "lib" and root.parent.name == "torch":
        skipped |= {name for name in names if name.endswith(".lib")}
    return list(skipped)


def copy_tree(source, target, excludes=()):
    def filtered(path, names):
        result = ignore(path, names)
        if Path(path) == source:
            result.extend(name for name in names if name in excludes)
        return result
    shutil.copytree(source, target, ignore=filtered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path, help="Explicit SO17 source when developer model cache was removed")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Use a new staging directory; existing bundles are preserved")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("Use server/.venv/Scripts/python.exe (Python 3.11)")
    base = Path(sys.base_prefix)
    packages = Path(sys.prefix) / "Lib/site-packages"
    model = args.checkpoint or REPO / "server/models/SO_seed17.pt"
    expected = "cddfb8c79f1db9d66695c0b1b7e2d98837187c600668a8aee3ccdd5b58981ecc"
    if sha256(model) != expected:
        raise ValueError("Selected checkpoint checksum mismatch")
    required = [base / "python.exe", base / "pythonw.exe", packages / "torch", model]
    if not all(path.exists() for path in required):
        raise FileNotFoundError("Incomplete runtime inputs")
    output.mkdir(parents=True)
    runtime = output / "runtime"
    runtime.mkdir()
    for name in ["python.exe", "pythonw.exe", "python3.dll", "python311.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"]:
        shutil.copy2(base / name, runtime / name)
    print("Copying Python standard runtime", flush=True)
    copy_tree(base / "DLLs", runtime / "DLLs")
    copy_tree(base / "tcl", runtime / "tcl")
    copy_tree(base / "Lib", runtime / "Lib", excludes=("site-packages", "ensurepip", "idlelib"))
    print("Copying verified CPU/CUDA dependencies (excluding compiler libraries)", flush=True)
    copy_tree(packages, runtime / "Lib/site-packages", excludes=("pip", "pip-26.3.dist-info", "ruff"))
    (runtime / "python311._pth").write_text(
        "Lib\nDLLs\nLib/site-packages\n../server\nimport site\n", encoding="utf8")
    server = output / "server"
    server.mkdir()
    for directory in ("app", "vendor", "assets"):
        copy_tree(REPO / "server" / directory, server / directory)
    for name in ("desktop_launcher.py", "desktop_runtime.py", "check_runtime.py",
                 "requirements-local-verified.txt"):
        shutil.copy2(REPO / "server" / name, server / name)
    (server / "models").mkdir()
    shutil.copy2(model, server / "models/SO_seed17.pt")
    (server / "models/MODEL.json").write_text(json.dumps({
        "file": "SO_seed17.pt", "sha256": expected, "model": "auto-avsr-vi-so_seed17",
        "precision": "float32", "purpose": "Internal application evaluation",
    }, indent=2), encoding="utf8")
    for name in ("VietLip.ico", "README_INSTALL.txt", "Start-VietLip.vbs", "verify_bundle.py"):
        shutil.copy2(Path(__file__).parent / name, output / name)
    print("Hashing the complete runtime payload", flush=True)
    entries = [{"path": str(path.relative_to(output)).replace("\\", "/"),
                "bytes": path.stat().st_size, "sha256": sha256(path)}
               for path in sorted(output.rglob("*")) if path.is_file()]
    manifest = {"app": "VietLip Server", "version": "1.7.0", "created": time.time(),
                "files": entries, "total_bytes": sum(item["bytes"] for item in entries)}
    (output / "PAYLOAD_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    print(json.dumps({"files": len(entries), "bytes": manifest["total_bytes"],
                      "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
