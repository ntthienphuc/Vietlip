enum ReadingMethod {
  visual(
    'visual',
    'Trực tiếp',
    'SO17 · mặc định',
    'Ưu tiên live. Hiện phụ đề gốc, không chờ AI.',
  ),
  gatewayConservative(
    'gateway_conservative',
    'AI sửa thận trọng',
    'Gateway · sau phiên',
    'Chỉ sửa khi có căn cứ trong câu. Thêm khoảng 7 giây.',
  ),
  gatewayDirect(
    'gateway_direct',
    'AI khôi phục câu',
    'Gateway · thử nghiệm',
    'Tốt nhất trên video điện thoại đã thử, nhưng có thể đổi ý. Thêm khoảng 9–12 giây.',
  ),
  localConservative(
    'local_conservative',
    'AI trên PC · thận trọng',
    'Model local · sau phiên',
    'Dùng endpoint LLM trên PC. Qwen 4B chưa giảm lỗi trong phép thử.',
  ),
  localDirect(
    'local_direct',
    'AI trên PC · khôi phục',
    'Model local · thử nghiệm',
    'Sửa câu mạnh hơn. Cần chạy LLM riêng trên PC; có thể làm câu sai hơn.',
  );

  const ReadingMethod(this.id, this.label, this.subtitle, this.description);
  final String id, label, subtitle, description;
  bool get usesAi => this != visual;
  static ReadingMethod parse(String? id) =>
      values.firstWhere((value) => value.id == id, orElse: () => visual);
}
