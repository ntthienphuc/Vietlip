enum ReadingMethod {
  visual(
    'visual',
    'Phụ đề trực tiếp',
    'Đọc môi theo thời gian thực',
    'Xem phụ đề khi bạn nói. Máy tính đọc chuyển động môi qua camera.',
  ),
  recovery(
    'recovery',
    'Kèm gợi ý câu',
    'Phụ đề và cách diễn đạt gợi ý',
    'Xem thêm một cách diễn đạt bên dưới phụ đề gốc sau mỗi câu.',
  );

  const ReadingMethod(this.id, this.label, this.subtitle, this.description);
  final String id, label, subtitle, description;
  bool get usesAi => this != visual;
  static ReadingMethod parse(String? id) {
    if (const {
      'gateway_direct',
      'gateway_conservative',
      'local_direct',
      'local_conservative',
    }.contains(id)) {
      return recovery;
    }
    return values.firstWhere((value) => value.id == id, orElse: () => visual);
  }
}

enum AiProvider {
  gemini('gemini', 'Gemini', 'Google Flash-Lite'),
  groq('groq', 'Groq', 'GPT-OSS 120B'),
  openrouter('openrouter', 'OpenRouter', 'Model miễn phí');

  const AiProvider(this.id, this.label, this.subtitle);
  final String id, label, subtitle;
  static AiProvider parse(String? id) =>
      values.firstWhere((value) => value.id == id, orElse: () => gemini);
}
