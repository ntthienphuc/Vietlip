# Local CameraX bridge

Based on Flutter camera_android_camerax 0.7.4+2 (BSD license retained).
The optional `vn.lipread/native_frames` EventChannel compresses an ImageProxy
on one native worker before crossing into Dart. Standard CameraImage callbacks
remain the fallback when no native event listener is attached.

At most two outstanding events must be acknowledged on `native_frames/control`; CameraX
frames arriving meanwhile are closed immediately. Capture timestamps use the
camera clock, not event arrival. Cancel invalidates queued events; all accepted
images close in finally. Recording and preview still use the upstream plugin.

Changes: NativeFrameStream.java, three hook lines in AnalyzerProxyApi,
ProxyApiRegistrar, CameraAndroidCameraxPlugin. No change to generated Pigeon code.
