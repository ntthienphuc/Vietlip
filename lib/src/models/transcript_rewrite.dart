class TranscriptRewrite {
  const TranscriptRewrite({
    required this.method,
    required this.status,
    this.text = '',
    this.modelId,
    this.message,
    this.elapsedMs = 0,
    this.startedAt,
    this.provider = 'groq',
    this.sentenceId,
    this.code,
  });

  final String method, status, text;
  final String? modelId, message;
  final int elapsedMs;
  final DateTime? startedAt;
  final String provider;
  final String? sentenceId, code;
  bool get pending =>
      status == 'pending' &&
      startedAt != null &&
      DateTime.now().difference(startedAt!).inSeconds < 40;
  bool get hasText =>
      (status == 'completed' || status == 'unchanged') && text.isNotEmpty;

  factory TranscriptRewrite.fromJson(Map<String, dynamic> json) =>
      TranscriptRewrite(
        method: json['method']?.toString() ?? 'visual',
        status: json['status']?.toString() ?? 'unavailable',
        text: json['text']?.toString() ?? '',
        modelId: json['model_id']?.toString(),
        message: json['message']?.toString(),
        elapsedMs: (json['elapsed_ms'] as num?)?.round() ?? 0,
        startedAt: DateTime.tryParse(json['started_at']?.toString() ?? ''),
        provider: json['provider']?.toString() ?? 'groq',
        sentenceId: json['sentence_id']?.toString(),
        code: json['code']?.toString(),
      );

  Map<String, dynamic> toJson() => {
    'method': method,
    'status': status,
    'text': text,
    'model_id': modelId,
    'message': message,
    'elapsed_ms': elapsedMs,
    'started_at': startedAt?.toIso8601String(),
    'provider': provider,
    'sentence_id': sentenceId,
    'code': code,
  };
}
