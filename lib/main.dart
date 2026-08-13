import 'package:flutter/material.dart';

import 'src/app.dart';
import 'src/data/history_repository.dart';
import 'src/data/settings_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = SettingsController();
  await settings.load();
  runApp(LipReaderApp(settings: settings, history: HistoryRepository()));
}
