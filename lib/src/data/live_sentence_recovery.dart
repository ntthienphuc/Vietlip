import 'dart:async';
import 'package:flutter/foundation.dart';

import '../models/live_sentence.dart';
import '../models/reading_method.dart';
import '../models/transcript_rewrite.dart';
import 'live_lip_session.dart';

typedef SentenceRewriteCall =
    Future<TranscriptRewrite> Function(String text, String sentenceId);

/// A committed visual prefix is immutable. Each endpoint owns only its new words.
/// Replies update their sentence ID even if a newer sentence is already visible.
class LiveSentenceRecovery extends ChangeNotifier {
  LiveSentenceRecovery({
    required this.sessionId,
    required this.method,
    required this.provider,
    required this.call,
    this.timeout = const Duration(seconds: 18),
  });
  final String sessionId;
  final ReadingMethod method;
  final AiProvider provider;
  final SentenceRewriteCall call;
  final Duration timeout;
  final List<LiveSentence> _sentences = [];
  final List<int> _queue = [];
  final Set<int> _closedTurns = {};
  String _closedText = '', _draft = '';
  int _active = 0;
  bool _disposed = false;
  Completer<void>? _drained;

  List<LiveSentence> get sentences => List.unmodifiable(_sentences);
  String get draft => _draft;
  int get pendingCount => _sentences.where((s) => s.pending).length;
  Future<void> get settled => _drained?.future ?? Future<void>.value();

  void accept(LiveLipUpdate update) {
    if (_disposed ||
        !{'partial', 'segment_final', 'session_final'}.contains(update.type)) {
      return;
    }
    final stable = update.stableTranscript.trim().isEmpty
        ? update.transcript.trim()
        : update.stableTranscript.trim();
    // Never invent a replacement when an older/out-of-order cumulative packet arrives.
    if (_closedText.isNotEmpty &&
        stable != _closedText &&
        !stable.startsWith('$_closedText ')) {
      return;
    }
    _draft = stable.substring(_closedText.length).trim();
    if (update.type == 'partial') {
      notifyListeners();
      return;
    }
    if (update.turnId != null && !_closedTurns.add(update.turnId!)) return;
    if (_draft.isEmpty) return;
    final index = _sentences.length;
    final id = '$sessionId-${index + 1}';
    final pending = method.usesAi;
    _sentences.add(
      LiveSentence(
        id: id,
        number: index + 1,
        raw: _draft,
        rewrite: pending
            ? TranscriptRewrite(
                method: method.id,
                provider: provider.id,
                sentenceId: id,
                status: 'pending',
                startedAt: DateTime.now(),
              )
            : null,
      ),
    );
    _closedText = stable;
    _draft = '';
    if (pending) {
      if (_queue.length >= 6) {
        _sentences[index] = _sentences[index].withRewrite(
          TranscriptRewrite(
            method: method.id,
            provider: provider.id,
            sentenceId: id,
            status: 'unavailable',
            code: 'busy',
            message: 'AI chưa theo kịp. Câu gốc đã được giữ lại.',
          ),
        );
      } else {
        if (_drained == null || _drained!.isCompleted) {
          _drained = Completer<void>();
        }
        _queue.add(index);
      }
    }
    notifyListeners();
    _pump();
  }

  void _pump() {
    while (!_disposed && _active < 2 && _queue.isNotEmpty) {
      final index = _queue.removeAt(0);
      _active++;
      unawaited(_recover(index));
    }
  }

  Future<void> _recover(int index) async {
    final sentence = _sentences[index];
    TranscriptRewrite result;
    try {
      result = await call(sentence.raw, sentence.id).timeout(timeout);
      if (result.sentenceId != sentence.id ||
          result.provider != provider.id ||
          result.method != method.id ||
          !{'completed', 'unchanged', 'unavailable'}.contains(result.status)) {
        throw const FormatException('Mã câu AI không khớp');
      }
    } catch (_) {
      result = TranscriptRewrite(
        method: method.id,
        provider: provider.id,
        sentenceId: sentence.id,
        status: 'unavailable',
        message: 'AI chưa hoàn tất. Câu gốc đã được giữ lại.',
      );
    }
    if (_disposed) return;
    _sentences[index] = sentence.withRewrite(result);
    _active--;
    notifyListeners();
    _pump();
    if (_active == 0 && _queue.isEmpty && _drained?.isCompleted == false) {
      _drained!.complete();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    if (_drained?.isCompleted == false) _drained!.complete();
    super.dispose();
  }
}
