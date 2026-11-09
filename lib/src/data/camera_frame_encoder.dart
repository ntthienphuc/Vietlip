import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:image/image.dart' as img;

Map<String, Object> copyCameraFrame(
  CameraImage image, {
  required int rotationDegrees,
}) => <String, Object>{
  'width': image.width,
  'height': image.height,
  'rotation': rotationDegrees,
  'format': image.format.group.name,
  'planes': image.planes
      .map(
        (plane) => <String, Object>{
          'bytes': Uint8List.fromList(plane.bytes),
          'rowStride': plane.bytesPerRow,
          'pixelStride': plane.bytesPerPixel ?? 1,
        },
      )
      .toList(growable: false),
};

Uint8List? encodeCameraFrame(Map<String, Object> payload) {
  final width = payload['width']! as int;
  final height = payload['height']! as int;
  final rotation = payload['rotation']! as int;
  final format = payload['format']! as String;
  final planes = (payload['planes']! as List).cast<Map<String, Object>>();
  if (width <= 0 || height <= 0 || planes.isEmpty) return null;

  if (format == ImageFormatGroup.jpeg.name) {
    final decoded = img.decodeJpg(planes.first['bytes']! as Uint8List);
    if (decoded == null) return null;
    final oriented = rotation == 0
        ? decoded
        : img.copyRotate(decoded, angle: rotation);
    final resized = oriented.width > 360
        ? img.copyResize(oriented, width: 360)
        : oriented;
    return Uint8List.fromList(img.encodeJpg(resized, quality: 80));
  }

  final rotatedWidth = rotation == 90 || rotation == 270 ? height : width;
  final scale = rotatedWidth > 360 ? 360 / rotatedWidth : 1.0;
  final outputWidth = (width * scale).round().clamp(1, width);
  final outputHeight = (height * scale).round().clamp(1, height);
  final output = img.Image(width: outputWidth, height: outputHeight);

  for (var y = 0; y < outputHeight; y++) {
    final sourceY = (y * height / outputHeight).floor().clamp(0, height - 1);
    for (var x = 0; x < outputWidth; x++) {
      final sourceX = (x * width / outputWidth).floor().clamp(0, width - 1);
      final color = _readPixel(format, planes, sourceX, sourceY);
      if (color == null) return null;
      output.setPixelRgba(x, y, color.$1, color.$2, color.$3, 255);
    }
  }

  final oriented = switch (rotation) {
    90 => img.copyRotate(output, angle: 90),
    180 => img.copyRotate(output, angle: 180),
    270 => img.copyRotate(output, angle: 270),
    _ => output,
  };
  // The server's MediaPipe alignment is mirror-invariant. Preserve the camera
  // buffer orientation so live and final video use the same geometry.
  return Uint8List.fromList(img.encodeJpg(oriented, quality: 80));
}

(int, int, int)? _readPixel(
  String format,
  List<Map<String, Object>> planes,
  int x,
  int y,
) {
  if (format == ImageFormatGroup.bgra8888.name && planes.length == 1) {
    final plane = planes.first;
    final bytes = plane['bytes']! as Uint8List;
    final index =
        y * (plane['rowStride']! as int) + x * (plane['pixelStride']! as int);
    if (index + 2 >= bytes.length) return null;
    return (bytes[index + 2], bytes[index + 1], bytes[index]);
  }

  if (format == ImageFormatGroup.yuv420.name && planes.length >= 3) {
    final yPlane = planes[0];
    final uPlane = planes[1];
    final vPlane = planes[2];
    final yBytes = yPlane['bytes']! as Uint8List;
    final uBytes = uPlane['bytes']! as Uint8List;
    final vBytes = vPlane['bytes']! as Uint8List;
    final yIndex =
        y * (yPlane['rowStride']! as int) + x * (yPlane['pixelStride']! as int);
    final uvX = x ~/ 2;
    final uvY = y ~/ 2;
    final uIndex =
        uvY * (uPlane['rowStride']! as int) +
        uvX * (uPlane['pixelStride']! as int);
    final vIndex =
        uvY * (vPlane['rowStride']! as int) +
        uvX * (vPlane['pixelStride']! as int);
    if (yIndex >= yBytes.length ||
        uIndex >= uBytes.length ||
        vIndex >= vBytes.length) {
      return null;
    }
    final luminance = yBytes[yIndex].toDouble();
    final u = uBytes[uIndex] - 128.0;
    final v = vBytes[vIndex] - 128.0;
    final red = (luminance + 1.402 * v).round().clamp(0, 255);
    final green = (luminance - 0.344136 * u - 0.714136 * v).round().clamp(
      0,
      255,
    );
    final blue = (luminance + 1.772 * u).round().clamp(0, 255);
    return (red, green, blue);
  }
  return null;
}
