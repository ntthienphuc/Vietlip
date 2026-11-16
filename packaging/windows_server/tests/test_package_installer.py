"""Windows integration checks for the final single-EXE bootstrapper."""

import base64
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "package_installer", ROOT / "package_installer.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


@unittest.skipUnless(CSC.exists(), "Windows .NET Framework compiler is required")
class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="VietLip-installer-test-")
        cls.root = Path(cls.temp.name)
        cls.payload = cls.root / "payload"
        cls.payload.mkdir()
        source = cls.root / "FakeSetup.cs"
        source.write_text(
            """using System; using System.IO; using System.Linq; using System.Text;
class FakeSetup { static int Main(string[] args) {
var output=args.Single(a=>a.StartsWith("/TESTLOG=")).Substring(9);
File.WriteAllLines(output,args.Select(a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a))));
return 7; } }""",
            encoding="utf8",
        )
        subprocess.run(
            [
                str(CSC),
                "/nologo",
                "/target:exe",
                "/reference:System.Core.dll",
                "/out:" + str(cls.payload / "VietLip-Server-Setup-1.10.1.exe"),
                str(source),
            ],
            check=True,
        )
        (cls.payload / "VietLip-Server-Setup-1.10.1-1.bin").write_bytes(
            bytes(range(256)) * 4096
        )
        cls.final = cls.root / "final.exe"
        cls.receipt = builder.package(
            cls.payload, cls.final, cls.root / "receipt.json", CSC
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_payload_verifies(self):
        self.assertEqual(
            subprocess.run([str(self.final), "--verify"], check=False).returncode, 0
        )

    def test_quiet_install_forwards_arguments_exit_code_and_cleans_temp(self):
        output = self.root / "argument log.txt"
        args = [
            "/VERYSILENT",
            "/TESTLOG=" + str(output),
            "spaces and unicode Việt",
            'a"quote',
            "trailing\\",
        ]
        temp_root = Path(tempfile.gettempdir())
        before = set(temp_root.glob("VietLip-setup-*"))
        self.assertEqual(
            subprocess.run([str(self.final), *args], check=False).returncode, 7
        )
        actual = [
            base64.b64decode(line).decode("utf8")
            for line in output.read_text().splitlines()
        ]
        self.assertEqual(actual, args)
        self.assertEqual(set(temp_root.glob("VietLip-setup-*")), before)

    def test_modified_archive_is_rejected(self):
        damaged = self.root / "damaged.exe"
        shutil.copy2(self.final, damaged)
        with damaged.open("r+b") as stream:
            stream.seek(self.receipt["payload_offset"] + 40)
            value = stream.read(1)
            stream.seek(-1, 1)
            stream.write(bytes([value[0] ^ 1]))
        self.assertEqual(
            subprocess.run([str(damaged), "--verify"], check=False).returncode, 2
        )

    def test_truncated_footer_is_rejected(self):
        damaged = self.root / "truncated.exe"
        damaged.write_bytes(self.final.read_bytes()[:-8])
        self.assertEqual(
            subprocess.run([str(damaged), "--verify"], check=False).returncode, 2
        )

    def test_existing_final_is_preserved(self):
        original = builder.sha256(self.final)
        with self.assertRaises(FileExistsError):
            builder.package(self.payload, self.final, self.root / "second.json", CSC)
        self.assertEqual(builder.sha256(self.final), original)

    def test_missing_slices_are_rejected(self):
        empty = self.root / "incomplete"
        empty.mkdir()
        shutil.copy2(next(self.payload.glob("*.exe")), empty)
        with self.assertRaises(ValueError):
            builder.package(
                empty, self.root / "incomplete.exe", self.root / "incomplete.json", CSC
            )


if __name__ == "__main__":
    unittest.main()
