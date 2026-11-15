"""Create the two-file user delivery from an already validated release kit.

This repackages existing binaries; it never rebuilds or removes source files.
Every release hash is checked, then every ZIP entry is read back and checked.
"""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def digest(stream):
    checksum = hashlib.sha256()
    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        checksum.update(block)
    return checksum.hexdigest()


def file_digest(path):
    with path.open("rb") as stream:
        return digest(stream)


def package(kit, output, receipt):
    kit = kit.resolve(strict=True)
    manifest = json.loads((kit / "SHA256SUMS.json").read_text(encoding="utf-8-sig"))
    version = manifest["version"]
    sources = {}
    for row in manifest["files"]:
        path = (kit / row["file"]).resolve(strict=True)
        path.relative_to(kit)
        if path.stat().st_size != row["bytes"] or file_digest(path) != row["sha256"]:
            raise ValueError(f"Release source mismatch: {row['file']}")
        sources[row["file"]] = path

    apk_names = [name for name in sources if name.endswith(".apk")]
    if len(apk_names) != 1:
        raise ValueError("Expected exactly one validated APK")
    output.mkdir(parents=True, exist_ok=False)
    apk = output / Path(apk_names[0]).name
    shutil.copy2(sources[apk_names[0]], apk)
    archive = output / f"VietLip-Windows-{version}.zip"
    expected = {}
    # BIN payloads are already compressed. Storing avoids an expensive second
    # compression pass and remains compatible with Windows Extract All.
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for name, path in sources.items():
            if name == apk_names[0]:
                continue
            # Keep the old instructions as provenance; give the new layout its
            # own clear entry point at the top of the ZIP.
            entry = (
                "03-Huong-dan/BAT_DAU_BO_CAI_GOC.txt" if name == "BAT_DAU.txt" else name
            )
            target.write(path, entry)
            expected[entry] = file_digest(path)
        target.write(kit / "SHA256SUMS.json", "03-Huong-dan/SHA256_BO_CAI_GOC.json")
        expected["03-Huong-dan/SHA256_BO_CAI_GOC.json"] = file_digest(
            kit / "SHA256SUMS.json"
        )
        instructions = (
            f"VIETLIP {version} — CÀI ĐẶT QUA WI-FI\n\n"
            "1. Giải nén toàn bộ ZIP này bằng Extract All.\n"
            f"2. Chạy 02-Server-Windows/VietLip-Server-Setup-{version}.exe.\n"
            "   Giữ nguyên hai file BIN cạnh EXE khi cài.\n"
            "3. Mở VietLip Server từ Start Menu và chờ Sẵn sàng đọc môi.\n"
            f"4. Cài file VietLip-{version}.apk đi kèm riêng trên Android.\n"
            "5. PC và điện thoại dùng cùng Wi-Fi; nhập IP hiển thị trên server\n"
            "   vào Cài đặt của app, bấm Lưu và kiểm tra rồi Bắt đầu đọc môi.\n\n"
            "Hướng dẫn và giới hạn thử nghiệm nằm trong 03-Huong-dan.\n"
            "Phụ đề chỉ dùng hình ảnh; độ chính xác câu tự do còn hạn chế.\n"
        ).encode("utf-8-sig")
        target.writestr("BAT_DAU.txt", instructions)
        expected["BAT_DAU.txt"] = hashlib.sha256(instructions).hexdigest()
        target.writestr("SHA256_NOI_DUNG.json", json.dumps(expected, indent=2))

    with zipfile.ZipFile(archive) as source:
        if len(source.namelist()) != len(set(source.namelist())):
            raise ValueError("Duplicate archive entry")
        for name, checksum in expected.items():
            with source.open(name) as stream:
                if digest(stream) != checksum:
                    raise ValueError(f"ZIP readback mismatch: {name}")
    if file_digest(apk) != file_digest(sources[apk_names[0]]):
        raise ValueError("APK copy mismatch")
    result = {
        "version": version,
        "source_kit": str(kit),
        "output": str(output.resolve()),
        "source_hashes_verified": True,
        "all_zip_entry_sha256_verified": True,
        "zip_entries": len(expected) + 1,
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_digest(path),
            }
            for path in (apk, archive)
        ],
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    package(args.kit, args.output, args.receipt)
