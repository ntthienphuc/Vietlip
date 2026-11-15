import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/features/capture/camera_viewport.dart';

PreviewGeometry geometry(int width, int height, int rotation, bool mirror) =>
    PreviewGeometry.fromMap({
      'textureId': 1,
      'width': width,
      'height': height,
      'left': 0,
      'top': 0,
      'right': width,
      'bottom': height,
      'rotationDegrees': rotation,
      'mirroring': mirror,
      'handlesCropAndRotation': false,
      'hasCameraTransform': rotation != 0,
    });

void main() {
  testWidgets('filled preview crops edges with equal scale on both axes', (
    tester,
  ) async {
    const marker = ValueKey('filled-preview');
    await tester.pumpWidget(
      const MaterialApp(
        home: Center(
          child: SizedBox(
            width: 360,
            height: 390,
            child: CameraViewport(
              sourceSize: Size(480, 720),
              fit: BoxFit.cover,
              overlay: SizedBox.shrink(),
              child: ColoredBox(key: marker, color: Colors.green),
            ),
          ),
        ),
      ),
    );
    final box = tester.renderObject<RenderBox>(find.byKey(marker));
    final matrix = box.getTransformTo(null);
    final origin = MatrixUtils.transformPoint(matrix, Offset.zero);
    final x = MatrixUtils.transformPoint(matrix, const Offset(100, 0));
    final y = MatrixUtils.transformPoint(matrix, const Offset(0, 100));
    expect((x - origin).distance, closeTo(75, .001));
    expect((y - origin).distance, closeTo(75, .001));
    expect(tester.takeException(), isNull);
  });

  testWidgets('switching ready to live reuses the last native geometry', (
    tester,
  ) async {
    const channel = MethodChannel('vn.lipread/preview_geometry');
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      (_) async => null,
    );
    Widget screen(Key key) => MaterialApp(
      home: SizedBox(
        width: 320,
        height: 280,
        child: NativeCameraPreview(
          key: key,
          textureId: 7,
          overlay: const SizedBox.shrink(),
        ),
      ),
    );
    await tester.pumpWidget(screen(const ValueKey('ready')));
    await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
      channel.name,
      const StandardMethodCodec().encodeSuccessEnvelope({
        'textureId': 7,
        'width': 480,
        'height': 720,
        'left': 0,
        'top': 0,
        'right': 480,
        'bottom': 720,
        'rotationDegrees': 0,
        'mirroring': false,
        'handlesCropAndRotation': false,
        'hasCameraTransform': false,
      }),
      (_) {},
    );
    await tester.pump();
    expect(find.byType(Texture), findsOneWidget);
    await tester.pumpWidget(screen(const ValueKey('live')));
    await tester.pump();
    expect(find.byType(Texture), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      null,
    );
  });

  testWidgets(
    'raw and StreamSharing surfaces keep upright shape without squeezing',
    (tester) async {
      const marker = ValueKey('sensor-content');
      for (final surface in [
        geometry(720, 480, 270, true),
        geometry(480, 720, 0, false),
      ]) {
        expect(surface.uprightSize, const Size(480, 720));
        await tester.pumpWidget(
          MaterialApp(
            home: Center(
              child: SizedBox(
                width: 320,
                height: 280,
                child: CameraViewport(
                  sourceSize: surface.uprightSize,
                  overlay: const SizedBox.shrink(),
                  child: surface.orient(
                    const ColoredBox(key: marker, color: Colors.green),
                  ),
                ),
              ),
            ),
          ),
        );
        final box = tester.renderObject<RenderBox>(find.byKey(marker));
        final matrix = box.getTransformTo(null);
        final origin = MatrixUtils.transformPoint(matrix, Offset.zero);
        final x = MatrixUtils.transformPoint(matrix, const Offset(100, 0));
        final y = MatrixUtils.transformPoint(matrix, const Offset(0, 100));
        // A circle remains a circle: equal length in both sensor axes even
        // when the live viewport is wide and CameraX has already rotated pixels.
        expect((x - origin).distance, closeTo((y - origin).distance, .001));
        // Full frame fits the short viewport: no face crop and no stretch.
        expect((x - origin).distance, closeTo(100 * 280 / 720, .001));
        expect(tester.takeException(), isNull);
      }
    },
  );

  testWidgets('front mirror is applied after rotation, not twice', (
    tester,
  ) async {
    const marker = ValueKey('raw');
    final surface = geometry(720, 480, 270, true);
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: Center(
          child: SizedBox.fromSize(
            size: surface.uprightSize,
            child: surface.orient(
              const ColoredBox(key: marker, color: Colors.green),
            ),
          ),
        ),
      ),
    );
    final box = tester.renderObject<RenderBox>(find.byKey(marker));
    final matrix = box.getTransformTo(null);
    final origin = MatrixUtils.transformPoint(matrix, Offset.zero);
    final horizontal =
        MatrixUtils.transformPoint(matrix, const Offset(100, 0)) - origin;
    final vertical =
        MatrixUtils.transformPoint(matrix, const Offset(0, 100)) - origin;
    expect(horizontal.dx, closeTo(0, .001));
    expect(horizontal.dy, closeTo(-100, .001));
    expect(vertical.dx, closeTo(-100, .001));
    expect(vertical.dy, closeTo(0, .001));
  });
}
