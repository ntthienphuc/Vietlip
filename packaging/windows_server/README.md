# VietLip Windows installer

Current target: 1.7.0, Windows x64, native SO17, CPU/CUDA, local Wi-Fi/LAN.
Python and all runtime dependencies are included. The user does not need Python,
CUDA Toolkit, Flutter, a cloud account or an API key. A compatible NVIDIA driver
is needed to use CUDA; CPU remains the fallback.

`build_installer.ps1` creates a new stage using `stage_bundle.py`, validates its
hashes and imports, then compiles `VietLipServer.iss`. Install the resulting EXE
with every generated BIN beside it. The full recipe is in
[`docs/PROJECT_MAP.md`](../../docs/PROJECT_MAP.md).

The stage intentionally includes only the selected model and runtime source.
It excludes signing credentials, recordings and experimental checkpoints.
Torch compiler `.lib` files and headers are unnecessary for eager inference and
are omitted; runtime DLLs and dependency licenses are retained.

Server UI: `server/desktop_launcher.py`. Profile and relocatable paths:
`server/desktop_runtime.py`. Shortcut targets the packaged `pythonw.exe` with
the launcher script. `python311._pth` isolates imports from globally installed
Python packages and includes the bundled server modules.

The source `tools/connect_android_usb.ps1` remains a historical developer tool;
it is not shipped or used by the VietLip user workflow. Distribution uses LAN IP
entry. See `README_INSTALL.txt` for the guide included in the installer.

The old 1.1.0 scripts are archived under `packaging/legacy_windows_server_1_1`.

After removing the developer virtual environment, the preserved installed Python
3.11 runtime can stage an update without downloading the model again:

```powershell
& "$env:LOCALAPPDATA\Programs\VietLip Server\runtime\python.exe" `
  packaging/windows_server/stage_bundle.py --output E:\VietLip-stage `
  --checkpoint "$env:LOCALAPPDATA\Programs\VietLip Server\server\models\SO_seed17.pt"
.\packaging\windows_server\build_installer.ps1 -StageDirectory E:\VietLip-stage `
  -OutputDirectory E:\VietLip-installers -SkipStage
```

The checkpoint is checked against the pinned SO17 SHA-256 before copying. Inno
excludes Python bytecode/cache files. Upgrade deletes only the two retired LLM
service modules and their bytecode inside the app's own installation directory.
