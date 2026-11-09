import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/features/capture/live_capture_layout.dart';
import 'package:lip_reader/src/features/capture/live_caption_panel.dart';

void main() {
  testWidgets('live stays readable on small screens and at large text size', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    for (final size in [
      const Size(360, 640),
      const Size(412, 780),
      const Size(800, 720),
    ]) {
      for (final scale in [1.0, 1.6, 2.0]) {
        tester.view.physicalSize = size;
        await tester.pumpWidget(
          MaterialApp(
            home: MediaQuery(
              data: MediaQueryData(
                size: size,
                textScaler: TextScaler.linear(scale),
              ),
              child: Scaffold(
                body: LiveCaptureLayout(
                  header: const Text('Đang live'),
                  preview: const ColoredBox(
                    key: ValueKey('preview'),
                    color: Colors.black,
                  ),
                  captions: const LiveCaptionPanel(
                    transcript: 'bạn có thể đặt quyển sách này lên bàn không',
                    committed: 'bạn có thể đặt quyển sách',
                    provisional: 'này lên bàn không',
                    status: 'Đang chờ khoảng ngừng để chốt đoạn…',
                    unavailable: false,
                    captureFps: 25,
                    elapsedMs: 400,
                  ),
                  controls: FilledButton(
                    onPressed: () {},
                    child: const Text('Kết thúc phiên'),
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$size / $scale');
        expect(
          tester.getSize(find.byKey(const ValueKey('preview'))).height,
          greaterThanOrEqualTo(280),
        );
      }
    }
  });
}
