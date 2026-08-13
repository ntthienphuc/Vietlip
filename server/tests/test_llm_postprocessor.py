import json

from app.services.llm_postprocessor import (
    _HttpLlmPostprocessor,
    _validate_assisted_transcript,
)


def test_context_select_remains_nbest_only():
    prompt = _HttpLlmPostprocessor._prompt(
        mode="context_select",
        visual_transcript="tôi rất là chinh phục",
        candidates=[
            "tôi rất là chinh phục",
            "tôi tên là chinh phục",
        ],
        context_hint="Tên người nói là Thiên Phúc.",
    )

    assert "Không được sửa hoặc tạo câu mới" in prompt
    assert "selected_index" in prompt


def test_assist_allows_only_context_bound_proper_nouns():
    prompt = _HttpLlmPostprocessor._prompt(
        mode="llm_assist",
        visual_transcript="tôi tên là chinh phục",
        candidates=["tôi tên là chinh phục"],
        context_hint="Tên người nói là Thiên Phúc.",
    )

    normalized = prompt.casefold()
    assert "xuất hiện nguyên văn trong user_context" in normalized
    assert "không thêm chi tiết nào khác ngoài ngữ cảnh" in normalized


def test_assist_grounding_accepts_name_that_is_explicit_in_context():
    grounding = _validate_assisted_transcript(
        assisted="Tôi xin chào mọi người, tôi tên là Thiên Phúc.",
        candidates=[
            "tôi xin chào mọi người tôi tên là chinh phục",
        ],
        context_hint="Tên người nói là Thiên Phúc.",
    )

    assert grounding["accepted"] is True
    assert grounding["new_context_tokens"] == ["phúc", "thiên"]


def test_assist_grounding_rejects_unsupported_hallucination():
    grounding = _validate_assisted_transcript(
        assisted="Ngày mai tôi sẽ bay đến Paris để dự hội nghị.",
        candidates=["hôm nay tôi xin giới thiệu chủ đề"],
        context_hint="Chủ đề môn Ngữ văn.",
    )

    assert grounding["accepted"] is False
    assert "paris" in grounding["unsupported_tokens"]


def test_parse_assist_rejects_ungrounded_llm_json():
    result = _HttpLlmPostprocessor._parse_result(
        mode="llm_assist",
        content=json.dumps(
            {
                "assisted_transcript": "Tôi đã thắng giải quốc tế.",
                "reason": "nghe tự nhiên",
            },
            ensure_ascii=False,
        ),
        candidates=["tôi xin giới thiệu chủ đề"],
        context_hint="Môn Ngữ văn.",
        diagnostics={"provider": "test"},
    )

    assert result.assisted_transcript is None
    assert result.diagnostics["status"] == "rejected"
