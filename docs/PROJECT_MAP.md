# VietLip project layout

| Path | Responsibility |
| --- | --- |
| [lib](../lib), [android](../android) | Flutter client, Android camera capture, pairing, captions, and session history. |
| [packages/camera_android_camerax](../packages/camera_android_camerax) | CameraX adapter with the app’s orientation and frame pacing changes. |
| [server/app](../server/app) | WebSocket transport, frame preprocessing, visual speech recognition, and sentence suggestions. |
| [server/desktop_launcher.py](../server/desktop_launcher.py) and [desktop_runtime.py](../server/desktop_runtime.py) | Windows UI, QR pairing, model configuration, and readiness checks. |
| [packaging/windows_server](../packaging/windows_server) | Runtime staging, payload verification, and Windows installer assembly. |
| [test](../test) and [server/tests](../server/tests) | Flutter and server tests. Installer tests live under [packaging/windows_server/tests](../packaging/windows_server/tests). |
| [tools](../tools) | Model download, signing, and development utilities. |

Start with the [build guide](BUILD.md) for the Android APK and Windows EXE. For the public checkpoint, use the [SO17 download script](../tools/get_so17.ps1). A standard source build uses the operator’s own Gemini key if sentence suggestions are enabled.

The private 1.10.5 distribution includes the signed APK, the preconfigured Windows installer, two Vietnamese reports, and two demo videos. Its [distribution inventory and checksums](ban-giao-1.10.5/README.md) identify those files. Local build output, experimental captures, and signing material are managed outside the source tree.
