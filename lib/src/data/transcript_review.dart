import 'dart:async';

import '../models/reading_method.dart';
import '../models/transcript_rewrite.dart';
import '../models/transcription_result.dart';
import 'history_repository.dart';
import 'lip_reader_api.dart';
import 'settings_controller.dart';

typedef RewriteCall =
    Future<TranscriptRewrite> Function(String text, ReadingMethod method);

/// Save raw immediately. Optional AI updates only the separate review field.
Future<TranscriptionResult> saveWithReview({
  required TranscriptionResult result,
  required SettingsController settings,
  required HistoryRepository history,
  RewriteCall? rewrite,
  ReadingMethod? method,
  String? serverAddress,
}) async {
  final selectedMethod = method ?? settings.readingMethod;
  // Freeze the destination with the method; changing settings cannot redirect
  // an in-flight session to a different server.
  final apiUrl = serverAddress ?? settings.apiUrl;
  final shouldRewrite =
      selectedMethod.usesAi && result.transcript.trim().isNotEmpty;
  final saved = shouldRewrite
      ? result.withRewrite(
          TranscriptRewrite(
            method: selectedMethod.id,
            status: 'pending',
            startedAt: DateTime.now(),
          ),
        )
      : result;
  await history.add(saved);
  if (!shouldRewrite) {
    return saved;
  }
  // Use a lightweight immutable API destination; no preferences are changed.
  final call =
      rewrite ??
      ((text, selected) =>
          LipReaderApi.atAddress(apiUrl).rewrite(text, selected));
  unawaited(_finish(saved, selectedMethod, history, call));
  return saved;
}

Future<void> _finish(
  TranscriptionResult saved,
  ReadingMethod method,
  HistoryRepository history,
  RewriteCall call,
) async {
  TranscriptRewrite review;
  try {
    if (saved.transcript.length > 4000) {
      throw const FormatException('Phiên quá dài');
    }
    review = await call(
      saved.transcript,
      method,
    ).timeout(const Duration(seconds: 32));
  } catch (_) {
    review = TranscriptRewrite(
      method: method.id,
      status: 'unavailable',
      message: 'AI chưa hoàn tất. Bản phụ đề gốc đã được giữ lại.',
    );
  }
  try {
    await history.replaceIfPresent(saved.withRewrite(review));
  } catch (_) {
    // The raw entry was already saved; storage failure cannot erase it.
  }
}
