import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:lip_reader/src/data/history_repository.dart';
import 'package:lip_reader/src/features/history/history_screen.dart';
import 'package:lip_reader/src/models/transcription_result.dart';

void main() {
  testWidgets(
    'existing history view receives a new live result without reopening',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      final repository = HistoryRepository();
      await tester.pumpWidget(
        MaterialApp(home: HistoryScreen(history: repository)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Chưa có bản đọc môi nào'), findsOneWidget);
      await repository.add(
        TranscriptionResult.fromJson({
          'request_id': 'live-test',
          'transcript': 'một câu vừa nói',
          'model_id': 'QA-prerecorded-test',
        }),
      );
      await tester.pumpAndSettle();
      expect(find.text('một câu vừa nói'), findsOneWidget);
      expect(find.textContaining('Kiểm thử phát lại'), findsOneWidget);
      await repository.clear();
      await tester.pumpAndSettle();
      expect(find.text('Chưa có bản đọc môi nào'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      repository.dispose();
      expect(tester.takeException(), isNull);
    },
  );
}
