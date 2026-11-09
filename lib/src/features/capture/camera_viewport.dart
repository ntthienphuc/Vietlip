import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Geometry belongs to the current CameraX surface, not to the sensor alone.
/// StreamSharing can replace a 720x480/270-degree surface with 480x720/0 degrees.
class PreviewGeometry {
  PreviewGeometry.fromMap(Map<dynamic, dynamic> data)
    : textureId = (data['textureId'] as num).toInt(),
      size = Size(
        (data['width'] as num).toDouble(),
        (data['height'] as num).toDouble(),
      ),
      crop = Rect.fromLTRB(
        (data['left'] as num).toDouble(),
        (data['top'] as num).toDouble(),
        (data['right'] as num).toDouble(),
        (data['bottom'] as num).toDouble(),
      ),
      quarterTurns = (data['rotationDegrees'] as num).toInt() ~/ 90,
      mirror = data['mirroring'] == true,
      transformedBySurface =
          data['handlesCropAndRotation'] == true &&
          data['hasCameraTransform'] == true;

  final int textureId;
  final Size size;
  final Rect crop;
  final int quarterTurns;
  final bool mirror;
  final bool transformedBySurface;

  Size get uprightSize =>
      quarterTurns.isOdd ? Size(crop.height, crop.width) : crop.size;

  Widget orient(Widget texture) {
    if (transformedBySurface) return texture;
    final cropped = SizedBox.fromSize(
      size: crop.size,
      child: ClipRect(
        child: OverflowBox(
          alignment: Alignment.topLeft,
          minWidth: size.width,
          maxWidth: size.width,
          minHeight: size.height,
          maxHeight: size.height,
          child: Transform.translate(
            offset: -crop.topLeft,
            child: SizedBox.fromSize(size: size, child: texture),
          ),
        ),
      ),
    );
    final upright = RotatedBox(quarterTurns: quarterTurns, child: cropped);
    // CameraX defines mirroring in upright coordinates, after rotation.
    return mirror ? Transform.flip(flipX: true, child: upright) : upright;
  }
}

/// Shows the whole upright image with uniform scale. The overlay shares the
/// image coordinates, including when the viewport has letterboxing.
class CameraViewport extends StatelessWidget {
  const CameraViewport({
    required this.sourceSize,
    required this.child,
    required this.overlay,
    super.key,
  });
  final Size sourceSize;
  final Widget child;
  final Widget overlay;

  @override
  Widget build(BuildContext context) => ClipRect(
    child: FittedBox(
      fit: BoxFit.contain,
      child: SizedBox.fromSize(
        size: sourceSize,
        child: Stack(
          fit: StackFit.expand,
          children: [
            child,
            IgnorePointer(child: overlay),
          ],
        ),
      ),
    ),
  );
}

class NativeCameraPreview extends StatelessWidget {
  const NativeCameraPreview({
    required this.textureId,
    required this.overlay,
    super.key,
  });
  final int textureId;
  final Widget overlay;
  static PreviewGeometry? _latestGeometry;
  static final Stream<PreviewGeometry> _geometry =
      const EventChannel(
        'vn.lipread/preview_geometry',
      ).receiveBroadcastStream().map((event) {
        final geometry = PreviewGeometry.fromMap(event as Map);
        _latestGeometry = geometry;
        return geometry;
      });

  @override
  Widget build(BuildContext context) => StreamBuilder<PreviewGeometry>(
    stream: _geometry,
    // The ready and live layouts overlap for one Flutter frame. A broadcast
    // listener added in that frame does not trigger a fresh native onListen.
    initialData: _latestGeometry,
    builder: (context, snapshot) {
      final geometry = snapshot.data;
      if (geometry == null || geometry.textureId != textureId) {
        return const Center(
          child: CircularProgressIndicator(color: Colors.white),
        );
      }
      return CameraViewport(
        sourceSize: geometry.uprightSize,
        overlay: overlay,
        child: geometry.orient(Texture(textureId: textureId)),
      );
    },
  );
}
