# VietLip Windows installer

Current target: 1.10.5, Windows x64, native SO17, CPU/CUDA, local Wi-Fi/LAN.
Python and all runtime dependencies are included. The user does not need Python,
CUDA Toolkit, Flutter, a cloud account or an API key. A compatible NVIDIA driver
is needed to use CUDA; CPU remains the fallback.

`build_installer.ps1` creates a new stage using `stage_bundle.py`, validates its
hashes and imports, then compiles `VietLipServer.iss`. The resulting EXE contains
the complete payload; no external BIN or ZIP is required. The full recipe is in
[`docs/PROJECT_MAP.md`](../../docs/PROJECT_MAP.md).

Inno's EXE and internal BIN slices are embedded by `package_installer.py` in a
small .NET Framework bootstrapper, compiled with the Windows-provided C# compiler.
The final EXE validates SHA-256 for the archive and each allowlisted member,
extracts into a unique user-owned temporary directory, runs Inno and removes
that directory on exit. Installer switches such as `/VERYSILENT` and `/LOG=...`
are forwarded. `--verify` checks the complete embedded payload without installing.
Temporary extraction needs about 3.5 GB in addition to the installed payload.
Internal slices/staging are build artifacts and are not distributed to users.

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

The default remains SO17 visual recognition. Optional per-sentence AI recovery
uses one Gemini key managed by the Windows launcher and preserves
the original caption. See [method settings](../../docs/LIVE_AI_1_10.md).
The launcher uses Google's Gemini generateContent endpoint. Windows DPAPI protects the active key for the current Windows user. Standard installers contain no credential. For a private handoff, pass `-IncludeSavedGeminiKey` to `build_installer.ps1`. The single Windows EXE then contains a recoverable shared key and must stay out of source control and public releases. The installer initializes an empty user profile before launching the server. Reinstallation preserves an existing key. Users can replace it in **Cài đặt key Gemini**. Android receives neither key. The desktop release is 1.10.5 and the frozen visual backend reports 1.10.1 in health.

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
