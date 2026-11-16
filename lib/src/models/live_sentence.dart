import 'transcript_rewrite.dart';

class LiveSentence {
  const LiveSentence({
    required this.id,
    required this.number,
    required this.raw,
    this.rewrite,
  });
  final String id, raw;
  final int number;
  final TranscriptRewrite? rewrite;
  bool get pending => rewrite?.pending == true;
  LiveSentence withRewrite(TranscriptRewrite value) =>
      LiveSentence(id: id, number: number, raw: raw, rewrite: value);

  Map<String, dynamic> toJson() => {
    'id': id,
    'number': number,
    'raw': raw,
    'rewrite': rewrite?.toJson(),
  };
  factory LiveSentence.fromJson(Map<String, dynamic> json) => LiveSentence(
    id: json['id']?.toString() ?? '',
    number: (json['number'] as num?)?.toInt() ?? 0,
    raw: json['raw']?.toString() ?? '',
    rewrite: json['rewrite'] is Map
        ? TranscriptRewrite.fromJson(
            Map<String, dynamic>.from(json['rewrite'] as Map),
          )
        : null,
  );
}
