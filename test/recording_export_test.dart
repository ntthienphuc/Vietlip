import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/recording_export.dart';
import 'package:lip_reader/src/features/result/recording_export_card.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('vn.lipread/recordings');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test(
    'export passes the selected recording and preserves picker cancellation',
    () async {
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, 'exportRecording');
        expect(call.arguments, {'path': '/captures/session.mp4'});
        return false;
      });
      expect(await RecordingExport.save('/captures/session.mp4'), isFalse);
      expect(() => RecordingExport.save(''), throwsArgumentError);
    },
  );

  testWidgets(
    'export cannot open two pickers and cancellation restores the button',
    (tester) async {
      final pending = Completer<bool>();
      var calls = 0;
      messenger.setMockMethodCallHandler(channel, (_) {
        calls++;
        return pending.future;
      });
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: RecordingExportCard(path: '/captures/session.mp4'),
          ),
        ),
      );
      await tester.tap(find.text('Lưu video ra máy'));
      await tester.pump();
      expect(
        tester.widget<OutlinedButton>(find.byType(OutlinedButton)).onPressed,
        isNull,
      );
      expect(calls, 1);
      pending.complete(false);
      await tester.pumpAndSettle();
      expect(find.text('Lưu video ra máy'), findsOneWidget);
      expect(find.byType(SnackBar), findsNothing);
    },
  );

  testWidgets('a missing recording gives a recoverable error', (tester) async {
    messenger.setMockMethodCallHandler(channel, (_) async {
      throw PlatformException(code: 'export_unavailable');
    });
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: RecordingExportCard(path: '/captures/missing.mp4'),
        ),
      ),
    );
    await tester.tap(find.text('Lưu video ra máy'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Video có thể đã bị xóa'), findsOneWidget);
    expect(
      tester.widget<OutlinedButton>(find.byType(OutlinedButton)).onPressed,
      isNotNull,
    );
  });
}
