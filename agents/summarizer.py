"""Meeting Summarizer: 파싱된 회의 데이터 → 구조화 요약"""
import json
from utils.llm_client import ask_llm
from utils.prompts import SUMMARIZER_PROMPT

LANG_LABEL = {
    "ko": "한국어",
    "en": "English",
    "zh": "中文",
    "cn": "中文",
    "ja": "日本語",
}


async def summarize_meeting(parsed_data: dict, languages: list[str] | None = None) -> str:
    """Sonnet으로 회의 요약 생성. language 설정에 따라 출력 언어 변경."""
    lang = (languages or ["ko"])[0]
    lang_label = LANG_LABEL.get(lang, "한국어")

    summary_input = {
        "date": parsed_data.get("date"),
        "participants": parsed_data.get("participants", []),
        "topic_sections": parsed_data.get("topic_sections", []),
        "content_excerpt": _extract_content(parsed_data),
    }

    prompt = SUMMARIZER_PROMPT.format(
        lang_instruction=f"{lang_label}로 요약하세요.",
        multilang_rule="",
        parsed_data=json.dumps(summary_input, ensure_ascii=False, indent=2),
    )

    summary = await ask_llm(
        prompt,
        model="claude-sonnet-4-6",
        max_tokens=3000,
    )
    return summary.strip()


def _extract_content(parsed_data: dict, max_chars: int = 3000) -> str:
    """segments에서 핵심 내용 압축 추출"""
    segments = parsed_data.get("segments", [])
    lines = []
    total = 0
    for seg in segments:
        line = f"[{seg.get('speaker', '?')}] {seg.get('content', '')}"
        total += len(line)
        lines.append(line)
        if total > max_chars:
            lines.append("... (이하 생략)")
            break
    return "\n".join(lines)
