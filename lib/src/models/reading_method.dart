enum ReadingMethod {
  visual(
    'visual',
    'Trực tiếp',
    'Đọc môi theo thời gian thực',
    'Ưu tiên live. Hiện phụ đề gốc, không chờ AI.',
  ),
  recovery(
    'recovery',
    'Khôi phục câu',
    'Bản gốc + AI theo từng câu',
    'Hiện lời đọc môi ngay. Khi bạn ngừng nói, AI khôi phục câu ở khung bên dưới.',
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
  groq('groq', 'Groq', 'GPT-OSS 120B'),
  openrouter('openrouter', 'OpenRouter', 'Model miễn phí');

  const AiProvider(this.id, this.label, this.subtitle);
  final String id, label, subtitle;
  static AiProvider parse(String? id) =>
      values.firstWhere((value) => value.id == id, orElse: () => groq);
}
