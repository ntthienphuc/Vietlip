class AlternativeTranscript {
  const AlternativeTranscript({required this.text, this.rawScore});

  final String text;
  final double? rawScore;

  factory AlternativeTranscript.fromJson(Map<String, dynamic> json) {
    return AlternativeTranscript(
      text: json['text']?.toString() ?? '',
      rawScore: (json['raw_score'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {'text': text, 'raw_score': rawScore};
}

class TranscriptionResult {
  const TranscriptionResult({
    required this.requestId,
    required this.transcript,
    required this.status,
    required this.modelId,
    required this.elapsedMs,
    required this.numFrames,
    required this.createdAt,
    required this.alternatives,
    required this.diagnostics,
    this.processingMode = 'visual_only',
    this.assistedTranscript,
    this.consensusTranscript,
    this.riskNotice,
  });

  final String requestId;
  final String transcript;
  final String status;
  final String modelId;
  final int elapsedMs;
  final int numFrames;
  final DateTime createdAt;
  final List<AlternativeTranscript> alternatives;
  final Map<String, dynamic> diagnostics;
  final String processingMode;
  final String? assistedTranscript;
  final String? consensusTranscript;
  final String? riskNotice;

  factory TranscriptionResult.fromJson(Map<String, dynamic> json) {
    return TranscriptionResult(
      requestId: json['request_id']?.toString() ?? '',
      transcript: json['transcript']?.toString() ?? '',
      status: json['status']?.toString() ?? 'review_required',
      modelId: json['model_id']?.toString() ?? 'unknown',
      elapsedMs: (json['elapsed_ms'] as num?)?.round() ?? 0,
      numFrames: (json['num_frames'] as num?)?.round() ?? 0,
      createdAt: json['created_at'] == null
          ? DateTime.now()
          : DateTime.parse(json['created_at'].toString()),
      alternatives: (json['alternatives'] as List<dynamic>? ?? const [])
          .map(
            (item) => AlternativeTranscript.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      diagnostics: Map<String, dynamic>.from(
        json['diagnostics'] as Map? ?? const {},
      ),
      processingMode: json['processing_mode']?.toString() ?? 'visual_only',
      assistedTranscript: json['assisted_transcript']?.toString(),
      consensusTranscript: json['consensus_transcript']?.toString(),
      riskNotice: json['risk_notice']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'request_id': requestId,
    'transcript': transcript,
    'status': status,
    'model_id': modelId,
    'elapsed_ms': elapsedMs,
    'num_frames': numFrames,
    'created_at': createdAt.toIso8601String(),
    'alternatives': alternatives.map((item) => item.toJson()).toList(),
    'processing_mode': processingMode,
    'assisted_transcript': assistedTranscript,
    'consensus_transcript': consensusTranscript,
    'risk_notice': riskNotice,
    'diagnostics': diagnostics,
  };
}
