import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/features/capture/live_caption_panel.dart';

void main() {
  testWidgets('caption stays bounded and expands full history on request', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              height: 250,
              child: LiveCaptionPanel(
                transcript: 'xin chào mọi người',
                committed: 'xin chào',
                provisional: 'mọi người',
                status: liveStatusLabel('pausing', 'idle'),
                unavailable: false,
                captureFps: 24.1,
                elapsedMs: 600,
              ),
            ),
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    expect(find.text('Đang chờ khoảng ngừng để chốt đoạn…'), findsOneWidget);
    await tester.tap(find.byTooltip('Xem toàn bộ phụ đề'));
    await tester.pumpAndSettle();
    expect(find.text('Bản ghi của phiên'), findsOneWidget);
    expect(find.text('Sao chép bản ghi'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
