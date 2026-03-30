"""Transcript Parser: 클로바노트 전사본 → 구조화 JSON"""
import json
import re
from datetime import date as date_cls
from utils.llm_client import ask_llm
from utils.prompts import PARSER_PROMPT


def _quick_parse(transcript: str, today: str) -> dict | None:
    """LLM 없이 빠른 파싱 시도 (클로바노트 / 다글로 포맷 모두 지원)"""
    # 클로바노트: 화자 N HH:MM:SS
    clova_pattern = re.compile(
        r"(화자\s*\d+|SPEAKER[_\s]\d+)\s+(\d{1,2}:\d{2}:\d{2})\s*\n?(.*?)(?=(?:화자\s*\d+|SPEAKER[_\s]\d+)\s+\d|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    # 다글로: MM:SS Speaker N
    daglo_pattern = re.compile(
        r"(\d{1,2}:\d{2})\s+(Speaker\s*\d+)\s*\n?(.*?)(?=\d{1,2}:\d{2}\s+Speaker\s*\d+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    clova_matches = clova_pattern.findall(transcript)
    daglo_matches = daglo_pattern.findall(transcript)

    # 더 많이 매칭된 포맷 사용
    if len(daglo_matches) >= len(clova_matches) and daglo_matches:
        # 다글로: (timestamp, speaker, content)
        matches = [(spk, ts, content) for ts, spk, content in daglo_matches]
    else:
        matches = clova_matches

    if not matches:
        return None

    segments = []
    speakers = set()
    for speaker, timestamp, content in matches:
        speaker = speaker.strip()
        content = content.strip()
        if content:
            speakers.add(speaker)
            segments.append({
                "speaker": speaker,
                "timestamp": timestamp.strip(),
                "content": content,
                "topic": "",
            })

    if not segments:
        return None

    return {
        "date": today,
        "participants": list(speakers),
        "segments": segments,
        "topic_sections": [],
        "duration_minutes": 0,
    }


async def parse_transcript(transcript: str) -> dict:
    today = date_cls.today().isoformat()

    # 빠른 파싱 먼저 시도
    quick = _quick_parse(transcript, today)

    # LLM으로 상세 파싱 (주제 분류, 날짜 추론 포함)
    prompt = PARSER_PROMPT.format(transcript=transcript[:4000], today=today)
    try:
        raw = await ask_llm(prompt, max_tokens=3000)
        # JSON 추출 (코드블록 제거)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        parsed = json.loads(raw)

        # date 기본값 보정
        if not parsed.get("date"):
            parsed["date"] = today

        # 빠른 파싱에서 segments가 더 충실하면 병합
        if quick and len(quick["segments"]) > len(parsed.get("segments", [])):
            parsed["segments"] = quick["segments"]
            parsed["participants"] = quick["participants"]

        return parsed
    except Exception:
        # LLM 실패 시 규칙 기반 결과 반환
        if quick:
            return quick
        # 최후 폴백
        return {
            "date": today,
            "participants": [],
            "segments": [{"speaker": "전체", "timestamp": "", "content": transcript, "topic": ""}],
            "topic_sections": [],
            "duration_minutes": 0,
        }
