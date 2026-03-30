"""Meeting Summarizer: 파싱된 회의 데이터 → 구조화 요약"""
import json
from utils.llm_client import ask_llm
from utils.prompts import SUMMARIZER_PROMPT


async def summarize_meeting(parsed_data: dict) -> str:
    """Sonnet으로 회의 요약 생성"""
    # 요약용 데이터 (전체 segments는 너무 길 수 있으므로 내용만 압축)
    summary_input = {
        "date": parsed_data.get("date"),
        "participants": parsed_data.get("participants", []),
        "topic_sections": parsed_data.get("topic_sections", []),
        "content_excerpt": _extract_content(parsed_data),
    }

    prompt = SUMMARIZER_PROMPT.format(
        parsed_data=json.dumps(summary_input, ensure_ascii=False, indent=2)
    )

    summary = await ask_llm(
        prompt,
        model="claude-sonnet-4-6",
        max_tokens=2000,
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
