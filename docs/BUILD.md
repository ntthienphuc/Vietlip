# Build VietLip for Android and Windows

This guide builds the Android APK and the Windows x64 inference server for VietLip 1.10.5. Run the commands in PowerShell from the checkout root (the directory containing `pubspec.yaml`). Use a short path such as `C:\src\Vietlip`.

## Android APK

Use Flutter 3.44.0 (Dart 3.12.0), Android SDK Platform 36, Android Build Tools, and a JDK compatible with Gradle 9.1, such as JDK 17 or 21. Run `flutter doctor -v` to check which SDK and JDK Flutter will use. The initial build downloads Flutter and Gradle dependencies. The checkpoint is needed only on the PC running inference.

```powershell
flutter pub get --enforce-lockfile
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --debug --no-pub
```

The debug APK is written to `build\app\outputs\flutter-apk\app-debug.apk`. Use a separate test device or emulator if the phone already has a release-signed installation with session history.

### Release signing

Set the following environment variables in the build session or CI secret store:

| Variable | Value |
| --- | --- |
| `LIP_READER_KEYSTORE_PATH` | Absolute path to the signing keystore |
| `LIP_READER_KEYSTORE_PASSWORD` | Keystore password |
| `LIP_READER_KEY_ALIAS` | Signing key alias |
| `LIP_READER_KEY_PASSWORD` | Password for that alias |

Run `flutter build apk --release --no-pub`. The output is `build\app\outputs\flutter-apk\app-release.apk`. Android requires the same signing certificate to update an existing installation in place.

## Windows server

1. Install Python **3.11 x64** with the Python Launcher and Tcl/Tk. To produce the installer, also install **Inno Setup 6** and ensure the Windows .NET Framework C# compiler is available. Reserve several tens of GB for dependencies, staging, temporary files, and the finished installer.
2. From the repository root, run `.\tools\get_so17.ps1`. It verifies the checkpoint and writes `server\models\SO_seed17.pt`. A second run checks the existing file.
3. Choose **one** runtime. For a CPU-only build, run `.\server\setup_server.ps1 -Runtime cpu`. For a CUDA-enabled build, run `.\server\setup_server.ps1 -Runtime gpu`. The latter installs PyTorch 2.8.0 for CUDA 12.6. On the target PC, a compatible NVIDIA driver enables GPU inference. The CUDA-enabled build also supports CPU fallback.

### Run directly from source

```powershell
.\server\.venv\Scripts\python.exe .\server\desktop_launcher.py
```

The launcher shows the LAN address, QR code, and readiness state. For a console-only session, add `--headless`. To force CPU inference during a check, also add `--device cpu`.

### Package the Windows installer

```powershell
$work = Join-Path $env:TEMP ("vietlip-build-" + [guid]::NewGuid().ToString("N"))
.\packaging\windows_server\build_installer.ps1 -StageDirectory "$work\stage" -OutputDirectory "$work\out"
$exe = Join-Path $work 'out\VietLip-Server-Setup-1.10.5.exe'
$check = Start-Process -FilePath $exe -ArgumentList '--verify' -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Installer verification failed ($($check.ExitCode))" }
```

Use a fresh staging directory for each build. Pass `-InnoCompiler` if Inno Setup is installed outside its default location. If VietLip Server 1.10.5 is already installed under the current Windows account, the builder can reuse its Python runtime and checkpoint when the checkout lacks them. Application code is always staged from the checkout. See [installer internals](../packaging/windows_server/README.md) for details.

### Gemini credentials

You can build, package, and use live captions without an API key. The EXE produced by the commands above has no bundled key. To enable suggestions, open **VietLip Server → Cài đặt key Gemini** on the PC, paste your own Gemini API key, and save it. On Android, select **Kèm gợi ý câu**.

Only the preconfigured EXE supplied in the private distribution package provisions a shared key on a fresh Windows profile. An existing key saved under the same Windows account is preserved across installations.

## Verify the installation

Run the server and packaging tests using the environment created above:

```powershell
Push-Location server
try {
    .\.venv\Scripts\python.exe -m pytest -q tests ..\packaging\windows_server\tests
} finally {
    Pop-Location
}
```

Start the server, wait for the ready indicator, and check `http://127.0.0.1:7100/healthz` on the PC (use the displayed port if different). The response should show `model_loaded: true` and `realtime_available: true`.

For an end-to-end check, install the APK on Android, connect both devices to the same LAN, scan the QR code in the app, and speak a short sentence facing the camera. End the session and confirm that the original caption appears in history. To test Gemini separately, enter a key on the PC, enable sentence suggestions on Android, and check for a second line attached to the same finalized sentence.
