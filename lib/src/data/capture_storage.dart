import 'dart:io';
import 'package:path_provider/path_provider.dart';

/// Camera and picker caches are temporary. Keep recordings in app documents.
Future<String> preserveRecording(String source) async {
  final documents = await getApplicationDocumentsDirectory();
  final captures = Directory('${documents.path}/captures');
  await captures.create(recursive: true);
  final target =
      '${captures.path}/lip_${DateTime.now().microsecondsSinceEpoch}.mp4';
  await File(source).copy(target);
  return target;
}
