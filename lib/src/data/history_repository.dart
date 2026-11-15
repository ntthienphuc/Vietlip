import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/transcription_result.dart';

class HistoryRepository extends ChangeNotifier {
  static const _key = 'lip_reader_history_v1';
  static const _limit = 50;
  Future<void> _writes = Future<void>.value();

  Future<void> _write(Future<void> Function() action) {
    final next = _writes.then((_) => action());
    _writes = next.catchError((Object _) {});
    return next;
  }

  Future<List<TranscriptionResult>> list() async {
    final preferences = await SharedPreferences.getInstance();
    final rows = preferences.getStringList(_key) ?? const [];
    return rows
        .map(
          (row) => TranscriptionResult.fromJson(
            Map<String, dynamic>.from(jsonDecode(row) as Map),
          ),
        )
        .toList();
  }

  Future<void> add(TranscriptionResult result) => _write(() async {
    final preferences = await SharedPreferences.getInstance();
    final rows = preferences.getStringList(_key)?.toList() ?? <String>[];
    rows.insert(0, jsonEncode(result.toJson()));
    await preferences.setStringList(_key, rows.take(_limit).toList());
    notifyListeners();
  });

  Future<void> replaceIfPresent(TranscriptionResult result) => _write(() async {
    final preferences = await SharedPreferences.getInstance();
    final rows = preferences.getStringList(_key)?.toList() ?? <String>[];
    final index = rows.indexWhere(
      (row) => (jsonDecode(row) as Map)['request_id'] == result.requestId,
    );
    if (index < 0) {
      return; // A late AI response must never recreate cleared history.
    }
    rows[index] = jsonEncode(result.toJson());
    await preferences.setStringList(_key, rows);
    notifyListeners();
  });

  Future<void> clear() => _write(() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_key);
    notifyListeners();
  });
}
