import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'src/app.dart';
import 'src/models/reading_method.dart';
import 'src/data/history_repository.dart';
import 'src/data/settings_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (!kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS)) {
    await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  }
  final settings = SettingsController();
  await settings.load();
  if (settings.aiProvider != AiProvider.gemini) {
    await settings.setAiProvider(AiProvider.gemini);
  }
  runApp(LipReaderApp(settings: settings, history: HistoryRepository()));
}
