"""Install with a real Inno wizard into a temporary profile, leaving Windows registration untouched."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_package_installer import CSC, ROOT, builder

ISCC = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
SERVER = ROOT.parents[1] / "server"


@unittest.skipUnless(CSC.exists() and ISCC.exists(), "Requires Windows and Inno Setup")
class GeminiInstallTest(unittest.TestCase):
    def test_default_is_installed_once_and_settings_survive_an_update(self):
        import sys

        with patch.object(sys, "path", [str(SERVER), *sys.path]):
            from desktop_gemini import configure_gemini, saved_key

        with tempfile.TemporaryDirectory(prefix="VietLip-install-test-") as temp:
            work = Path(temp)
            with patch.dict(os.environ, {"LOCALAPPDATA": str(work / "profile")}):
                self.check_installation(work, configure_gemini, saved_key)

    def check_installation(self, work, configure, saved):
        payload = work / "payload"
        payload.mkdir()
        (work / "marker.txt").write_text("runtime fixture", encoding="ascii")
        rule = next(line for line in (ROOT / "VietLipServer.iss").read_text(encoding="utf8").splitlines()
                    if 'Source: "{src}\\gemini-default.dpapi"' in line)
        rule = rule.replace(r"{localappdata}\VietLip", r"{app}\VietLip")
        script = work / "test.iss"
        script.write_text(
            "[Setup]\nAppName=VietLip isolated test\nAppVersion=1\n"
            "DefaultDirName={tmp}\\Unused\nPrivilegesRequired=lowest\nUninstallable=no\n"
            "CreateUninstallRegKey=no\nUsePreviousAppDir=no\nDisableDirPage=yes\n"
            "DiskSpanning=yes\nCompression=none\nOutputBaseFilename=VietLip-Server-Setup-test\n"
            "OutputDir=payload\n[Files]\n"
            'Source: "marker.txt"; DestDir: "{app}"\n' + rule + "\n", encoding="utf-8-sig")
        subprocess.run([str(ISCC), "/Qp", str(script)], check=True, stdout=subprocess.DEVNULL)
        seed = b"fake-key-for-private-installer-test"
        private = work / "private.exe"
        standard = work / "standard.exe"
        builder.package(payload, standard, work / "standard.json", CSC)
        builder.package(payload, private, work / "private.json", CSC, default_key=seed)
        args = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=" + str(work / "profile")]
        subprocess.run([str(standard), *args], check=True)
        self.assertFalse(configure())
        subprocess.run([str(private), "--verify"], check=True)
        self.assertFalse(saved())
        subprocess.run([str(private), *args], check=True)
        self.assertTrue(configure())
        self.assertEqual(saved().encode(), seed)
        folder = work / "profile/VietLip"
        self.assertNotIn(seed, (folder / "gemini.dpapi").read_bytes())
        self.assertNotIn(seed, (folder / "desktop-gemini-profile.json").read_bytes())
        self.assertTrue(configure("changed-in-settings"))
        ciphertext = (folder / "gemini.dpapi").read_bytes()
        for exe in [private, standard]:
            subprocess.run([str(exe), *args], check=True)
            self.assertEqual((folder / "gemini.dpapi").read_bytes(), ciphertext)
            self.assertEqual(saved(), "changed-in-settings")
