# Camera preview: portrait and proportional framing

Delivered Android 1.4.1+6 to the connected Samsung SM-G965F (Galaxy S9+),
Android 10, on 2026-11-06. Updated in place, preserving application data.

## Cause verified on the phone

The activity remained portrait, but starting recording with frame streaming
changed the CameraX preview surface. Native TransformationInfo logs show:

| State | Buffer | Rotation | Mirror | hasCameraTransform |
|---|---|---|---|---|
| Ready | 720 x 480 | 270 degrees | true | true |
| Live | 480 x 720 | 0 degrees | false | false |
| Stopped | 720 x 480 | 270 degrees | true | true |

SurfaceProducer.handlesCropAndRotation was false throughout this device run.
Using sensor orientation alone rotated the already-upright live buffer again.
Separately, tight layout constraints stretched the preview to the camera card.

The native bridge now forwards each current SurfaceRequest's transformation
to Flutter. The preview applies its crop, rotation and mirroring in order,
then scales uniformly with BoxFit.cover. Rounded clipping and the face guide
remain. Some edges are cropped to fill the card; horizontal and vertical scales
remain equal. The portrait activity and capture locks remain enabled.

The last geometry is cached across ready/live widget replacement. This avoids
a spinner when the incoming broadcast subscriber overlaps the outgoing one
without causing a new native onListen event. Old surface callbacks are ignored
after replacement or release.

References: [CameraX transformation contract](https://developer.android.com/reference/androidx/camera/core/SurfaceRequest.TransformationInfo)
and [matching Flutter camera issue](https://github.com/flutter/flutter/issues/180075).

## Verification

- flutter analyze --no-pub: no issues.
- flutter test --no-pub: all 15 tests passed, including rotation/mirror geometry,
  uniform scaling in ready/live aspect ratios, and geometry replay on remount.
- Android profile APK built and signature verified; installed package reports
  versionName 1.4.1 and versionCode 6.
- Actual phone: ready -> live -> stop -> live again -> stop. All inspected
  screenshots remain upright, fill the rounded viewport, and preserve the
  proportions of circular objects in view.
- Live UI displayed 25 fps. Transport log for the first final-build session:
  1,296 encoded frames / 53.133 seconds = 24.39 fps, mean encode 11.15 ms.
  Restarted session: 3,679 / 148.187 seconds = 24.83 fps, mean encode 12.76 ms.
- Left the phone at the capture screen with recording stopped.

This run validates preview geometry and camera transport on this device.
The phone faced a room/ceiling during these checks, so it does not add a new
human lip-reading accuracy result or validate other Android devices/iPhones.
Previous human-caption results remain documented in DEVICE_S9_2026-11-06.md.

## Artifacts

- output/LipReader-App-Android-v1.4.1-device.apk (signed, installed)
- artifacts/orientation_v141/DELIVERY_RECEIPT.json (hashes and verification)
- artifacts/orientation_v141/verified-ready.png
- artifacts/orientation_v141/verified-live.png
- artifacts/orientation_v141/verified-stopped.png
- artifacts/orientation_v141/verified-restarted.png
- artifacts/orientation_v141/verified-final-ready.png
- artifacts/orientation_v141/device-log.txt
- artifacts/orientation_v141/tests-final.log
- artifacts/orientation_v141/analyze-final.log
- artifacts/orientation_v141/build-remount.log

Other screenshots in that directory include intermediate unsuccessful attempts;
the verified-* files above are the final installed build.
